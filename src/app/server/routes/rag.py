"""The A4 RAG hop, live. Retrieves the care-protocol passages that DEFINE the rule behind the patient's
status — e.g. what HbA1c evidence the GSD numerator accepts — from the Lakebase document corpus (rag.chunks),
with document-level RLS enforced in-database (ADR-0014). Returns real passages with citation provenance
(document / section / page), never a bare score.

Reuses src/retrieval/a4_lakebase.py (A4RagRetriever). Embeddings are not yet populated (RUNBOOK), so this
runs lexical/BM25 and reports semantic_pending=True; once rag.chunks.embedding is backfilled it auto-upgrades
to hybrid (RRF of BM25 + pgvector) with no code change.
"""
import os
import time

from fastapi import APIRouter, HTTPException

from ..config import (
    LAKEBASE_ENDPOINT,
    LAKEBASE_HOST,
    LAKEBASE_SEARCH_EXT,
    LAKEBASE_USER,
    ARM,
    get_profile,
)

router = APIRouter()

# Doc-level RLS denies unknown identities, so the deployed app SP sees nothing unless it SET ROLEs to a seeded
# reader. CARE_RAG_AS_USER names that seeded identity (OBO stand-in) when set; unset = connect as self (local dev).
_AS_USER = os.environ.get("CARE_RAG_AS_USER") or None

_RAG_QUESTION = (
    "What HbA1c or glycemic evidence satisfies the GSD (Glycemic Status Assessment) numerator for an adult "
    "diabetes patient, and what HbA1c monitoring cadence does the care protocol require?"
)

_embed_count: int | None = None  # process cache: how many chunks are embedded (decides lexical vs hybrid)


def _retriever():
    from ..a4_lakebase import A4RagRetriever  # vendored copy (deploy-safe; src/ isn't synced with the app)

    return A4RagRetriever(
        endpoint=LAKEBASE_ENDPOINT, host=LAKEBASE_HOST, user=LAKEBASE_USER,
        profile=get_profile(), search_ext=LAKEBASE_SEARCH_EXT,
    )


@router.get("/patient/{patient_id}/rag")
def rag(patient_id: str):
    global _embed_count
    try:
        r = _retriever()
        if _embed_count is None:
            rows = r._run("SELECT count(embedding) AS n FROM rag.chunks", (), _AS_USER)
            _embed_count = int(rows[0]["n"]) if rows else 0
        mode = "hybrid" if _embed_count > 0 else "lexical"
        t0 = time.time()
        results = r.search_documents(_RAG_QUESTION, k=5, mode=mode, as_user=_AS_USER)
        latency = round(time.time() - t0, 1)
    except Exception as e:  # noqa: BLE001 — surface the real failure to the UI
        hint = " (doc-level RLS denies unknown identities — set CARE_RAG_AS_USER to a seeded reader)" \
            if "permission" in str(e).lower() or "denied" in str(e).lower() else ""
        raise HTTPException(502, f"Lakebase RAG error: {type(e).__name__}: {str(e)[:260]}{hint}")

    passages = [
        {
            "document_id": str(x.get("document_id")),
            "title": x.get("title"),
            "section_path": x.get("section_path"),
            "page_start": x.get("page_start"),
            "source": x.get("source"),
            "measurement_year": x.get("measurement_year"),
            "content": x.get("content"),
            "score": float(x["score"]) if x.get("score") is not None else None,
        }
        for x in results
    ]
    return {
        "patient_id": patient_id,
        "question": _RAG_QUESTION,
        "mode": mode,
        "semantic_pending": _embed_count == 0,
        "search_ext": LAKEBASE_SEARCH_EXT,
        "embedded_chunks": _embed_count,
        "ran_as": f"the app's Databricks identity against the {ARM} Lakebase project (document-level RLS enforced)",
        "results": passages,
        "latency_s": latency,
    }
