"""HEDIS fact presence (docs/CONTEXT_LAB_PLAN.md §2): every fact the benchmark questions depend on, per approach.

docs/benchmark/hedis_facts.yaml gives each fact one entry per approach: a pointer that must resolve, `none` (the
approach can't reasonably hold it) or `gap` (it could and doesn't yet). File pointers are checked offline. Table
and graph pointers are checked against ECT when CARE_LIVE=1 (read-only queries through scripts/q.py).

    python3 -I tests/test_hedis_facts.py            # offline + the gap list
    CARE_LIVE=1 python3 -I tests/test_hedis_facts.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FACTS = yaml.safe_load((ROOT / "docs/benchmark/hedis_facts.yaml").read_text())["facts"]
MODES = ["metric_view", "closure", "rag", "genie_ontology", "graph"]
NS = "https://care-protocol.example/ontology/"
TERM = "eli_test_classic_catalog.care_protocol_terminology"
GRAPH = json.loads((ROOT / "docs/ontology/graph_baseline_clinicaldomain.json").read_text())["graph"]


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


def _sql(entry: dict) -> str:
    if "table" in entry:
        return f"SELECT count(*) AS n FROM {TERM}.{entry['table']} WHERE {entry['where']}"
    conds = [f"{col} = '{NS}{entry[k]}'" for k, col in (("s", "subject"), ("p", "predicate"), ("o", "object"))
             if entry.get(k)]
    return f"SELECT count(*) AS n FROM {GRAPH} WHERE " + " AND ".join(conds)


def test_every_fact_has_one_entry_per_approach():
    ids = [f["id"] for f in FACTS]
    assert len(ids) == len(set(ids)), "duplicate fact id"
    for f in FACTS:
        assert f.get("fact") and f.get("questions"), f["id"]
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
            text = p.read_text() if p.exists() else ""
            missing = [h for h in e["has"] if h not in text]
            if not p.exists() or missing:
                bad.append((f["id"], m, e["file"], missing or "file missing"))
    assert not bad, bad


def test_live_pointers_resolve():
    if os.environ.get("CARE_LIVE") != "1":
        print("  (skipped live table/graph checks: set CARE_LIVE=1)")
        return
    run = _q()
    bad = []
    for f in FACTS:
        for m in MODES:
            e = f[m]
            if _kind(e) in ("table", "triple"):
                n = int(run(_sql(e))[0]["n"])
                if n == 0:
                    bad.append((f["id"], m, _sql(e)))
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
