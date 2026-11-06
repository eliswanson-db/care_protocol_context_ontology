"""Retrieval-as-context for the two "knowledge" arms, shared by the app's Retrieval Arena and the eval harness
(src/benchmark/retrieval_eval/providers.py), so the Arena shows exactly the context that gets scored.

Both functions take a question and a `run_sql(sql) -> list[dict]` callable and return MLflow-retriever-shaped
documents ({page_content, metadata}). Neither computes an answer: they return what each knowledge layer HOLDS
for the question, which a fixed agent then reasons over.

  genie_ontology_docs  Genie Ontology's OWN retrieval (recorded from Genie One's knowledge-snippet search):
                       inferred snippets + ranked Pages + Page bodies read. No Genie One answer or SQL.
  closure_context   Closure tables as tools: resolve the question's concepts to hierarchy nodes, walk the derived
                    closure (ancestors / descendants), and join the patients recorded under each subtree.
  graph_context     Ontobricks: entity-link the question's clinical terms (and patient ids) to graph nodes, return
                    the k-hop subgraph around them over the terminology + guideline layer, from the live triplestore.
"""
from __future__ import annotations

import re

# --------------------------------------------------- graph -----------------------------------------------------
ONTO_NS = "https://care-protocol.example/ontology/"

# The cross-vocabulary guideline + structural predicates -- the graph's lift over a closure join.
GUIDELINE_PREDS = ["recommendedFor", "inDrugClass", "contraindicatedWith", "contraindicatedWhen",
                   "monitoredBy", "hasThreshold", "firstLineFor", "definedBy", "subClassOf"]
# Patient-level ABox predicates -- sampled (not exhaustively dumped) so the agent sees membership exists.
MEMBER_PREDS = ["hasDiagnosis", "eligibleFor", "prescribed", "hasCareGap"]

# Synonym -> IRI-node anchors (local names). Entity-linking only: every value is a NODE in the graph -- never a
# question-specific answer edge.
LEXICON: dict[str, list[str]] = {
    "diabetes": ["icd/E10", "icd/E11", "icd/E13"], "diabetic": ["icd/E10", "icd/E11", "icd/E13"],
    "kidney": ["icd/N18", "icd/N17", "Measure/KED", "ValueSet/COMORBID_CKD"],
    "nephropathy": ["icd/N18", "icd/E11.2"], "renal": ["icd/N18", "Measure/KED"],
    "ckd": ["icd/N18", "ValueSet/COMORBID_CKD"], "retinopathy": ["icd/E11.3", "icd/E10.3"],
    "heart failure": ["icd/I50", "ValueSet/COMORBID_HF"],
    "cardiorenal": ["icd/I50", "icd/N18", "icd/E11", "ValueSet/COMORBID_HF", "ValueSet/COMORBID_CKD"],
    "statin": ["DrugClass/DRUGCLASS-STATIN", "Measure/SPD"],
    "simvastatin": ["DrugClass/DRUGCLASS-STATIN", "Measure/SPD"],
    "metformin": ["DrugClass/DRUGCLASS-BIGUANIDE", "Threshold/eGFR_LT_30"],
    "biguanide": ["DrugClass/DRUGCLASS-BIGUANIDE"], "sglt2": ["DrugClass/DRUGCLASS-SGLT2"],
    "ace inhibitor": ["DrugClass/DRUGCLASS-ACE"], "ace": ["DrugClass/DRUGCLASS-ACE"],
    "arb": ["DrugClass/DRUGCLASS-ARB"],
    "albuminuria": ["ValueSet/ALBUMINURIA", "DrugClass/DRUGCLASS-ACE", "DrugClass/DRUGCLASS-ARB"],
    "uacr": ["ValueSet/ALBUMINURIA"], "pregnan": ["ValueSet/CONTRA_PREGNANCY"],
    "hepatic": ["ValueSet/CONTRA_HEPATIC"], "contraindicat": ["ValueSet/CONTRA_PREGNANCY", "ValueSet/CONTRA_HEPATIC"],
    "a1c": ["Measure/GSD", "part/LP-HBA1C"], "hba1c": ["Measure/GSD", "part/LP-HBA1C"],
    "glycemic": ["Measure/GSD", "ValueSet/GLYCEMIC"],
    "egfr": ["part/LP-EGFR", "Measure/KED", "Threshold/eGFR_LT_30"],
    "blood pressure": ["Measure/BPD"], "systolic": ["Measure/BPD", "Threshold/systolic_lt_140"],
    "diastolic": ["Measure/BPD", "Threshold/diastolic_lt_90"],
}
MEASURE_CODES = {"gsd": "Measure/GSD", "ked": "Measure/KED", "bpd": "Measure/BPD",
                 "spd": "Measure/SPD", "eed": "Measure/EED"}


_UUID = r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"


def link_entities(question: str) -> tuple[set[str], set[str]]:
    """Resolve the question to (exact IRIs, icd-subtree prefixes). Patient ids in the question link to Patient nodes."""
    q = question.lower()
    exact: set[str] = set()
    prefixes: set[str] = set()
    for term, anchors in LEXICON.items():
        if term in q:
            for a in anchors:
                (prefixes if a.startswith("icd/") else exact).add(a)
    for code, iri in MEASURE_CODES.items():
        if re.search(rf"\b{code}\b", q):
            exact.add(iri)
    for m in re.findall(r"\b([A-TV-Z][0-9]{2}(?:\.[0-9]{1,3})?)\b", question):  # raw ICD-10 codes in the prompt
        prefixes.add("icd/" + m)
    for m in re.findall(_UUID, q):
        exact.add("Patient/" + m)
    return exact, prefixes


def _short(iri: str) -> str:
    return iri[len(ONTO_NS):] if iri and iri.startswith(ONTO_NS) else (iri or "").rsplit("/", 1)[-1]


# Instance-data predicates that explode (15M observations) or carry no structure -- never traversed.
_SKIP_PREDS = ["hasObservation", "ofTest", "resultValue", "type", "label"]
# Patient-level edges (ABox). From a linked patient we take all of them (1 hop); otherwise only a small sample.
_PATIENT_PREDS = ["hasDiagnosis", "prescribed", "eligibleFor", "hasCareGap", "ageAtPeriodEnd"]
MAX_HOPS = 3


def _iri_list(nodes) -> str:
    return ", ".join("'" + (n if n.startswith("http") else ONTO_NS + n).replace("'", "") + "'" for n in sorted(nodes))


_SCHEMA_CACHE: dict[str, str] = {}


def graph_schema(run_sql, graph: str) -> str:
    """The graph's predicate vocabulary (predicate: subject type -> object type, triple count), read from the graph
    itself. The graph's counterpart to the closure arm's table cards and the metric views' YAML; cached per graph."""
    if graph not in _SCHEMA_CACHE:
        rows = run_sql(
            f"SELECT regexp_extract(predicate, '([^/#]+)$', 1) AS p, regexp_extract(subject, 'ontology/([^/]+)/', 1) AS st, "
            f"coalesce(nullif(regexp_extract(object, 'ontology/([^/]+)/', 1), ''), 'literal') AS ot, count(*) AS n "
            f"FROM {graph} GROUP BY 1, 2, 3 ORDER BY 1, 4 DESC")
        lines = [f"{r['p']}: {r['st'] or '?'} -> {r['ot']} ({int(r['n']):,})" for r in rows
                 if r["p"] not in ("type", "label")]
        _SCHEMA_CACHE[graph] = "; ".join(lines)
    return _SCHEMA_CACHE[graph]


def graph_context(question: str, run_sql, graph: str) -> list[dict]:
    """k-hop subgraph around the question's linked entities (standard graph-RAG retrieval). `graph` =
    catalog.schema.<base>_graph.

    Seeds = entity-linked nodes (lexicon terms, ICD codes, patient ids). From a linked PATIENT we take its own
    record edges (diagnoses, prescriptions, measure eligibility/gaps). Then we expand up to MAX_HOPS over the
    terminology + guideline layer in BOTH directions (subClassOf, contains, hasIngredient, inDrugClass,
    recommendedFor, contraindicatedWith, ...), so a path such as patient -> drug -> class -> rule -> value set ->
    code <- patient's diagnosis is retrievable without knowing it in advance. Unlinked questions retrieve nothing.
    The first document names the triple table and IRI scheme (provenance) so the context is queryable."""
    exact, prefixes = link_entities(question)
    if not exact and not prefixes:
        return []
    skip = ", ".join(f"'{ONTO_NS}{p}'" for p in _SKIP_PREDS + _PATIENT_PREDS)
    pat_in = ", ".join(f"'{ONTO_NS}{p}'" for p in _PATIENT_PREDS)
    seen: dict[tuple, int] = {}
    tiers: dict[tuple, str] = {}

    def add(rows, hop, tier):
        for r in rows:
            k = (r["subject"], r["predicate"], r["object"])
            if k not in seen:
                seen[k] = hop
                tiers[k] = tier

    patients = {n for n in exact if n.startswith("Patient/")}
    frontier = {ONTO_NS + n for n in exact - patients}
    if patients:
        rows = run_sql(f"SELECT subject, predicate, object FROM {graph} WHERE subject IN ({_iri_list(patients)}) "
                       f"AND predicate IN ({pat_in}) LIMIT 80")
        add(rows, 1, "patient")
        frontier |= {r["object"] for r in rows if r["object"].startswith(ONTO_NS)}
    else:
        like = " OR ".join([f"object IN ({_iri_list(exact)})"] if exact else []
                           + [f"object LIKE '{ONTO_NS}{p}%'" for p in sorted(prefixes)])
        add(run_sql(f"SELECT subject, predicate, object FROM {graph} WHERE predicate IN ({pat_in}) AND ({like}) LIMIT 8"),
            1, "member")
    prefix_clause = " OR ".join(f"subject LIKE '{ONTO_NS}{p}%' OR object LIKE '{ONTO_NS}{p}%'" for p in sorted(prefixes))
    visited: set[str] = set()
    for hop in range(1, MAX_HOPS + 1):
        todo = frontier - visited
        if not todo and not (hop == 1 and prefix_clause):
            break
        conds = []
        if todo:
            lst = _iri_list(todo)
            conds.append(f"subject IN ({lst}) OR object IN ({lst})")
        if hop == 1 and prefix_clause:
            conds.append(prefix_clause)
        rows = run_sql(f"SELECT subject, predicate, object FROM {graph} WHERE predicate NOT IN ({skip}) "
                       f"AND predicate NOT RLIKE '[#/](type|label|valueSetId)$' AND ({' OR '.join(conds)}) LIMIT 120")
        visited |= todo
        add(rows, hop, "guideline")
        frontier |= {x for r in rows for x in (r["subject"], r["object"]) if x.startswith(ONTO_NS)}
    linked = sorted(exact | {p + "*" for p in prefixes})
    header = {"page_content": (f"Source: Ontobricks triple table {graph} (columns subject, predicate, object). "
                               f"Node IRIs are {ONTO_NS}<Type>/<id> (e.g. {ONTO_NS}Patient/<patient_id>, "
                               f"{ONTO_NS}icd/E11.9, {ONTO_NS}DrugClass/DRUGCLASS-STATIN); predicate IRIs are "
                               f"{ONTO_NS}<predicate>. Triples below are shown with that prefix removed.\n"
                               f"Graph schema (predicate: subject type -> object type, count): {graph_schema(run_sql, graph)}"),
              "metadata": {"source": "ontobricks", "kind": "provenance", "graph": graph, "linked_entities": linked}}
    order = sorted(seen, key=lambda k: (seen[k], tiers[k] != "patient"))
    return [header] + [
        {"page_content": f"({_short(k[0])}) -[{_short(k[1])}]-> ({_short(k[2])})  [{tiers[k]}, hop {seen[k]}]",
         "metadata": {"source": "ontobricks", "kind": "triple", "tier": tiers[k], "hop": seen[k], "graph": graph,
                      "subject": _short(k[0]), "predicate": _short(k[1]), "object": _short(k[2]),
                      "linked_entities": linked}}
        for k in order]


# ------------------------------------------------ Genie Ontology -----------------------------------------------
def genie_ontology_docs(rec: dict) -> list[dict]:
    """Documents from Genie Ontology's OWN retrieval for one question (recorded by scripts/record_genie_ontology.py
    from Genie One's knowledge-snippet search): inferred snippets, ranked Pages, and Page bodies Genie read.
    Genie One's answer, SQL and other tools are deliberately not included."""
    docs = []
    for x in rec.get("snippets") or []:
        docs.append({"page_content": f"Inferred snippet ({x.get('type')}) from {x.get('source')}: {x.get('headline')}\n"
                                     f"{x.get('content') or ''}",
                     "metadata": {"source": "genie_ontology", "kind": "snippet", **{k: x.get(k) for k in (
                         "headline", "type", "source", "relevance", "authority", "on_topic", "stale", "content")}}})
    read = {p.get("page_id"): p for p in rec.get("pages_read") or []}
    for p in rec.get("pages") or []:
        body = (read.get(p.get("id")) or {}).get("body")
        docs.append({"page_content": f"Ontology Page — {p.get('name')} [{p.get('domain')}]: {p.get('description') or ''}"
                                     + (f"\n{body}" if body else ""),
                     "metadata": {"source": "genie_ontology", "kind": "page", "page": p.get("name"),
                                  "domain": p.get("domain"), "relevance": p.get("relevance"),
                                  "certified": p.get("certified"), "on_topic": p.get("on_topic"),
                                  "description": p.get("description"), "body": body}})
    return docs


# --------------------------------------------------- closure ---------------------------------------------------
# Closure-table retrieval as parameterized TOOLS (docs/decisions.md ADR-0010 addendum 2026-11-06, after the
# "Closure-Table Retrieval on Databricks" review): direct edges (icd10_hier, rxnorm_hier) are the source of truth;
# the closures (icd10_closure, rxnorm_closure: ancestor, descendant, depth incl. a depth-0 self row) are derived.
# Request flow: resolve the question's concepts to nodes -> filter the closure (descendants / ancestors) -> join the
# content attached to those nodes (here: patients' recorded diagnoses and medication orders) -> agent context.
# One relationship only (is-a / contains). Protocol rules (contraindicatedWith, recommendedFor ...) are a different
# relationship and are deliberately NOT folded in -- that cross-relationship multi-hop is the graph's job.

_GENERIC = set("type 1 2 mellitus unspecified other specified with without of the and for to related conditions "
               "demo scd mg oral tablet hr extended release hydrochloride calcium potassium encounter supervision "
               "disorder care maternal".split())
_NORM = {"diabetic": "diabetes", "complications": "complication", "statins": "statin", "inhibitors": "inhibitor"}


def _toks(text: str) -> set[str]:
    out = set()
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        w = _NORM.get(w, w)
        if len(w) > 1 and not w.isdigit():
            out.add(w)
    return out


_NODES: dict[str, list[dict]] = {}


def _closure_nodes(run_sql, term: str) -> list[dict]:
    """knowledge_nodes = the two hierarchies' nodes (code, name, parent, which closure they live in)."""
    if term not in _NODES:
        rows = run_sql(f"SELECT code, parent_code, name, 'icd' AS h FROM {term}.icd10_hier UNION ALL "
                       f"SELECT code, parent_code, name, 'rx' AS h FROM {term}.rxnorm_hier")
        _NODES[term] = rows
    return _NODES[term]


def resolve_nodes(question: str, run_sql, term: str) -> list[dict]:
    """resolve_node: match the question to hierarchy nodes by NAME (every non-generic word of the node's name appears in
    the question) plus the alias table (LEXICON entries that point at a code or drug class). A candidate whose matched
    words are a strict subset of another candidate's is dropped (the question named the more specific concept); a
    candidate under another candidate with the same matched words is dropped too (keep the top of the subtree).
    Returns [{code, name, h, matched}], where `matched` groups synonyms: same words -> same concept -> OR."""
    q = _toks(question)
    nodes = {n["code"]: n for n in _closure_nodes(run_sql, term)}
    cands: dict[str, frozenset] = {}
    for n in nodes.values():
        c = _toks(n["name"]) - _GENERIC
        if c and c <= q:
            cands[n["code"]] = frozenset(c)
    ql = question.lower()
    for term_, anchors in LEXICON.items():
        if term_ in ql:
            for a in anchors:
                code = a.split("/", 1)[1]
                if (a.startswith("icd/") or a.startswith("DrugClass/")) and code in nodes and code not in cands:
                    cands[code] = frozenset(_toks(term_))
    keep = {k: v for k, v in cands.items() if not any(v < w for w in cands.values())}

    def ancestors(code):
        seen, p = [], nodes.get(code, {}).get("parent_code")
        while p and p not in seen:
            seen.append(p)
            p = nodes.get(p, {}).get("parent_code")
        return seen
    keep = {k: v for k, v in keep.items() if not any(a in keep and keep[a] == v for a in ancestors(k))}
    return [{"code": k, "name": nodes[k]["name"], "h": nodes[k]["h"], "matched": sorted(v)} for k, v in keep.items()]


def closure_context(question: str, run_sql, catalog: str, schema: str, term_schema: str) -> list[dict]:
    """Closure retrieval with four tools over the derived closures: resolve_nodes, get_ancestors, get_descendants and
    patients_under (the content join: patients with a recorded diagnosis / medication order anywhere in the subtree).
    Concepts matched by different words are ANDed (e.g. diabetes AND statin); synonyms matched by the same words are
    ORed (E10.2 OR E11.2). Nothing is retrieved when the question names no hierarchy node."""
    term = f"{catalog}.{term_schema}"
    anchors = resolve_nodes(question, run_sql, term)
    if not anchors:
        return []
    clos = {"icd": f"{term}.icd10_closure", "rx": f"{term}.rxnorm_closure"}
    facts = {"icd": (f"{catalog}.{schema}.bronze_pat_enc_dx", "icd10_code", "a recorded diagnosis"),
             "rx": (f"{catalog}.{schema}.bronze_order_med", "rxnorm_code", "a medication order")}
    q = lambda v: "'" + str(v).replace("'", "") + "'"  # noqa: E731
    docs = [{"page_content": ("Source: closure-table tools over " + ", ".join(sorted({clos[a['h']] for a in anchors}))
                              + " (ancestor_code, descendant_code, depth). Content joined from "
                              + ", ".join(sorted({facts[a['h']][0] for a in anchors})) + "."),
             "metadata": {"source": "closure", "kind": "provenance"}}]
    groups: dict[tuple, list[dict]] = {}
    for a in anchors:
        groups.setdefault((a["h"], tuple(a["matched"])), []).append(a)
    for a in anchors:
        anc = run_sql(f"SELECT ancestor_code, ancestor_name, depth FROM {clos[a['h']]} "
                      f"WHERE descendant_code = {q(a['code'])} AND depth > 0 ORDER BY depth DESC")
        desc = run_sql(f"SELECT descendant_code, descendant_name, depth FROM {clos[a['h']]} "
                       f"WHERE ancestor_code = {q(a['code'])} ORDER BY depth, descendant_code LIMIT 40")
        crumb = " > ".join([f"{r['ancestor_code']}" for r in anc] + [a["code"]])
        docs.append({"page_content": (f"resolve_node(\"{' '.join(a['matched'])}\") -> {a['code']} ({a['name']}). "
                                      f"Ancestors: {crumb}. Descendants ({len(desc)}, incl. itself): "
                                      + "; ".join(f"{r['descendant_code']} {r['descendant_name']} [depth {r['depth']}]"
                                                  for r in desc)),
                     "metadata": {"source": "closure", "kind": "subtree", "anchor": a["code"], "h": a["h"]}})
    counts = []
    subq = []
    for (h, words), grp in groups.items():
        tbl, col, what = facts[h]
        codes = ", ".join(q(a["code"]) for a in grp)
        sql = (f"SELECT DISTINCT f.patient_id FROM {tbl} f JOIN {clos[h]} c ON f.{col} = c.descendant_code "
               f"WHERE c.ancestor_code IN ({codes})")
        subq.append(sql)
        n = run_sql(f"SELECT COUNT(*) AS n FROM ({sql})")[0]["n"]
        label = " or ".join(f"{a['code']} ({a['name']})" for a in grp)
        counts.append(f"Patients with {what} under {label}: {int(n):,}")
    if len(subq) > 1:
        both = " INTERSECT ".join(f"({s})" for s in subq)
        n = run_sql(f"SELECT COUNT(*) AS n FROM ({both})")[0]["n"]
        counts.append(f"Patients matching ALL of the above concepts: {int(n):,}")
    docs.append({"page_content": "patients_under(...) -> " + " | ".join(counts),
                 "metadata": {"source": "closure", "kind": "content"}})
    return docs
