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
        "GSD Compliance Rate (MY2026, year-to-date)",
        f"SELECT ROUND(MEASURE(`GSD Compliance Rate`), 4) AS gsd_compliance_rate, MEASURE(`Eligible Patients`) AS "
        f"eligible, MEASURE(`Compliant Patients`) AS compliant "
        f"FROM {CATALOG}.{SCHEMA_SEMANTIC}.gsd_compliance_metrics WHERE `Measurement Year` = 2026",
    ),
    "kpi_ked_eligible": (
        "KED Eligible Patients",
        f"SELECT MEASURE(`Eligible Patients`) AS ked_eligible "
        f"FROM {CATALOG}.{SCHEMA_SEMANTIC}.ked_compliance_metrics",
    ),
    # Protocol Step-3 adherence by clinic (closed 90-day windows), lowest first.
    "op_worst_clinic_annual": (
        "Protocol Step-3 adherence by clinic, MY2026 year-to-date (closed windows), lowest first",
        f"SELECT `Clinic` AS clinic, ROUND(MEASURE(`Protocol Step 3 Adherence Rate`), 3) AS step3_adherence_rate, "
        f"MEASURE(`Trigger Events`) AS closed_obligations "
        f"FROM {CATALOG}.{SCHEMA_SEMANTIC}.protocol_adherence_metrics GROUP BY ALL ORDER BY 2",
    ),
    # Window measures: grouping by Clinic alone returns each clinic's LATEST trailing-3-month window (semiadditive last).
    "op_clinic_drift": (
        "Protocol Step-3 drift by clinic: latest trailing-3-month adherence vs the clinic's own baseline",
        f"SELECT `Clinic` AS clinic, ROUND(MEASURE(`Adherence (trailing 3mo)`), 3) AS trailing_3mo, "
        f"ROUND(MEASURE(`Adherence (baseline)`), 3) AS own_baseline, "
        f"ROUND(MEASURE(`Drift (trailing vs baseline)`), 3) AS drift "
        f"FROM {CATALOG}.{SCHEMA_SEMANTIC}.protocol_drift_metrics GROUP BY ALL ORDER BY 4",
    ),
}


def _render(rows: list[dict], limit: int = 12) -> str:
    if not rows:
        return "(no rows)"
    cols = list(rows[0].keys())
    lines = [" | ".join(cols)] + [" | ".join(str(r.get(c)) for c in cols) for r in rows[:limit]]
    return "\n".join(lines) + (f"\n... (+{len(rows) - limit} more rows)" if len(rows) > limit else "")


@mlflow.trace(span_type="RETRIEVER", name="metric_view")
def metric_view(question: str, qid: str) -> list[dict]:
    entry = _METRIC_SQL.get(qid)
    if not entry:
        return []  # no certified metric view covers this question -> the arm is structurally insufficient
    label, sql = entry
    rows = run_sql(sql)
    if not rows:
        return []
    return [_doc(f"Governed metric view result — {label}:\n{_render(rows)}", source="metric_view",
                 measure=label, sql=sql[:300])]


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
    return [_doc(f"Result of a fixed-shape governed SQL query (closure / edge / gold tables):\n{_render(rows)}",
                 source="closure_sql", sql=sql[:300])]


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


# --- ontobricks + genie_ontology: the two "knowledge" arms. The retrieval logic lives in ONE place --------------
# (src/app/server/context_retrieval.py) and is shared with the app's Retrieval Arena, so the Arena shows exactly
# the context scored here. Ontobricks is Eli-owned (ADR-0005); this is only retrieval plumbing.
#   ontobricks      entity-linked typed 1-hop subgraph from the live triplestore (latest published version).
#   genie_ontology  Genie Ontology's MODELED layer: Genie Pages (synonym/keyword match) + certified metric views.
#                   Genie's own snippet search is semantic and its payload isn't exposed by the API, so this is a
#                   transparent stand-in over the same content; inferred snippets are not included.
import sys as _sys  # noqa: E402

_sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "app")))
from server.context_retrieval import graph_context, ontology_context  # noqa: E402

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


@mlflow.trace(span_type="RETRIEVER", name="ontobricks")
def ontobricks(question: str, qid: str) -> list[dict]:
    graph = f"{ONTOBRICKS_CATALOG}.{ONTOBRICKS_SCHEMA}.{_latest_ontobricks()}_graph"
    try:
        return graph_context(question, run_sql, graph)
    except Exception as e:  # noqa: BLE001
        return [_doc(f"[Ontobricks query failed: {type(e).__name__}: {str(e)[:140]}]", source="ontobricks_error")]


@mlflow.trace(span_type="RETRIEVER", name="genie_ontology")
def genie_ontology(question: str, qid: str) -> list[dict]:
    try:
        return ontology_context(question, run_sql, CATALOG, SCHEMA, SCHEMA_SEMANTIC)
    except Exception as e:  # noqa: BLE001
        return [_doc(f"[Genie Ontology retrieval failed: {type(e).__name__}: {str(e)[:140]}]",
                     source="genie_ontology_error")]


# The arms, in display order. closed_book first = the floor every other arm's lift is measured against.
PROVIDERS = {
    "closed_book": None,  # sentinel: no retrieval, handled in the runner
    "metric_view": metric_view,
    "closure_sql": closure_sql,
    "rag": rag,
    "genie_ontology": genie_ontology,
    "ontobricks": ontobricks,
}
