"""The locked HEDIS benchmark v2 (docs/benchmark/questions_v2.yaml): the rules the set must keep.

- every question names a fixed date or period: no "current", "recent", "this year", "today", "year to date"
- every gold id exists in src/benchmark/gold_queries.sql and is `-- holdout:` (no approach may hold the answer key)
- holdouts never become Genie-space benchmarks (src/genie/knowledge_stores.py)
- every fact id exists in docs/benchmark/hedis_facts.yaml
- question 8's outside letter says what its gold says (date, finding, care-team only)

    python3 -I tests/test_benchmark_v2.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
QS = yaml.safe_load((ROOT / "docs/benchmark/questions_v2.yaml").read_text())["questions"]
GOLD = (ROOT / "src/benchmark/gold_queries.sql").read_text()
FACTS = {f["id"] for f in yaml.safe_load((ROOT / "docs/benchmark/hedis_facts.yaml").read_text())["facts"]}
RELATIVE = re.compile(r"\b(current(ly)?|recent(ly)?|this year|today|now|year[- ]to[- ]date|ytd|latest)\b", re.IGNORECASE)
APPROACHES = {"metric_view", "closure", "rag", "genie_ontology", "graph"}


def _blocks() -> dict[str, str]:
    return {b.split("\n", 1)[0].strip(): b for b in re.split(r"(?m)^-- @id: ", GOLD)[1:]}


def _gold_ids(q: dict) -> list[str]:
    g = q["gold"]
    ids = g if isinstance(g, list) else [g]
    return [i for i in ids if not i.startswith("doc:")]


def test_questions_use_fixed_dates_only():
    for q in QS:
        assert not RELATIVE.search(q["question"]), (q["id"], RELATIVE.search(q["question"]).group(0))
        for f in q["expected_facts"]:
            assert not RELATIVE.search(f), (q["id"], f)


def test_gold_ids_exist_and_are_holdout():
    blocks = _blocks()
    for q in QS:
        for gid in _gold_ids(q):
            assert gid in blocks, (q["id"], gid)
            assert "\n-- holdout:" in "\n" + blocks[gid], f"{gid} must be marked -- holdout:"


def test_holdouts_never_reach_genie_spaces():
    sys.path.insert(0, str(ROOT / "src"))
    from genie import knowledge_stores as ks

    holdout_sql = {b.split("\n", 1)[0].strip() for b in re.split(r"(?m)^-- @id: ", GOLD)[1:] if "\n-- holdout:" in b}
    notes = [b.note for st in ks.stores().values() for b in st.benchmarks]  # note = "Gold answer key <id> ..."
    assert notes, "expected some (non-holdout) gold benchmarks in the Genie spaces"
    for gid in holdout_sql:
        assert not any(re.search(rf"\b{re.escape(gid)}\b", n) for n in notes), f"holdout {gid} leaked into a Genie space"


def test_every_question_has_facts_and_predictions():
    for q in QS:
        assert set(q["facts"]) <= FACTS, (q["id"], set(q["facts"]) - FACTS)
        assert set(q["predictions"]) == APPROACHES, (q["id"], set(q["predictions"]) ^ APPROACHES)
        assert "wins" not in q, "no question names a designed winner"


def test_q8_letter_matches_its_gold():
    q8 = next(q for q in QS if q["id"] == "q8")
    text = (ROOT / f"docs/care_protocol/corpus/letters/LETTER-EYE-{q8['patient'][:8]}.md").read_text()
    assert f"patient_id: {q8['patient']}" in text and "access: [care_team]" in text
    assert "effective_date: 2026-09-02" in text and "No evidence of diabetic retinopathy" in text
    assert all(s in q8["expected_facts"][0] for s in ("2026-09-02", "Northside Optometry Group"))
    assert "Northside Optometry Group" in text


def test_app_bundles_the_current_results():
    # The app serves benchmark_data/ copies (the repo isn't synced to the app); they must match docs/benchmark.
    for name in ("questions_v2.yaml", "benchmark_v2.json", "genie_ontology_retrieval_v2.json"):
        src, dst = ROOT / "docs/benchmark" / name, ROOT / "src/app/server/benchmark_data" / name
        assert dst.read_bytes() == src.read_bytes(), f"copy docs/benchmark/{name} to src/app/server/benchmark_data/"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
