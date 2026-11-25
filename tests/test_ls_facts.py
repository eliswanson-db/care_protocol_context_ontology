"""Life-sciences fact presence (the HEDIS counterpart is tests/test_hedis_facts.py): every fact the LS benchmark
questions depend on, per approach.

docs/benchmark/ls_facts.yaml gives each fact one entry per approach: a pointer that must resolve, `none` (the
approach can't reasonably hold it) or `gap` (it could and doesn't yet). File pointers are checked offline; table
and graph pointers against ECT when CARE_LIVE=1 (read-only queries through scripts/q.py).

    python3 -I tests/test_ls_facts.py            # offline + the gap list
    CARE_LIVE=1 python3 -I tests/test_ls_facts.py
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FACTS = yaml.safe_load((ROOT / "docs/benchmark/ls_facts.yaml").read_text())["facts"]
QUESTIONS = {q["id"] for q in yaml.safe_load((ROOT / "docs/benchmark/ls_questions.yaml").read_text())["questions"]}
MODES = ["metric_view", "closure", "rag", "genie_ontology", "graph"]
CATALOG = "eli_test_classic_catalog"
NS = "https://clinical-study-lab.example/ontology/"
GRAPH = "eswanson_demo.ontobricks.triplestore_clinicalstudylab_v4_graph"


def _kind(entry: dict) -> str:
    for k in ("none", "gap"):
        if k in entry:
            return k
    if "file" in entry:
        return "file"
    if "table" in entry:
        return "table"
    if "p" in entry:
        return "triple"
    raise AssertionError(f"unrecognized entry {entry}")


def _q():
    spec = importlib.util.spec_from_file_location("q", ROOT / "scripts/q.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.run


def test_every_fact_has_one_entry_per_approach():
    ids = [f["id"] for f in FACTS]
    assert len(ids) == len(set(ids)), "duplicate fact id"
    for f in FACTS:
        assert f.get("fact") and f.get("questions"), f["id"]
        assert set(f["questions"]) <= QUESTIONS, (f["id"], set(f["questions"]) - QUESTIONS)
        assert set(MODES) <= set(f), (f["id"], sorted(set(MODES) - set(f)))
        for m in MODES:
            _kind(f[m])


def test_file_pointers_resolve():
    bad = []
    for f in FACTS:
        for m in MODES:
            e = f[m]
            if _kind(e) != "file":
                continue
            p = ROOT / e["file"]
            text = p.read_text(encoding="utf-8") if p.exists() else ""
            missing = [h for h in e["has"] if h not in text]
            if not p.exists() or missing:
                bad.append((f["id"], m, e["file"], missing or "file missing"))
    assert not bad, bad


def test_live_pointers_resolve():
    if os.environ.get("CARE_LIVE") != "1":
        print("  (skipped live table checks: set CARE_LIVE=1)")
        return
    run = _q()
    bad = []
    for f in FACTS:
        for m in MODES:
            e = f[m]
            if _kind(e) == "table":
                sql = f"SELECT count(*) AS n FROM {CATALOG}.{e['table']} WHERE {e['where']}"
            elif _kind(e) == "triple":
                conds = [f"{col} = '{NS}{e[k]}'" for k, col in (("s", "subject"), ("p", "predicate"), ("o", "object"))
                         if e.get(k)]
                sql = f"SELECT count(*) AS n FROM {GRAPH} WHERE " + " AND ".join(conds)
            if _kind(e) in ("table", "triple"):
                if int(run(sql)[0]["n"]) == 0:
                    bad.append((f["id"], m, sql))
    assert not bad, bad


def gaps() -> list[tuple[str, str, str]]:
    return [(f["id"], m, f[m]["gap"]) for f in FACTS for m in MODES if "gap" in f[m]]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
    print(f"\n{len(FACTS)} facts. Held / none / gap per approach:")
    for m in MODES:
        kinds = [_kind(f[m]) for f in FACTS]
        held = sum(k in ("file", "table", "triple") for k in kinds)
        print(f"  {m:15} {held:2} held  {kinds.count('none'):2} none  {kinds.count('gap'):2} gap")
    print("\nGaps (feasible, not yet held):")
    for fid, m, why in gaps():
        print(f"  {fid} {m:15} {why}")
    sys.exit(0)
