"""Life-sciences retrieval-as-context for the closure and graph approaches. The HEDIS counterpart is
server/context_retrieval.py; same shapes (MLflow-retriever documents {page_content, metadata}), same contract:
return what the layer HOLDS for a question, never an answer computed for it.

  graph_context    Ontobricks (ClinicalStudyLab): entity-link the question (participant / site / study / rule ids,
                   MONDO codes and a small lexicon of study terms) to graph nodes, then return the k-hop subgraph around
                   them from the live triplestore. From a linked participant, its own record edges come first.
  closure_context  The standards closures as tools: resolve the question's disease / drug-class concepts and the
                   protocol's concept classes to nodes, walk mondo_closure / medrt_class_closure, and join the
                   participants recorded under each subtree (medical history or a concomitant medication).
  CLOSURE_TOOLS / closure_tool   the same tools as single calls (the closure approach's one query).
"""

from __future__ import annotations

import re

NS = "https://clinical-study-lab.example/ontology/"
_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"

# Study terms -> graph node anchors (local ids). Entity linking only: every value is a NODE in the graph, never an
# answer edge. Mirrors HEDIS's LEXICON (diabetes -> Condition/E11, statin -> DrugClass/...).
LEXICON: dict[str, list[str]] = {
    "weight-related comorbidit": ["ConceptClass/WRC-V1", "ConceptClass/WRC-V2"],
    "comorbidit": ["ConceptClass/WRC-V1", "ConceptClass/WRC-V2"],
    "sleep apnea": ["Disease/MONDO:0007147", "ConceptClass/WRC-V2"],
    "exclusionary": ["ConceptClass/EXCL-MH-V1"], "excluded": ["ConceptClass/EXCL-MH-V1", "AnalysisPopulation/PPS"],
    "per-protocol": ["AnalysisPopulation/PPS"], "full analysis set": ["AnalysisPopulation/FAS"],
    "prohibit": ["ConceptClass/PROHIB-CM-V1"], "glp-1": ["DrugClass/MEDRT:N0000178480"],
    "appetite suppress": ["DrugClass/MEDRT:N0000175372"],
    "week 24": ["EndpointDefinition/EP-A-WT24"], "body weight": ["BiomedicalConcept/COSMOS_BC:C81328"],
    "percent change": ["EndpointDefinition/EP-A-WT24"],
    "bmi": ["BiomedicalConcept/COSMOS_BC:C16358", "BiomedicalConcept/COSMOS_BC:C164634"],
    "height": ["BiomedicalConcept/COSMOS_BC:C164634"],
    "amendment 1": ["StudyVersion/CSL-A.P2.0"], "protocol 2.0": ["StudyVersion/CSL-A.P2.0"],
    "protocol 1.0": ["StudyVersion/CSL-A.P1.0"], "sap v2.0": ["EndpointRuleVersion/EP-A-WT24.R2"],
    "monitoring": ["Site/SITE-118"],
}
_ID_PATTERNS = [
    (r"\bCSL-[AB]-\d{3}-\d{4}\b", "Participant/{}"),
    (r"\bSITE-\d{3}\b", "Site/{}"),
    (r"\bEP-[AB]-WT24\.R\d\b", "EndpointRuleVersion/{}"),
    (r"\bMONDO:\d{7}\b", "Disease/{}"),
    (r"\bCSL-[AB]\b(?!-)", "Study/{}"),
]
# Person-level edges: taken in full from a linked participant, never expanded across the population.
_PERSON_PREDS = ["screenedFor", "atSite", "hasMedicalHistory", "hasConMed", "hasObservation"]
# High-volume edges INTO a person or record (forParticipant, derivedUnder...) are sampled, not dumped.
_FANIN_PREDS = ["forParticipant", "derivedUnder", "generatedBy", "codedAs", "measures", "conformsTo", "hasUnit",
                "originatesFrom", "usesBaselineObservation", "usesFollowupObservation"]
MAX_HOPS = 3


def link_entities(question: str) -> set[str]:
    q = question.lower()
    out: set[str] = set()
    for term, anchors in LEXICON.items():
        if term in q:
            out.update(anchors)
    for pat, tpl in _ID_PATTERNS:
        out.update(tpl.format(m) for m in re.findall(pat, question))
    if "Participant/" in " ".join(out):
        out.discard("Study/CSL-A")  # "CSL-A-103-0137" also matches the study id; the participant is the anchor
    return out


def _iri_list(nodes) -> str:
    return ", ".join("'" + (n if n.startswith("http") else NS + n).replace("'", "") + "'" for n in sorted(nodes))


def _short(iri: str) -> str:
    return iri[len(NS):] if iri and iri.startswith(NS) else (iri or "").rsplit("/", 1)[-1]


_SCHEMA: dict[str, str] = {}


def graph_schema(run_sql, graph: str) -> str:
    if graph not in _SCHEMA:
        rows = run_sql(
            f"SELECT regexp_extract(predicate, '([^/#]+)$', 1) AS p, regexp_extract(subject, 'ontology/([^/]+)/', 1) AS st, "
            f"coalesce(nullif(regexp_extract(object, 'ontology/([^/]+)/', 1), ''), 'literal') AS ot, count(*) AS n "
            f"FROM {graph} GROUP BY 1, 2, 3 ORDER BY 1, 4 DESC")
        _SCHEMA[graph] = "; ".join(f"{r['p']}: {r['st'] or '?'} -> {r['ot']} ({int(r['n']):,})" for r in rows
                                   if r["p"] not in ("type", "label"))
    return _SCHEMA[graph]


def graph_context(question: str, run_sql, graph: str) -> list[dict]:
    """k-hop subgraph around the question's linked entities (graph-RAG). Unlinked questions retrieve nothing."""
    seeds = link_entities(question)
    if not seeds:
        return []
    seen: dict[tuple, tuple[int, str]] = {}

    def add(rows, hop, tier):
        for r in rows:
            seen.setdefault((r["subject"], r["predicate"], r["object"]), (hop, tier))

    people = {n for n in seeds if n.startswith("Participant/")}
    frontier = {NS + n for n in seeds - people}
    if people:  # the participant's own record: every edge out, then what each record points at
        rows = run_sql(f"SELECT subject, predicate, object FROM {graph} WHERE subject IN ({_iri_list(people)}) "
                       f"AND predicate NOT LIKE '%rdf-syntax-ns#type' LIMIT 120")
        add(rows, 1, "participant")
        recs = {r["object"] for r in rows if r["object"].startswith(NS) and "Observation/" not in r["object"]}
        inbound = run_sql(f"SELECT subject, predicate, object FROM {graph} WHERE object IN ({_iri_list(people)}) "
                          f"AND predicate = '{NS}forParticipant' LIMIT 10")
        add(inbound, 1, "participant")
        recs |= {r["subject"] for r in inbound}
        if recs:
            rows2 = run_sql(f"SELECT subject, predicate, object FROM {graph} WHERE subject IN ({_iri_list(recs)}) "
                            f"AND predicate NOT LIKE '%rdf-syntax-ns#type' AND predicate <> '{_LABEL}' LIMIT 120")
            add(rows2, 2, "participant")
            frontier |= {r["object"] for r in rows2 if r["object"].startswith(NS)
                         and not r["object"].startswith((NS + "Participant/", NS + "WeightObservation/",
                                                         NS + "SourceRecord/"))}
    skip = ", ".join(f"'{NS}{p}'" for p in _PERSON_PREDS + _FANIN_PREDS)
    visited: set[str] = set()
    for hop in range(1, MAX_HOPS + 1):
        todo = frontier - visited
        if not todo:
            break
        lst = _iri_list(todo)
        rows = run_sql(f"SELECT subject, predicate, object FROM {graph} WHERE predicate NOT IN ({skip}) "
                       f"AND predicate NOT RLIKE '[#/](type|label)$' AND (subject IN ({lst}) OR object IN ({lst})) "
                       f"LIMIT 120")
        visited |= todo
        add(rows, hop + (1 if people else 0), "study design" if not people else "standards")
        frontier |= {x for r in rows for x in (r["subject"], r["object"])
                     if x.startswith(NS) and not x.startswith(NS + "Participant/")}
    order = sorted(seen, key=lambda k: (seen[k][0], seen[k][1] != "participant"))
    nodes = {x for k in order for x in (k[0], k[2]) if x.startswith(NS)}
    names: dict[str, str] = {}
    if nodes:
        for r in run_sql(f"SELECT subject, object FROM {graph} WHERE predicate = '{_LABEL}' "
                         f"AND subject IN ({_iri_list(nodes)})"):
            names.setdefault(r["subject"], r["object"])

    def nm(x):
        if not x.startswith(NS):
            return f"\"{x}\""
        return f"{_short(x)} \"{names[x]}\"" if x in names and names[x] != _short(x).split("/", 1)[-1] else _short(x)
    header = {"page_content": (f"Source: Ontobricks triple table {graph} (columns subject, predicate, object). Node IRIs "
                               f"are {NS}<Type>/<id> (e.g. {NS}Participant/CSL-A-103-0137, {NS}Disease/MONDO:0004982, "
                               f"{NS}ConceptClass/WRC-V1); predicate IRIs are {NS}<predicate>. Triples below are shown "
                               f"with that prefix removed. Query the graph with one SQL statement over this table "
                               f"(self-joins on subject/object; the object column mixes IRIs and literals of every type, so convert a literal with try_cast(object AS DATE / TIMESTAMP / DOUBLE): a plain CAST can fail on other predicates' rows, since Spark may evaluate it before the predicate filter; WITH "
                               f"RECURSIVE for subClassOf*).\nGraph schema (predicate: subject type -> object type, "
                               f"count): {graph_schema(run_sql, graph)}"),
              "metadata": {"source": "ontobricks", "kind": "provenance", "graph": graph, "linked_entities": sorted(seeds)}}
    return [header] + [
        {"page_content": f"({nm(k[0])}) -[{_short(k[1])}]-> ({nm(k[2])})  [{seen[k][1]}, hop {seen[k][0]}]",
         "metadata": {"source": "ontobricks", "kind": "triple", "tier": seen[k][1], "hop": seen[k][0], "graph": graph,
                      "subject": _short(k[0]), "predicate": _short(k[1]), "object": _short(k[2]),
                      "linked_entities": sorted(seeds)}}
        for k in order]


# --------------------------------------------------- closure ---------------------------------------------------
# The standards closures (vendored MONDO and MED-RT subsets): mondo_closure / medrt_class_closure (ancestor,
# descendant, depth incl. the depth-0 self row), the protocol's concept classes (class_root: a class's roots and
# carve-outs), and the content attached to the nodes: participants' coded medical history (silver_mh.CPL_MONDO_ID)
# and concomitant medications (silver_cm.CPL_RXNORM_ID -> MED-RT memberOf / has_PE -> class). One relationship (is_a)
# plus the governed class definitions; protocol rules, dates and endpoint results are not in it.
_GENERIC = {"disease", "disorder", "syndrome", "of", "the", "and", "or", "with", "without", "other", "unspecified",
            "type", "form", "specified", "related", "condition", "epc", "moa", "apc", "pe", "hc", "tc"}
_NODES: dict[str, list[dict]] = {}


def _toks(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and not w.isdigit()}


def _nodes(run_sql, std: str) -> list[dict]:
    if std not in _NODES:
        _NODES[std] = run_sql(
            f"SELECT code, max(name) AS name, 'mondo' AS h FROM {std}.mondo_hier GROUP BY code UNION ALL "
            f"SELECT code, max(name) AS name, 'medrt' AS h FROM {std}.medrt_class_hier GROUP BY code UNION ALL "
            f"SELECT concept_id AS code, label AS name, 'rxnorm' AS h FROM {std}.kb_concept WHERE scheme = 'RXNORM'")
    return _NODES[std]


_CLASS_WORDS = {"weight-related comorbidit": "WRC-V1", "comorbidit": "WRC-V1", "exclusionary": "EXCL-MH-V1",
                "prohibit": "PROHIB-CM-V1"}


def resolve_nodes(question: str, run_sql, std: str) -> list[dict]:
    """Nodes the question names: a code written literally (MONDO:0005148), a node whose every non-generic name word
    appears in the question (most specific wins), or a protocol concept class (weight-related comorbidity -> WRC-V1)."""
    q = _toks(question)
    out: dict[str, dict] = {}
    for n in _nodes(run_sql, std):
        if re.search(rf"(?<![\w:]){re.escape(n['code'])}(?![\w])", question):
            out[n["code"]] = {**n, "matched": [n["code"]]}
            continue
        w = _toks(n["name"] or "") - _GENERIC
        if w and w <= q and len(w) >= 1:
            out.setdefault(n["code"], {**n, "matched": sorted(w)})
    keep = {k: v for k, v in out.items() if not any(set(v["matched"]) < set(o["matched"]) for o in out.values())}
    for term, cls in _CLASS_WORDS.items():
        if term in question.lower():
            keep[cls] = {"code": cls, "name": f"protocol concept class {cls}", "h": "class", "matched": [term]}
    return list(keep.values())[:12]


def closure_context(question: str, run_sql, catalog: str) -> list[dict]:
    std, cs = f"{catalog}.clinical_study_standards", f"{catalog}.clinical_study"
    anchors = resolve_nodes(question, run_sql, std)
    # Protocol v3 (ADR-0028): the same entry points as the graph (link_entities: participant, site, study, rule-version
    # and concept-class ids), so closure and graph start from the same nodes.
    linked = link_entities(question)
    participants = sorted(n.split("/", 1)[1] for n in linked if n.startswith("Participant/"))
    design_ids = sorted(n.split("/", 1)[1] for n in linked if not n.startswith(("Participant/", "Disease/")))
    if not anchors and not participants and not design_ids:
        return []
    q = lambda v: "'" + str(v).replace("'", "") + "'"
    docs = [{"page_content": (f"Source: closure-table tools over {std}.mondo_closure and {std}.medrt_class_closure "
                              f"(ancestor_code, descendant_code, depth), the protocol's concept classes in "
                              f"{std}.class_root (class_id, concept_id, kind = root / exclude_root / ...), drug -> class "
                              f"edges in {std}.kb_edge (predicate medrt:memberOf / medrt:has_PE), and participants' coded "
                              f"history and medications in {cs}.silver_mh (USUBJID, CPL_MONDO_ID) and {cs}.silver_cm "
                              f"(USUBJID, CPL_RXNORM_ID, CMSTDTC)."),
             "metadata": {"source": "closure", "kind": "provenance"}}]
    for a in anchors:
        if a["h"] == "class":
            roots = run_sql(f"SELECT r.kind, r.concept_id, k.label FROM {std}.class_root r LEFT JOIN {std}.kb_concept k "
                            f"ON k.concept_id = r.concept_id WHERE r.class_id = {q(a['code'])} ORDER BY r.kind")
            docs.append({"page_content": f"class {a['code']}: " + "; ".join(
                f"{r['kind']} {r['concept_id']} {r['label'] or ''}" for r in roots),
                "metadata": {"source": "closure", "kind": "class", "anchor": a["code"]}})
            continue
        clos = f"{std}.mondo_closure" if a["h"] == "mondo" else f"{std}.medrt_class_closure"
        if a["h"] == "rxnorm":
            cls = run_sql(f"SELECT e.predicate, e.object, k.label FROM {std}.kb_edge e LEFT JOIN {std}.kb_concept k "
                          f"ON k.concept_id = e.object WHERE e.subject = {q(a['code'])} "
                          f"AND e.predicate IN ('medrt:memberOf', 'medrt:has_PE')")
            docs.append({"page_content": f"resolve_node(\"{' '.join(a['matched'])}\") -> {a['code']} ({a['name']}), "
                                         f"an RxNorm ingredient. Classes: " + "; ".join(
                                             f"{r['predicate']} {r['object']} {r['label'] or ''}" for r in cls),
                         "metadata": {"source": "closure", "kind": "subtree", "anchor": a["code"]}})
            continue
        anc = run_sql(f"SELECT ancestor_code, ancestor_name, depth FROM {clos} WHERE descendant_code = {q(a['code'])} "
                      f"AND depth > 0 ORDER BY depth")
        desc = run_sql(f"SELECT descendant_code, descendant_name, depth FROM {clos} WHERE ancestor_code = "
                       f"{q(a['code'])} ORDER BY depth, descendant_code LIMIT 30")
        docs.append({"page_content": (f"resolve_node(\"{' '.join(a['matched'])}\") -> {a['code']} ({a['name']}). "
                                      f"Ancestors: " + (", ".join(f"{r['ancestor_code']} {r['ancestor_name']} [{r['depth']}]"
                                                                 for r in anc) or "none")
                                      + f". Descendants ({len(desc)}, incl. itself): "
                                      + "; ".join(f"{r['descendant_code']} {r['descendant_name']} [{r['depth']}]"
                                                  for r in desc)),
                     "metadata": {"source": "closure", "kind": "subtree", "anchor": a["code"]}})
    for u in participants:  # the participant's own coded record, rolled up through the closures
        mh = run_sql(f"SELECT DISTINCT m.CPL_MONDO_ID AS code, m.MHTERM AS term, c.ancestor_code, c.depth "
                     f"FROM {cs}.silver_mh m JOIN {std}.mondo_closure c ON c.descendant_code = m.CPL_MONDO_ID "
                     f"WHERE m.USUBJID = {q(u)} ORDER BY code, c.depth")
        roll: dict[str, list[str]] = {}
        for x in mh:
            roll.setdefault(f"{x['code']} ({x['term']})", []).append(f"{x['ancestor_code']}[{x['depth']}]")
        cm = run_sql(f"SELECT DISTINCT cm.CPL_RXNORM_ID AS rx, cm.CMTRT AS term, e.object AS cls FROM {cs}.silver_cm cm "
                     f"LEFT JOIN {std}.kb_edge e ON e.subject = cm.CPL_RXNORM_ID AND e.predicate IN ('medrt:memberOf', "
                     f"'medrt:has_PE') WHERE cm.USUBJID = {q(u)}")
        docs.append({"page_content": (f"Participant {u}: medical-history codes with their closure ancestors: "
                                      + ("; ".join(f"{k} -> {', '.join(v)}" for k, v in roll.items()) or "none")
                                      + ". Concomitant medications and their MED-RT classes: "
                                      + (", ".join(sorted({f"{x['rx']} {x['term']} in {x['cls']}" for x in cm})) or "none")),
                     "metadata": {"source": "closure", "kind": "participant"}})
    if design_ids:  # the governed rule tables for linked rule versions, study versions and classes
        ql_ = ", ".join(q(c) for c in design_ids)
        rv = run_sql(f"SELECT endpoint_version, protocol_version, sap_version, window_half_width_days, target_offset_days, "
                     f"baseline_method, review_state FROM {std}.rule_version WHERE endpoint_version IN ({ql_}) "
                     f"OR study_id IN ({ql_}) OR endpoint_id IN ({ql_})")
        sv = run_sql(f"SELECT study_version_id, study_id, protocol_version, sap_version, effective_date, change_summary "
                     f"FROM {std}.study_version WHERE study_version_id IN ({ql_}) OR study_id IN ({ql_})")
        lines = [f"rule_version: {x['endpoint_version']} protocol {x['protocol_version']} SAP {x['sap_version']} window "
                 f"±{x['window_half_width_days']} target +{x['target_offset_days']} baseline {x['baseline_method']} "
                 f"({x['review_state']})" for x in rv]
        lines += [f"study_version: {x['study_version_id']} protocol {x['protocol_version']} SAP {x['sap_version']} effective "
                  f"{x['effective_date']}: {x['change_summary']}" for x in sv]
        if lines:
            docs.append({"page_content": "Rule and study versions for the linked ids:\n" + "\n".join(lines),
                         "metadata": {"source": "closure", "kind": "design"}})
    counts = []
    for a in anchors:
        r = closure_tool("participants_under", {"groups": [[a["code"]]]}, run_sql, catalog)["rows"][0]
        counts.append(f"Participants with a recorded {r['what']} under {a['code']} ({a['name']}): {int(r['participants']):,}")
    if counts:
        docs.append({"page_content": "participants_under(...) -> " + " | ".join(counts),
                     "metadata": {"source": "closure", "kind": "content"}})
    # Edges attached to the resolved concepts: class roots / carve-outs, and drug -> class / effect / contraindication.
    codes = [a["code"] for a in anchors] + design_ids
    ql = ", ".join(q(c) for c in codes) or "''"
    edges = [f"class_root: {r['class_id']} {r['kind']} {r['concept_id']}" for r in run_sql(
        f"SELECT class_id, kind, concept_id FROM {std}.class_root WHERE class_id IN ({ql}) OR concept_id IN ({ql})")]
    edges += [f"kb_edge: {r['subject']} {r['predicate']} {r['object']}" for r in run_sql(
        f"SELECT subject, predicate, object FROM {std}.kb_edge WHERE (subject IN ({ql}) OR object IN ({ql})) AND "
        f"predicate IN ('medrt:memberOf', 'medrt:has_PE', 'medrt:CI_with', 'skos:exactMatch', 'oboInOwl:hasDbXref') "
        f"LIMIT 60")]
    if edges:
        docs.append({"page_content": "Edges attached to these concepts (class definitions, drug classes):\n"
                                     + "\n".join(edges), "metadata": {"source": "closure", "kind": "edges"}})
    from .context_retrieval import mapped_tables, table_cards
    docs.append({"page_content": ("Tables you can join the closure to (the same data the knowledge graph maps; "
                                  "query with one SQL statement):\n" + table_cards(
                                      run_sql, mapped_tables("src/ontology/life_sciences/clinical_study.r2rml.ttl"))),
                 "metadata": {"source": "closure", "kind": "tables"}})
    return docs


CLOSURE_TOOLS = {
    "resolve": "resolve(text): MONDO / MED-RT / RxNorm nodes and protocol concept classes the text names",
    "ancestors": "ancestors(code): every ancestor of a MONDO or MED-RT code with its shortest distance",
    "descendants": "descendants(code, max_depth=None): the subtree under a MONDO or MED-RT code",
    "is_under": "is_under(code, ancestor): the shortest distance from ancestor down to code, or null",
    "class_members": "class_members(class_id): the MONDO codes in a protocol concept class (WRC-V1, WRC-V2, EXCL-MH-V1): "
                     "every descendant of its roots minus every descendant of its carve-outs",
    "participants_under": "participants_under(groups, study=None, randomized_only=False): distinct participants with a "
                          "medical-history term (MONDO codes / a concept class id) or a concomitant medication (MED-RT "
                          "class or RxNorm codes) in the subtrees; groups = [[codes ORed], ...], groups are ANDed",
}


def _members_sql(std: str, class_id: str) -> str:
    q = "'" + class_id.replace("'", "") + "'"
    return (f"SELECT c.descendant_code AS code FROM {std}.mondo_closure c JOIN {std}.class_root r ON r.concept_id = "
            f"c.ancestor_code AND r.class_id = {q} AND r.kind = 'root' EXCEPT SELECT c.descendant_code FROM "
            f"{std}.mondo_closure c JOIN {std}.class_root r ON r.concept_id = c.ancestor_code AND r.class_id = {q} "
            f"AND r.kind = 'exclude_root'")


def closure_tool(tool: str, args: dict, run_sql, catalog: str) -> dict:
    std, cs = f"{catalog}.clinical_study_standards", f"{catalog}.clinical_study"
    args = args or {}
    q = lambda v: "'" + str(v).replace("'", "") + "'"

    def clos(code):
        return f"{std}.medrt_class_closure" if str(code).startswith("MEDRT:") else f"{std}.mondo_closure"
    if tool == "resolve":
        rows = resolve_nodes(args.get("text", ""), run_sql, std)
        return {"count": len(rows), "rows": [{"code": r["code"], "name": r["name"], "kind": r["h"]} for r in rows]}
    if tool == "ancestors":
        rows = run_sql(f"SELECT ancestor_code, ancestor_name, depth FROM {clos(args['code'])} WHERE descendant_code = "
                       f"{q(args['code'])} AND depth > 0 ORDER BY depth, ancestor_code")
        return {"count": len(rows), "rows": rows}
    if tool == "descendants":
        md = args.get("max_depth")
        lim = f" AND depth <= {int(md)}" if md is not None else ""
        rows = run_sql(f"SELECT descendant_code, descendant_name, depth FROM {clos(args['code'])} WHERE ancestor_code = "
                       f"{q(args['code'])}{lim} ORDER BY depth, descendant_code LIMIT 200")
        return {"count": len(rows), "rows": rows}
    if tool == "is_under":
        rows = run_sql(f"SELECT depth FROM {clos(args['code'])} WHERE ancestor_code = {q(args['ancestor'])} "
                       f"AND descendant_code = {q(args['code'])}")
        return {"count": len(rows), "rows": rows or [{"depth": None}]}
    if tool == "class_members":
        rows = run_sql(f"SELECT m.code, k.label FROM ({_members_sql(std, args['class_id'])}) m LEFT JOIN "
                       f"{std}.kb_concept k ON k.concept_id = m.code ORDER BY m.code LIMIT 300")
        return {"count": len(rows), "rows": rows}
    if tool == "participants_under":
        groups = args.get("groups") or []
        if not groups or not all(isinstance(g, list) and g for g in groups):
            raise ValueError("groups must be a non-empty list of non-empty code lists")
        where = []
        if args.get("study"):
            where.append(f"dm.STUDYID = {q(args['study'])}")
        if args.get("randomized_only"):
            where.append("dm.CPL_RANDDT IS NOT NULL")
        dm = f"SELECT USUBJID FROM {cs}.silver_dm dm" + (" WHERE " + " AND ".join(where) if where else "")
        subs, rows = [], []
        for g in groups:
            drug_cls = {x: [r["concept_id"] for r in run_sql(
                f"SELECT concept_id FROM {std}.class_root WHERE class_id = {q(x)} AND kind IN ('member_of_class', "
                f"'physiologic_effect')")] for x in g if not str(x).startswith(("MEDRT:", "RXNORM:", "MONDO:"))}
            if all(str(x).startswith(("MEDRT:", "RXNORM:")) or drug_cls.get(x) for x in g):
                classes = [x for x in g if x.startswith("MEDRT:")] + [c for x in g for c in drug_cls.get(x, [])]
                drugs = [x for x in g if x.startswith("RXNORM:")]
                parts = []
                if classes:
                    parts.append(f"SELECT e.subject AS rx FROM {std}.kb_edge e JOIN {std}.medrt_class_closure c ON "
                                 f"c.descendant_code = e.object WHERE e.predicate IN ('medrt:memberOf', 'medrt:has_PE') "
                                 f"AND c.ancestor_code IN ({', '.join(q(x) for x in classes)})")
                if drugs:
                    parts.append("SELECT explode(array(" + ", ".join(q(x) for x in drugs) + ")) AS rx")
                sub = (f"SELECT DISTINCT cm.USUBJID FROM {cs}.silver_cm cm JOIN ({' UNION '.join(parts)}) d ON d.rx = "
                       f"cm.CPL_RXNORM_ID WHERE cm.USUBJID IN ({dm})")
                what = "concomitant medication"
            else:
                codes = []
                for x in g:
                    codes.append(f"({_members_sql(std, x)})" if not str(x).startswith("MONDO:") else
                                 f"(SELECT descendant_code AS code FROM {std}.mondo_closure WHERE ancestor_code = {q(x)})")
                sub = (f"SELECT DISTINCT mh.USUBJID FROM {cs}.silver_mh mh JOIN ({' UNION '.join(codes)}) m ON m.code = "
                       f"mh.CPL_MONDO_ID WHERE mh.USUBJID IN ({dm})")
                what = "medical-history term"
            subs.append(sub)
            rows.append({"group": g, "what": what, "participants": run_sql(f"SELECT COUNT(*) AS n FROM ({sub})")[0]["n"]})
        if len(subs) > 1:
            rows.append({"group": "ALL groups", "what": "all of the above", "participants": run_sql(
                f"SELECT COUNT(*) AS n FROM ({' INTERSECT '.join('(' + x + ')' for x in subs)})")[0]["n"]})
        return {"count": len(rows), "rows": rows}
    raise ValueError(f"unknown closure tool {tool!r}; choose one of {sorted(CLOSURE_TOOLS)}")
