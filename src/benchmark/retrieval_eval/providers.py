"""Context providers for the retrieval-science arm (ADR-0020, docs/BENCHMARK_CHARTER.md reframe).

Each provider IS one retrieval approach under test. Given a question it returns the context that approach
would surface -- and NOTHING else -- so the controlled supervisor (agent.py) answers *only* from it. This is
what makes the benchmark a retrieval eval rather than a reasoner leaderboard: we hold the front door fixed
and vary the injected context one component at a time, with closed_book as the floor.

    closed_book    no retrieval                          -> the parametric-knowledge floor (necessity baseline)
    metric_view    governed MEASURE() over a metric view -> build-time semantic resolution
    closure_sql    fixed-shape SQL over closure/edge tbls -> query-time semantic resolution (reuses gold_queries.sql)
    rag            Lakebase hybrid passages (A4)          -> unstructured text retrieval

Every provider that actually retrieves is wrapped as an MLflow RETRIEVER span so RetrievalGroundedness and the
custom sufficiency judge can read the documents back off the trace. Documents use MLflow's retriever shape
({page_content, metadata}). closed_book emits NO span (nothing was retrieved -- grounding is N/A by design).
"""
from __future__ import annotations

import os
import re

import mlflow

from .warehouse import run_sql

CATALOG = os.environ.get("CARE_CATALOG", "eli_test_classic_catalog")
SCHEMA = os.environ.get("CARE_SCHEMA", "care_protocol")
SCHEMA_SEMANTIC = os.environ.get("CARE_SCHEMA_SEMANTIC", "care_protocol_semantic")
SCHEMA_TERM = os.environ.get("CARE_SCHEMA_TERM", "care_protocol_terminology")
_GOLD_SQL = os.path.join(os.path.dirname(__file__), "..", "gold_queries.sql")


def _doc(content: str, **meta) -> dict:
    """An MLflow retriever document: page_content is what the judges read; metadata is provenance."""
    return {"page_content": content, "metadata": meta}


# --- metric_view: a governed MEASURE() answers KPIs directly; nothing else. Registry is deliberately small --
# so the arm visibly SUCCEEDS on the KPI and returns no context (insufficient) on discovery/definition classes.
# (label, SQL) per question. The label makes the retrieved context self-describing so a grounded answer
# doesn't have to INFER what the number is (an un-labelled bare value reads as ungrounded, correctly).
_METRIC_SQL = {
    "kpi_gsd_rate": (
        "GSD Compliance Rate",
        f"SELECT ROUND(MEASURE(`GSD Compliance Rate`), 4) AS v "
        f"FROM {CATALOG}.{SCHEMA_SEMANTIC}.gsd_compliance_metrics",
    ),
    "kpi_ked_eligible": (
        "KED Eligible Patients",
        f"SELECT MEASURE(`Eligible Patients`) AS v "
        f"FROM {CATALOG}.{SCHEMA_SEMANTIC}.ked_compliance_metrics",
    ),
}


@mlflow.trace(span_type="RETRIEVER", name="metric_view")
def metric_view(question: str, qid: str) -> list[dict]:
    entry = _METRIC_SQL.get(qid)
    if not entry:
        return []  # no covering metric view -> the arm is structurally insufficient for this question
    label, sql = entry
    rows = run_sql(sql)
    if not rows:
        return []
    val = list(rows[0].values())[0]
    return [_doc(f"Governed metric view — {label} = {val}", source="metric_view", measure=label, sql=sql[:200])]


# --- closure_sql: reuse the hand-verified gold_queries.sql blocks (the closure/edge-table resolution arm) ----
def _load_gold_sql() -> dict[str, str]:
    """{id: sql} from gold_queries.sql, substituting catalog/schema placeholders (mirrors verify_gold.py)."""
    raw = open(os.path.normpath(_GOLD_SQL)).read()
    out = {}
    for chunk in re.split(r"(?m)^-- @id:\s*", raw)[1:]:
        lines = chunk.splitlines()
        qid = lines[0].strip()
        sql = "\n".join(ln for ln in lines[1:] if not ln.lstrip().startswith("--")).strip()
        if sql:
            out[qid] = sql.format(catalog=CATALOG, schema=SCHEMA, tschema=SCHEMA_TERM)
    return out


_GOLD = _load_gold_sql()


@mlflow.trace(span_type="RETRIEVER", name="closure_sql")
def closure_sql(question: str, qid: str) -> list[dict]:
    sql = _GOLD.get(qid)
    if not sql:
        return []  # class 7/8 (definition / graph) have no scalar closure query -> arm insufficient here
    rows = run_sql(sql)
    if not rows:
        return []
    r0 = rows[0]
    rendered = ", ".join(f"{k} = {v}" for k, v in r0.items())
    return [_doc(f"Result of a governed query over the closure/edge tables: {rendered}",
                 source="closure_sql", sql=sql[:200])]


# --- rag: A4 Lakebase hybrid retrieval over the care-protocol corpus (best-effort from local) ----------------
_rag_retriever = None
_rag_error: str | None = None


def _get_rag():
    global _rag_retriever, _rag_error
    if _rag_retriever is not None or _rag_error is not None:
        return _rag_retriever
    try:
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "retrieval"))
        from a4_lakebase import A4RagRetriever  # type: ignore
        from databricks.sdk import WorkspaceClient
        profile = os.environ.get("DATABRICKS_CONFIG_PROFILE") or os.environ.get("DATABRICKS_PROFILE")
        w = WorkspaceClient(profile=profile) if profile else WorkspaceClient()
        ep = os.environ.get("CARE_LAKEBASE_ENDPOINT",
                            "projects/care-protocol/branches/production/endpoints/primary")
        host = w.postgres.get_endpoint(ep).status.hosts.host
        user = os.environ.get("CARE_LAKEBASE_USER") or w.current_user.me().user_name
        # Postgres full-text fallback (search_ext=False) is the robust path when Lakebase Search isn't enabled.
        _rag_retriever = A4RagRetriever(endpoint=ep, host=host, user=user, profile=profile, search_ext=False)
    except Exception as e:  # noqa: BLE001 -- RAG is best-effort locally; surface, don't crash the run
        _rag_error = f"{type(e).__name__}: {str(e)[:160]}"
    return _rag_retriever


@mlflow.trace(span_type="RETRIEVER", name="rag")
def rag(question: str, qid: str) -> list[dict]:
    r = _get_rag()
    if r is None:
        return [_doc(f"[RAG retrieval unavailable in this environment: {_rag_error}]", source="rag_error")]
    as_user = os.environ.get("CARE_RAG_AS_USER") or None
    try:
        hits = r.search_documents(question, k=5, mode="lexical", as_user=as_user)
    except Exception as e:  # noqa: BLE001
        return [_doc(f"[RAG query failed: {type(e).__name__}: {str(e)[:160]}]", source="rag_error")]
    docs = []
    for h in hits:
        content = h.get("content") or ""
        docs.append(_doc(content, source="rag", title=h.get("title"),
                         section=h.get("section_path"), page=h.get("page_start")))
    return docs


# --- ontobricks: A5 graph arm. Eli owns the modeling (ADR-0005); this is only the retrieval PLUMBING. --------
# Reads the published Ontobricks triplestore's subject/predicate/object tables directly:
#   <base>_graph    = asserted triples (the TBox + ABox Eli published)
#   <base>_inferred = entailed triples (OWL-reasoner output -- the graph-native payload a closure join can't make)
# The real arm IS published and live: `eswanson_demo.ontobricks.triplestore_clinicaldomain_v2_graph`
# (~55M asserted triples; v2_inferred has the reasoner output). The app queries it via routes/ontobricks.py;
# this provider binds to the same table for the eval harness so the scored benchmark is 1:1 with the app.
#
# RETRIEVAL STRATEGY -- entity-linked subgraph (mirrors routes/ontobricks.py), NOT a blind term-LIKE dump:
#   1. ENTITY-LINK the question's clinical terms to IRI *nodes* via `_LEXICON` (a synonym->node map -- the
#      standard graph-RAG NER/EL layer; it points at ENTITIES, never at answer edges, so retrieval returns
#      whatever edges those nodes actually have).
#   2. Return their typed 1-hop NEIGHBOURHOOD: first the small cross-vocabulary guideline/structural TBox
#      (recommendedFor / inDrugClass / contraindicated* / monitoredBy / hasThreshold / subClassOf / ...) -- the
#      graph's genuine lift -- then a small SAMPLE of patient membership edges (hasDiagnosis / eligibleFor / ...).
# Consequence, by design and honestly: the graph surfaces a typed PATH or a cross-vocab DEFINITION (its lift),
# but a triple neighbourhood does NOT aggregate, so it legitimately fails to produce a cohort COUNT (that is
# closure_sql's job). The eval scores that distinction instead of asserting "graph reaches everywhere".
ONTOBRICKS_CATALOG = os.environ.get("CARE_ONTOBRICKS_CATALOG", "eswanson_demo")
ONTOBRICKS_SCHEMA = os.environ.get("CARE_ONTOBRICKS_SCHEMA", "ontobricks")
ONTOBRICKS_TABLE = os.environ.get("CARE_ONTOBRICKS_TABLE")  # None -> the latest published clinicaldomain version


def _latest_ontobricks() -> str:
    if ONTOBRICKS_TABLE:
        return ONTOBRICKS_TABLE
    rows = run_sql(f"SELECT table_name FROM {ONTOBRICKS_CATALOG}.information_schema.tables "
                   f"WHERE table_schema = '{ONTOBRICKS_SCHEMA}'")
    found = sorted((int(m.group(1)), m.group(0)[:-len("_graph")]) for r in rows
                   if (m := re.match(r"^triplestore_clinicaldomain_v(\d+)_graph$", r["table_name"])))
    return found[-1][1] if found else "triplestore_clinicaldomain_v2"
_ONS = "https://care-protocol.example/ontology/"

# The cross-vocabulary guideline + structural predicates -- the graph's lift over a closure join.
_GUIDELINE_PREDS = ["recommendedFor", "inDrugClass", "contraindicatedWith", "contraindicatedWhen",
                    "monitoredBy", "hasThreshold", "firstLineFor", "definedBy", "subClassOf"]
# Patient-level ABox predicates -- sampled (not exhaustively dumped) so the agent sees membership exists.
_MEMBER_PREDS = ["hasDiagnosis", "eligibleFor", "prescribed", "hasCareGap"]

# Synonym -> IRI-node anchors (local names). Entity-linking only: every value is a NODE in the graph, verified
# against the live clinicaldomain_v2 TBox -- never a question-specific answer edge.
_LEXICON: dict[str, list[str]] = {
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
_MEASURE_CODES = {"gsd": "Measure/GSD", "ked": "Measure/KED", "bpd": "Measure/BPD",
                  "spd": "Measure/SPD", "eed": "Measure/EED"}


def _link_entities(question: str) -> tuple[set[str], set[str]]:
    """Resolve the question to (exact IRIs, icd-subtree prefixes). ICD anchors expand down the hierarchy by
    local-name prefix (E11 -> E11.21 etc.), which is exactly the subsumption the graph's subClassOf encodes."""
    q = question.lower()
    exact: set[str] = set()
    prefixes: set[str] = set()
    for term, anchors in _LEXICON.items():
        if term in q:
            for a in anchors:
                (prefixes if a.startswith("icd/") else exact).add(a)
    for code, iri in _MEASURE_CODES.items():  # bare measure codes (word-boundary)
        if re.search(rf"\b{code}\b", q):
            exact.add(iri)
    for m in re.findall(r"\b([A-TV-Z][0-9]{2}(?:\.[0-9]{1,3})?)\b", question):  # raw ICD-10 codes in the prompt
        prefixes.add("icd/" + m)
    return exact, prefixes


def _ns(names) -> str:
    return ", ".join(f"'{_ONS}{n}'" for n in sorted(names))


@mlflow.trace(span_type="RETRIEVER", name="ontobricks")
def ontobricks(question: str, qid: str) -> list[dict]:
    exact, prefixes = _link_entities(question)
    if not exact and not prefixes:
        return []  # nothing in the question linked to a graph entity -> arm has nothing to retrieve
    g, s, base = ONTOBRICKS_CATALOG, ONTOBRICKS_SCHEMA, _latest_ontobricks()
    graph = f"{g}.{s}.{base}_graph"

    def _match(col: str) -> str:
        cl = []
        if exact:
            cl.append(f"{col} IN ({_ns(exact)})")
        for p in sorted(prefixes):
            cl.append(f"{col} LIKE '{_ONS}{p}%'")  # p is from the lexicon or a regex-validated ICD code
        return "(" + " OR ".join(cl) + ")"

    guideline_in = ", ".join(f"'{_ONS}{p}'" for p in _GUIDELINE_PREDS)
    member_in = ", ".join(f"'{_ONS}{p}'" for p in _MEMBER_PREDS)
    # Tier 1: the cross-vocab guideline/structural neighbourhood of the linked entities (the graph's lift).
    # Tier 2: a small sample of patient membership edges pointing at those entities (shows members, not a count).
    sql = (
        f"(SELECT subject, predicate, object, 'guideline' AS tier FROM {graph} "
        f"  WHERE predicate IN ({guideline_in}) AND ({_match('subject')} OR {_match('object')}) LIMIT 55) "
        f"UNION ALL "
        f"(SELECT subject, predicate, object, 'member' AS tier FROM {graph} "
        f"  WHERE predicate IN ({member_in}) AND {_match('object')} LIMIT 8)")
    try:
        rows = run_sql(sql)
    except Exception as e:  # noqa: BLE001
        return [_doc(f"[Ontobricks query failed: {type(e).__name__}: {str(e)[:140]}]", source="ontobricks_error")]
    if not rows:
        return []

    def _short(iri: str) -> str:
        return iri[len(_ONS):] if iri and iri.startswith(_ONS) else (iri or "").rsplit("/", 1)[-1]

    # One doc = one triple so the judges can cite specific edges; the triple is pre-shortened for readability.
    return [_doc(f"({_short(r['subject'])}) -[{_short(r['predicate'])}]-> ({_short(r['object'])})  [{r['tier']}]",
                 source="ontobricks", tier=r["tier"], triplestore=base) for r in rows]


# The arms, in display order. closed_book first = the floor every other arm's lift is measured against.
PROVIDERS = {
    "closed_book": None,  # sentinel: no retrieval, handled in the runner
    "metric_view": metric_view,
    "closure_sql": closure_sql,
    "rag": rag,
    "ontobricks": ontobricks,
}
