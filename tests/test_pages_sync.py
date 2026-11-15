"""scripts/sync_pages.py parsing and ownership (no workspace).

    python3 -I tests/test_pages_sync.py   (or pytest)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sync_pages as sp  # noqa: E402


def _all():
    return [sp.parse_source(p) for c in sp.DEMOS.values() for p in sorted((ROOT / c["src"]).glob("*.md"))
            if p.name != "README.md"]


def test_every_source_parses_within_api_limits():
    srcs = _all()
    assert len(srcs) == 31
    for s in srcs:
        pg = s["page"]
        assert 1 <= len(pg["display_name"]) <= 200
        assert len(pg["synonyms"]) <= 50 and all(1 <= len(x) <= 200 for x in pg["synonyms"])
        assert s["domain_name"] == "Clinical Domain"


def test_titles_are_unique_across_demos():
    # the API refuses two PUBLISHED Pages with one title in a domain, and both demos share Clinical Domain
    titles = [s["page"]["display_name"] for s in _all()]
    assert len(titles) == len(set(titles))


def test_footer_marks_ownership_and_round_trips():
    for s in _all():
        m = sp.FOOTER_RE.search(s["page"]["body"])
        assert m and m.group(1) == s["source"] and m.group(2) == s["hash"]
    assert not sp.FOOTER_RE.search("A page somebody wrote by hand.")


def test_hash_is_stable_and_content_sensitive():
    p = ROOT / "docs/life_sciences/pages/study-glossary.md"
    a, b = sp.parse_source(p), sp.parse_source(p)
    assert a["hash"] == b["hash"]


def test_topic_key_groups_old_and_new_titles():
    assert sp.topic_key("BPD (Blood Pressure Control)") == sp.topic_key("BPD — Blood Pressure Control for Patients") == "bpd"
    assert sp.topic_key("HbA1c (Hemoglobin A1c)") == sp.topic_key("HbA1c (A1c) — Hemoglobin A1c") == "hba1c"
    assert sp.topic_key("Measurement Year") == "measurement year"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
