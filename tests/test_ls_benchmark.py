"""The life-sciences benchmark question set (docs/benchmark/ls_questions.yaml): the rules it must keep. The HEDIS
counterpart is tests/test_benchmark_v2.py.

- every question names the data cutoff (2026-10-31) or another fixed date; no relative dates
- every gold id exists in src/benchmark/ls_gold_queries.sql and is `-- holdout:`
- holdouts never become Genie-space benchmarks
- every fact id exists in docs/benchmark/ls_facts.yaml; every question predicts every approach; no designed winner
- the document golds say what the expected facts claim (Amendment 1; the monitoring report's root cause)
- the participant a question names is the one its stated rule picks (checked live when CARE_LIVE=1)

    python3 -I tests/test_ls_benchmark.py
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load((ROOT / "docs/benchmark/ls_questions.yaml").read_text())
QS = SPEC["questions"]
GOLD = (ROOT / "src/benchmark/ls_gold_queries.sql").read_text()
FACTS = {f["id"] for f in yaml.safe_load((ROOT / "docs/benchmark/ls_facts.yaml").read_text())["facts"]}
RELATIVE = re.compile(r"\b(current(ly)?|recent(ly)?|this year|today|now|year[- ]to[- ]date|ytd|latest)\b", re.IGNORECASE)
APPROACHES = {"metric_view", "closure", "rag", "genie_ontology", "graph"}
DOCS = ROOT / "docs/life_sciences/documents"


def _blocks() -> dict[str, str]:
    return {b.split("\n", 1)[0].strip(): b for b in re.split(r"(?m)^-- @id: ", GOLD)[1:]}


def _sql_gold(q: dict) -> str | None:
    g = q["gold"]
    return None if g.startswith(("doc:", "data:")) else g


def test_questions_use_fixed_dates_only():
    for q in QS:
        assert not RELATIVE.search(q["question"]), (q["id"], RELATIVE.search(q["question"]).group(0))
        assert re.search(r"\d{4}-\d{2}-\d{2}|Amendment 1", q["question"]), (q["id"], "names no fixed date")
        for f in q["expected_facts"]:
            assert not RELATIVE.search(f), (q["id"], f)


def test_nothing_left_pending():
    for q in QS:
        assert "PENDING" not in yaml.safe_dump(q), (q["id"], "has a PENDING value")
    for gid, b in _blocks().items():
        assert re.search(r"expect:\s*\S", b), gid


def test_gold_ids_exist_and_are_holdout():
    blocks = _blocks()
    for q in QS:
        gid = _sql_gold(q)
        if gid:
            assert gid in blocks, (q["id"], gid)
            assert "\n-- holdout:" in "\n" + blocks[gid], f"{gid} must be marked -- holdout:"


def test_holdouts_never_reach_genie_spaces():
    sys.path.insert(0, str(ROOT / "src"))
    from genie import knowledge_stores as ks

    notes = [f"{b.question} {b.sql} {b.note}" for st in ks.stores().values() for b in st.benchmarks]
    for gid in _blocks():
        assert not any(re.search(rf"\b{re.escape(gid)}\b", n) for n in notes), f"holdout {gid} in a Genie space"


def test_every_question_has_facts_and_predictions():
    for q in QS:
        assert set(q["facts"]) <= FACTS, (q["id"], set(q["facts"]) - FACTS)
        assert set(q["predictions"]) == APPROACHES, (q["id"], set(q["predictions"]) ^ APPROACHES)
        assert "wins" not in q, "no question names a designed winner"


def test_document_golds_say_what_they_claim():
    amd = (DOCS / "corpus/CSL-A-PROT-AMD1.md").read_text()
    lq4 = next(q for q in QS if q["id"] == "lq4")["expected_facts"][0]
    for s in ("2025-10-27", "±14 days", "Obstructive sleep apnea added"):
        assert s in amd, s
    assert all(s in lq4 for s in ("2025-10-27", "±7", "±14", "obstructive sleep apnea"))
    lq9 = next(q for q in QS if q["id"] == "lq9")
    doc = re.search(r"doc: (MVR-SITE-118-\d{2})", lq9["gold"]).group(1)
    text = (DOCS / f"monitoring/{doc}.md").read_text()
    assert "Root cause (site interview)" in text and "25 weeks after first dose" in text
    date = re.search(r"Visit: .*?, (\d{4}-\d{2}-\d{2})", text).group(1)
    assert date in lq9["expected_facts"][0], (date, "the expected fact names the report's visit date")
    causes = [p.name for p in (DOCS / "monitoring").glob("MVR-*.md") if "Root cause (site interview)" in p.read_text()]
    assert causes == [f"{doc}.md"], causes


def test_named_participant_is_the_rules_pick():
    if os.environ.get("CARE_LIVE") != "1":
        print("  (skipped live participant check: set CARE_LIVE=1)")
        return
    spec = importlib.util.spec_from_file_location("q", ROOT / "scripts/q.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    C = "eli_test_classic_catalog.clinical_study"
    pick = m.run(
        f"SELECT min(e.USUBJID) AS u FROM {C}.gold_eligibility_criterion e "
        f"JOIN {C}.gold_participant_population p USING (USUBJID) WHERE p.STUDYID = 'CSL-A' AND p.FASFL = 'Y' "
        f"AND p.PPSFL = 'N' AND e.criterion_id = 'EXC-MH' AND e.outcome = 'TRIGGERED' AND size(e.path) >= 2 "
        f"AND NOT exists(p.deviations, d -> d.deviation = 'PROHIBITED_MEDICATION_ON_TREATMENT')"
    )[0]["u"]
    lq7 = next(q for q in QS if q["id"] == "lq7")
    assert pick in lq7["question"], (pick, lq7["question"])


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
