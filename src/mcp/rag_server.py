"""Care Protocol RAG MCP server (A4) — exposes Lakebase hybrid document retrieval as an MCP tool.

Why this exists (ADR-0020): delivering RAG to Genie One AS AN MCP TOOL means every time Genie One retrieves a
care-protocol passage it is logged in `system.access.audit` as `genieChat.mcpToolInvocation` (tool_name +
mcp_server_name + conversation_id) — durable, system-table-backed ATTRIBUTION of "did Genie use RAG for this
answer." Native built-ins (search_knowledge_snippets, native SQL) are NOT audited that way; MCP tools are. The
same tool backs the controlled-supervisor eval's `rag` arm (benchmark/retrieval_eval/providers.py), so the
product arm (Genie One) and the science arm (controlled supervisor) call identical retrieval.

A thin FastMCP wrapper around A4RagRetriever (src/retrieval/a4_lakebase.py). Returns real passages with
document/section/page provenance and document-level RLS enforced in-database. Deploy as a Databricks App and
register as a Genie One MCP tool; locally, `python src/mcp/rag_server.py` runs it over stdio.

Env: CARE_LAKEBASE_ENDPOINT (logical path), CARE_LAKEBASE_USER (optional; default = caller identity),
     CARE_RAG_AS_USER (optional OBO stand-in for the RLS test), CARE_LAKEBASE_SEARCH_EXT (1=Lakebase Search).
"""
import os
import sys

from databricks.sdk import WorkspaceClient
from mcp.server.fastmcp import FastMCP

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "retrieval"))
from a4_lakebase import A4RagRetriever  # noqa: E402  (vendored on deploy)

_ENDPOINT = os.environ.get("CARE_LAKEBASE_ENDPOINT",
                           "projects/care-protocol/branches/production/endpoints/primary")
_SEARCH_EXT = os.environ.get("CARE_LAKEBASE_SEARCH_EXT", "1") == "1"
_AS_USER = os.environ.get("CARE_RAG_AS_USER") or None

_w = WorkspaceClient()
_retriever: A4RagRetriever | None = None


def _get() -> A4RagRetriever:
    global _retriever
    if _retriever is None:
        host = _w.postgres.get_endpoint(_ENDPOINT).status.hosts.host
        user = os.environ.get("CARE_LAKEBASE_USER") or _w.current_user.me().user_name
        _retriever = A4RagRetriever(endpoint=_ENDPOINT, host=host, user=user, search_ext=_SEARCH_EXT)
    return _retriever


mcp = FastMCP("care-protocol-rag")


@mcp.tool()
def search_care_protocol(query: str, k: int = 5) -> dict:
    """Retrieve care-protocol passages relevant to a clinical question via Lakebase hybrid (BM25 + vector)
    retrieval over the governed document corpus. Returns passages with document/section/page citation and
    document-level RLS enforced. Use for definitions, thresholds, eligibility rules, and contraindications
    that live in the care-protocol text rather than in the structured measures."""
    hits = _get().search_documents(query, k=k, as_user=_AS_USER)
    passages = [
        {
            "title": h.get("title"),
            "section": h.get("section_path"),
            "page": h.get("page_start"),
            "measurement_year": h.get("measurement_year"),
            "content": h.get("content"),
            "score": float(h["score"]) if h.get("score") is not None else None,
        }
        for h in hits
    ]
    return {"query": query, "k": k, "passages": passages, "count": len(passages)}


if __name__ == "__main__":
    mcp.run()
