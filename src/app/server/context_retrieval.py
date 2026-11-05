"""Retrieval-as-context for the two "knowledge" arms, shared by the app's Retrieval Arena and the eval harness
(src/benchmark/retrieval_eval/providers.py), so the Arena shows exactly the context that gets scored.

Both functions take a question and a `run_sql(sql) -> list[dict]` callable and return MLflow-retriever-shaped
documents ({page_content, metadata}). Neither computes an answer: they return what each knowledge layer HOLDS
for the question, which a fixed agent then reasons over.

  genie_ontology_docs  Genie Ontology's OWN retrieval (recorded from Genie One's knowledge-snippet search):
                       inferred snippets + ranked Pages + Page bodies read. No Genie One answer or SQL.
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
                               f"{ONTO_NS}<predicate>. Triples below are shown with that prefix removed."),
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
