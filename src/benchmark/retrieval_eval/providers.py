"""Context providers for the retrieval-science arm (ADR-0020, docs/BENCHMARK_CHARTER.md reframe).

Each provider IS one retrieval approach under test. Given a question it returns the context that approach
would surface -- and NOTHING else -- so the controlled supervisor (agent.py) answers *only* from it. This is
what makes the benchmark a retrieval eval rather than a reasoner leaderboard: we hold the front door fixed
and vary the injected context one component at a time, with closed_book as the floor.

    closed_book    no retrieval                          -> the parametric-knowledge floor (necessity baseline)
    metric_view    the governed metric-view DEFINITIONS (YAML) most relevant to the question
    closure_sql    closure tables as tools: resolve the concepts, walk the closure, join the patients under each subtree
    rag            Lakebase hybrid passages (A4)          -> unstructured text retrieval

Every provider that actually retrieves is wrapped as an MLflow RETRIEVER span so RetrievalGroundedness and the
custom sufficiency judge can read the documents back off the trace. Documents use MLflow's retriever shape
({page_content, metadata}). closed_book emits NO span (nothing was retrieved -- grounding is N/A by design).
"""
from __future__ import annotations

import json
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


# --- metric_view + closure_sql retrieve what their LAYER holds -- never a per-question answer query. -----------
# (Earlier versions ran a hand-picked MEASURE() per question and, for closure, the gold answer-key query itself;
# that measured the answer key, not retrieval.) The SAME entity linker as the graph arm drives closure lookups,
# so closure-vs-graph differs only in the store (relational closure/edge tables vs one triple graph).
import sys as _sys  # noqa: E402

_sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "app")))
from server.context_retrieval import (CLOSURE_TOOLS, closure_context, closure_tool, genie_ontology_docs,  # noqa: E402
                                      graph_context, link_entities)

_STOP = set("the a an of to in on for and or is are was what which how many much does do did with by from this "
            "that their its it as at be any each all whether under show give name own".split())


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in _STOP}


_MV_CACHE: dict[str, str] | None = None


def _metric_views() -> dict[str, str]:
    """{fqn: YAML definition} for every certified metric view in the semantic schema (live from UC)."""
    global _MV_CACHE
    if _MV_CACHE is None:
        names = [r["table_name"] for r in run_sql(
            f"SELECT table_name FROM {CATALOG}.information_schema.tables "
            f"WHERE table_schema = '{SCHEMA_SEMANTIC}' AND table_type = 'METRIC_VIEW' ORDER BY table_name")]
        _MV_CACHE = {}
        for n in names:
            fqn = f"{CATALOG}.{SCHEMA_SEMANTIC}.{n}"
            row = run_sql(f"DESCRIBE TABLE EXTENDED {fqn} AS JSON")
            meta = json.loads(list(row[0].values())[0]) if row else {}
            _MV_CACHE[fqn] = meta.get("view_text") or ""
    return _MV_CACHE


MV_TOP_K = 3


@mlflow.trace(span_type="RETRIEVER", name="metric_view")
def metric_view(question: str, qid: str) -> list[dict]:
    """The governed semantic layer: the definitions (YAML) of the K metric views most relevant to the question,
    ranked by term overlap with each view's names, comments and synonyms. Definitions only -- no query results."""
    qt = _tokens(question)
    scored = sorted(((len(qt & _tokens(y)), fqn) for fqn, y in _metric_views().items()), reverse=True)
    mvs = _metric_views()
    return [_doc(f"UC metric view {fqn} (query measures with MEASURE(`<measure name>`) FROM {fqn}):\n{mvs[fqn]}",
                 source="metric_view", view=fqn, score=sc)
            for sc, fqn in scored[:MV_TOP_K] if sc > 0]


def _q(v: str) -> str:
    return "'" + v.replace("'", "") + "'"


@mlflow.trace(span_type="RETRIEVER", name="closure_sql")
def closure_sql(question: str, qid: str) -> list[dict]:
    """Closure tables as parameterized tools (resolve_node -> ancestors / descendants -> patients under the subtree).
    See closure_context in src/app/server/context_retrieval.py. No free-form SQL, no per-question queries."""
    return closure_context(question, run_sql, CATALOG, SCHEMA, SCHEMA_TERM)


def _render(rows: list[dict], limit: int = 12) -> str:
    if not rows:
        return "(no rows)"
    cols = list(rows[0].keys())
    lines = [" | ".join(cols)] + [" | ".join(str(r.get(c)) for c in cols) for r in rows[:limit]]
    return "\n".join(lines) + (f"\n... (+{len(rows) - limit} more rows)" if len(rows) > limit else "")


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
ONTOBRICKS_CATALOG = os.environ.get("CARE_ONTOBRICKS_CATALOG", "eswanson_demo")
ONTOBRICKS_SCHEMA = os.environ.get("CARE_ONTOBRICKS_SCHEMA", "ontobricks")
ONTOBRICKS_TABLE = os.environ.get("CARE_ONTOBRICKS_TABLE")  # None -> the latest published clinicaldomain version
# Full name of the triple table/view to use instead (e.g. the live compiled-mapping view, to test a republish before it
# happens). Overrides CARE_ONTOBRICKS_TABLE.
ONTOBRICKS_GRAPH = os.environ.get("CARE_ONTOBRICKS_GRAPH")


def _graph_table() -> str:
    return ONTOBRICKS_GRAPH or f"{ONTOBRICKS_CATALOG}.{ONTOBRICKS_SCHEMA}.{_latest_ontobricks()}_graph"


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
    graph = _graph_table()
    try:
        return graph_context(question, run_sql, graph)
    except Exception as e:  # noqa: BLE001
        return [_doc(f"[Ontobricks query failed: {type(e).__name__}: {str(e)[:140]}]", source="ontobricks_error")]


_GO_REC = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "benchmark",
                                       "genie_ontology_retrieval.json"))


def _go_rec(workspace: str, qid: str) -> dict | None:
    if not os.path.isfile(_GO_REC):
        return None
    return json.load(open(_GO_REC))["workspaces"].get(workspace, {}).get("questions", {}).get(qid)


def genie_skipped(arm: str, qid: str) -> bool | None:
    """True if Genie One never ran its ontology search for this question (so 'retrieved nothing' is not a finding);
    None if there is no recording for the question at all."""
    ws = {"genie_ontology": "ect", "genie_ontology_dmvm": "dmvm"}.get(arm)
    if not ws:
        return False
    rec = _go_rec(ws, qid)
    return None if rec is None else bool(rec.get("skipped_search"))


def _genie_ontology(workspace: str, qid: str) -> list[dict]:
    """Genie Ontology's OWN retrieval for this question (recorded: snippet search + Pages read), no Genie One answer."""
    rec = _go_rec(workspace, qid)
    if rec is None:
        return []
    return genie_ontology_docs(rec)


@mlflow.trace(span_type="RETRIEVER", name="genie_ontology")
def genie_ontology(question: str, qid: str) -> list[dict]:
    return _genie_ontology("ect", qid)


@mlflow.trace(span_type="RETRIEVER", name="genie_ontology_dmvm")
def genie_ontology_dmvm(question: str, qid: str) -> list[dict]:
    return _genie_ontology("dmvm", qid)


# The arms, in display order. closed_book first = the floor every other arm's lift is measured against.
PROVIDERS = {
    "closed_book": None,  # sentinel: no retrieval, handled in the runner
    "metric_view": metric_view,
    "closure_sql": closure_sql,
    "rag": rag,
    "genie_ontology": genie_ontology,
    "genie_ontology_dmvm": genie_ontology_dmvm,
    "ontobricks": ontobricks,
}


def warm() -> None:
    """Populate the per-run metadata caches (metric-view definitions, terminology table cards) before parallel use."""
    _metric_views()
    graph_runner()


# ---- what each approach retrieved, in one line (shown on every card) --------------------------------------------
def summarize(arm: str, docs: list[dict]) -> str:
    from collections import Counter
    if not docs:
        return "Retrieved nothing."
    m = [d.get("metadata", {}) for d in docs]
    if arm == "metric_view":
        return "Definitions of " + ", ".join(x.get("view", "").split(".")[-1] for x in m) + "."
    if arm == "closure_sql":
        anchors = [x["anchor"] for x in m if x.get("kind") == "subtree"]
        content = next((d["page_content"].replace("patients_under(...) -> ", "") for d, x in zip(docs, m)
                        if x.get("kind") == "content"), "")
        return f"Resolved {', '.join(anchors)}; walked their subtrees; {content}"[:300]
    if arm.startswith("genie_ontology"):
        sn = [x for x in m if x.get("kind") == "snippet"]
        pg = [x.get("page") for x in m if x.get("kind") == "page"]
        on = sum(1 for x in sn if x.get("on_topic"))
        return (f"{len(sn)} inferred snippets ({on} about this demo); {len(pg)} Pages"
                + (f": {', '.join(p for p in pg if p)}" if pg else "") + ".")
    if arm == "rag":
        titles = [x.get("title") for x in m if x.get("title")]
        return f"{len(docs)} passages from: " + ", ".join(dict.fromkeys(titles)) + "."
    if arm == "ontobricks":
        head = next((x for x in m if x.get("kind") == "provenance"), {})
        preds = Counter(x.get("predicate") for x in m if x.get("kind") == "triple")
        top = ", ".join(f"{p} {n}" for p, n in preds.most_common(5))
        linked = ", ".join(head.get("linked_entities", [])[:6])
        return f"Linked {linked or 'nothing'}; {sum(preds.values())} triples ({top})."
    return f"{len(docs)} documents."


_GRAPH = None


def graph_runner():
    """The published graph loaded in memory for one-shot traversal calls (cached per run)."""
    global _GRAPH
    if _GRAPH is None:
        from server import graph_runner as gr
        from .warehouse import fetch_all
        _GRAPH = gr.load(_graph_table(), fetch_all)
    return _GRAPH
