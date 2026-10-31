"""Negative-security tests for A4 RAG document-level RLS (design doc §13; the +perm tracer, roadmap §7).

Requires a LIVE Lakebase `care-protocol` project with:
  1. src/retrieval/lakebase/schema.sql applied,
  2. scripts/lakebase_rag_corpus.py --emit_demo_roles loaded (seeds group_membership + demo identity roles),
  3. embeddings loaded (optional; lexical/BM25 tests run without them).

Configure via env, then run `python3 -I tests/test_rag_rls.py` (skips cleanly if LAKEBASE_HOST unset):
    export LAKEBASE_HOST=ep-....database.us-east-1.cloud.databricks.com
    export LAKEBASE_USER="you@databricks.com"       # the connecting (loader) identity
    export DATABRICKS_CONFIG_PROFILE=ECT

The policy keys on current_user, so we SET ROLE to the seeded identities to simulate OBO identities:
  * analyst@example.org   -> group quality_analytics (population docs only)
  * clinician@example.org -> groups quality_analytics + care_team (also patient-specific records)
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "src/retrieval"))

HOST = os.environ.get("LAKEBASE_HOST")
USER = os.environ.get("LAKEBASE_USER")
PROFILE = os.environ.get("DATABRICKS_CONFIG_PROFILE")
EP = "projects/care-protocol/branches/production/endpoints/primary"
RESTRICTED_DOC = "LETTER-EYE-TRC-0003"        # the care-team-only patient eye-exam letter
EYE_QUERY = "dilated retinal examination for patient TRC-0003"
PROTOCOL_QUERY = "below what eGFR is metformin contraindicated"


def _retriever():
    from a4_lakebase import A4RagRetriever
    # search_ext=False keeps the test runnable on the pgvector/full-text fallback too.
    return A4RagRetriever(endpoint=EP, host=HOST, user=USER, profile=PROFILE, search_ext=False)


def _doc_ids(rows):
    return {r["document_id"] for r in rows}


def test_analyst_cannot_see_patient_letter():
    r = _retriever()
    rows = r.search_documents(EYE_QUERY, k=10, mode="lexical", as_user="analyst@example.org")
    assert RESTRICTED_DOC not in _doc_ids(rows), "SECURITY FAIL: analyst retrieved the restricted patient letter"


def test_clinician_can_see_patient_letter():
    r = _retriever()
    rows = r.search_documents(EYE_QUERY, k=10, mode="lexical", as_user="clinician@example.org")
    assert RESTRICTED_DOC in _doc_ids(rows), "care-team clinician should retrieve the patient letter"


def test_both_identities_see_population_protocol():
    r = _retriever()
    for ident in ("analyst@example.org", "clinician@example.org"):
        rows = r.search_documents(PROTOCOL_QUERY, k=10, mode="lexical", as_user=ident)
        assert rows, f"{ident} got no population protocol results"
        assert RESTRICTED_DOC not in _doc_ids(rows), f"{ident}: protocol query leaked the patient letter"


def test_rls_holds_even_without_acl_join_in_query():
    # The retrieval SQL never joins document_acl; RLS is the authoritative filter (design doc §10).
    r = _retriever()
    rows = r.search_documents(EYE_QUERY, k=50, mode="lexical", as_user="analyst@example.org")
    assert RESTRICTED_DOC not in _doc_ids(rows)


if __name__ == "__main__":
    if not (HOST and USER):
        print("SKIP: set LAKEBASE_HOST + LAKEBASE_USER (and DATABRICKS_CONFIG_PROFILE) to run live RLS tests.")
        raise SystemExit(0)
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  ok  {name}")
            passed += 1
    print(f"\n{passed} RLS negative-security tests passed.")
