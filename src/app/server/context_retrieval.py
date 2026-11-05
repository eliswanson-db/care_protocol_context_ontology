"""Retrieval-as-context for the two "knowledge" arms, shared by the app's Retrieval Arena and the eval harness
(src/benchmark/retrieval_eval/providers.py), so the Arena shows exactly the context that gets scored.

Both functions take a question and a `run_sql(sql) -> list[dict]` callable and return MLflow-retriever-shaped
documents ({page_content, metadata}). Neither computes an answer: they return what each knowledge layer HOLDS
for the question, which a fixed agent then reasons over.

  genie_ontology_docs  Genie Ontology's OWN retrieval (recorded from Genie One's knowledge-snippet search):
                       inferred snippets + ranked Pages + Page bodies read. No Genie One answer or SQL.
  graph_context     Ontobricks: entity-link the question's clinical terms to graph nodes, return their typed
                    1-hop neighbourhood (cross-vocabulary guideline edges first, then a small sample of patient
                    membership edges) from the live triplestore.
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


def link_entities(question: str) -> tuple[set[str], set[str]]:
    """Resolve the question to (exact IRIs, icd-subtree prefixes)."""
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
    return exact, prefixes


def _short(iri: str) -> str:
    return iri[len(ONTO_NS):] if iri and iri.startswith(ONTO_NS) else (iri or "").rsplit("/", 1)[-1]


def graph_context(question: str, run_sql, graph: str) -> list[dict]:
    """Typed 1-hop neighbourhood of the question's linked entities. `graph` = catalog.schema.<base>_graph."""
    exact, prefixes = link_entities(question)
    if not exact and not prefixes:
        return []

    def _match(col: str) -> str:
        cl = []
        if exact:
            cl.append(f"{col} IN ({', '.join(chr(39) + ONTO_NS + n + chr(39) for n in sorted(exact))})")
        for p in sorted(prefixes):
            cl.append(f"{col} LIKE '{ONTO_NS}{p}%'")  # p is from the lexicon or a regex-validated ICD code
        return "(" + " OR ".join(cl) + ")"

    guideline_in = ", ".join(f"'{ONTO_NS}{p}'" for p in GUIDELINE_PREDS)
    member_in = ", ".join(f"'{ONTO_NS}{p}'" for p in MEMBER_PREDS)
    sql = (f"(SELECT subject, predicate, object, 'guideline' AS tier FROM {graph} "
           f"  WHERE predicate IN ({guideline_in}) AND ({_match('subject')} OR {_match('object')}) LIMIT 55) "
           f"UNION ALL "
           f"(SELECT subject, predicate, object, 'member' AS tier FROM {graph} "
           f"  WHERE predicate IN ({member_in}) AND {_match('object')} LIMIT 8)")
    rows = run_sql(sql)
    linked = sorted(exact | {p + "*" for p in prefixes})
    return [{"page_content": f"({_short(r['subject'])}) -[{_short(r['predicate'])}]-> ({_short(r['object'])})  [{r['tier']}]",
             "metadata": {"source": "ontobricks", "kind": "triple", "tier": r["tier"], "graph": graph,
                          "subject": _short(r["subject"]), "predicate": _short(r["predicate"]),
                          "object": _short(r["object"]), "linked_entities": linked}}
            for r in rows]


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
