"""Saved queries (src/semantic/saved_queries/, published by scripts/sync_saved_queries.py) are Genie context: Genie
One mines inferred snippets from them. They must be well-formed, use fixed periods, and stay off the benchmark's
answers: no benchmark gold id, hero patient, or answer-bearing topic (docs/benchmark/questions_v2.yaml).

    python3 -I tests/test_saved_queries.py
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
QS = yaml.safe_load((ROOT / "docs/benchmark/questions_v2.yaml").read_text())["questions"]
RELATIVE = re.compile(r"\b(current(ly)?|recent(ly)?|this year|today|year[- ]to[- ]date|ytd)\b", re.IGNORECASE)
# Topics whose answers the benchmark asks for: a saved query on them would put the answer in Genie's context.
OFF_LIMITS = {
    "q1 poor control by clinic": re.compile(r"Poor Control Rate", re.IGNORECASE),
    "q2/q7 statin gaps by patient": re.compile(r"gold_adherence_spd", re.IGNORECASE),
    "q3 kidney-complication cohort": re.compile(r"E1[013]\.2\b"),
    "q5 eGFR value set": re.compile(r"KED_EGFR|98979-8|33914-3"),
    "q6 contraindications": re.compile(r"contraindicat|protocol_edges", re.IGNORECASE),
    "q8 outside letters": re.compile(r"\boutside\b|\bletter", re.IGNORECASE),
}


def _load():
    spec = importlib.util.spec_from_file_location("s", ROOT / "scripts/sync_saved_queries.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.load()


def test_queries_are_well_formed():
    qs = _load()
    assert len(qs) >= 10
    for q in qs:
        assert q["sql"].lstrip().upper().startswith(("SELECT", "WITH", "--")), q["file"]
        assert "{" not in q["sql"], f"{q['file']}: unsubstituted placeholder"


def test_fixed_periods_only():
    for q in _load():
        for text in (q["name"], q["description"], q["sql"]):
            assert not RELATIVE.search(text), (q["file"], RELATIVE.search(text).group(0))


def test_no_benchmark_answers():
    heroes = {q["patient"] for q in QS if q.get("patient")}
    for q in _load():
        text = "\n".join((q["name"], q["description"], q["sql"]))
        assert not re.search(r"\bbq\d", text), (q["file"], "benchmark gold id")
        assert not any(h in text for h in heroes), (q["file"], "benchmark hero patient")
        for topic, pat in OFF_LIMITS.items():
            assert not pat.search(text), (q["file"], topic)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
