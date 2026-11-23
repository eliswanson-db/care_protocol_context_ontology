"""Deterministic unit tests for the A4 RAG corpus builder (scripts/lakebase_rag_corpus.py).

No workspace required — exercises the committed corpus + chunker. Run:
    python3 -I tests/test_rag_corpus_build.py        # plain (asserts)
    pytest tests/test_rag_corpus_build.py            # if pytest is installed
"""
import importlib.util
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("rag_corpus", os.path.join(REPO, "scripts/lakebase_rag_corpus.py"))
rag = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rag)

DOCS = rag.load_docs(os.path.join(REPO, "docs/care_protocol/corpus"),
                     os.path.join(REPO, "docs/care_protocol/html"))
BY_ID = {d["meta"]["doc_id"]: d for d in DOCS}


LETTERS = [d for d in DOCS if d["meta"]["doc_id"].startswith("LETTER-EYE-")]


def test_all_corpus_docs_loaded():
    # protocol / memo markdown + the HTML lineage anchor + the generated outside-provider letters
    for required in ("CP-DM-2025.1", "PAYER-MEMO-MY2026", "CP-SSD-BH-2025.1"):
        assert required in BY_ID, f"missing corpus doc {required}"
    assert len(LETTERS) >= 50, f"expected the generated outside letters (scripts/gen_outside_letters.py), got {len(LETTERS)}"


def test_patient_letters_are_care_team_restricted_and_about_real_patients():
    # Per-patient letters are visible to care_team ONLY (drives the +perm security tracer), each tied to a real
    # demo patient (a Synthea UUID), dated inside MY2026 on or before the extract horizon.
    for d in LETTERS:
        m = d["meta"]
        assert m["access"] == ["care_team"], f"{m['doc_id']} must be care_team-only, got {m['access']}"
        assert len(m["patient_id"]) == 36 and m["patient_id"].count("-") == 4, m["patient_id"]
        assert "2026-01-01" <= m["effective_date"] <= "2026-10-30", m["effective_date"]


def test_population_docs_visible_to_both_scopes():
    for doc_id in ("CP-DM-2025.1", "CP-PHARM-CARDIORENAL-2025.1", "PAYER-MEMO-MY2026"):
        acl = set(BY_ID[doc_id]["meta"]["access"])
        assert acl == {"quality_analytics", "care_team"}, f"{doc_id} ACL wrong: {acl}"


def test_provenance_preserved():
    # Every chunk-bearing doc must carry section headings for citation provenance.
    for d in DOCS:
        assert d["sections"], f"{d['meta']['doc_id']} produced no sections"
        assert all(hd.strip() for hd, _ in d["sections"]), "blank section heading"


def test_chunking_is_deterministic():
    a = {s for d in rag.load_docs(os.path.join(REPO, "docs/care_protocol/corpus"),
                                  os.path.join(REPO, "docs/care_protocol/html")) for s in (d["hash"],)}
    b = {d["hash"] for d in DOCS}
    assert a == b, "content hashes are not stable across loads"


def test_drift_doc_supersedes_the_2025_protocol():
    assert BY_ID["PAYER-MEMO-MY2026"]["meta"].get("supersedes") == "CP-DM-2025.1"
    assert BY_ID["PAYER-MEMO-MY2026"]["meta"].get("measurement_year") == "2026"


def test_membership_manifest_parses():
    m = rag.parse_group_membership(os.path.join(REPO, "context/value_set_manifests/rag_access_manifest.yaml"))
    assert m.get("analyst@example.org") == ["quality_analytics"]
    assert set(m.get("clinician@example.org", [])) == {"quality_analytics", "care_team"}


def test_study_documents_load_as_their_own_corpus():
    # The Clinical Study lab's documents share the Lakebase tables but not the corpus: each demo searches its own.
    ls = rag.load_ls_docs(os.path.join(REPO, "docs/life_sciences/documents/corpus"))
    assert len(ls) == 8, len(ls)  # protocols, SAPs, Amendment 1, data spec, interpretation note
    assert {d["meta"]["corpus"] for d in ls} == {"clinical_study"}
    assert all(d["meta"]["patient_id"] is None and d["meta"]["access"] == ["study_team"] for d in ls)
    assert all(d["sections"] for d in ls), "every study document has sections"
    assert "care_protocol" == DOCS[0]["meta"].get("corpus", "care_protocol")
    assert not {d["meta"]["doc_id"] for d in ls} & set(BY_ID), "document ids collide across demos"


def test_monitoring_reports_are_consistent_with_the_study_timeline():
    import datetime as dt
    import re

    mon = rag.load_ls_docs(os.path.join(REPO, "docs/life_sciences/documents/monitoring"))
    assert len(mon) >= 500, len(mon)  # one per site per visit (scripts/gen_monitoring_reports.py)
    assert {d["meta"]["corpus"] for d in mon} == {"clinical_study"}
    assert all(d["meta"]["access"] == ["study_team"] for d in mon)
    text = {d["meta"]["doc_id"]: open(d["path"], encoding="utf-8").read() for d in mon}
    causes = sorted(k for k, t in text.items() if "Root cause (site interview)" in t)
    # The systematic cause is recorded once, at the one site whose Week 24 visits are systematically late, and before
    # Amendment 1 (which cites it) takes effect.
    assert len(causes) == 1 and causes[0].startswith("MVR-SITE-118-"), causes
    visit = re.search(r"^- Visit: .*, (\d{4}-\d{2}-\d{2})$", text[causes[0]], re.M).group(1)
    amd1 = re.search(r'^effective_date: "([\d-]+)"', open(os.path.join(
        REPO, "docs/life_sciences/documents/corpus/CSL-A-PROT-AMD1.md"), encoding="utf-8").read(), re.M).group(1)
    assert dt.date.fromisoformat(visit) < dt.date.fromisoformat(amd1), (visit, amd1)


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  ok  {name}")
            passed += 1
    print(f"\n{passed} tests passed.")
