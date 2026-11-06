"""Read-only validation of the derived closure tables against their direct edges (source of truth).

Checks from the "Closure-Table Retrieval on Databricks" review (2026-11-06): self-row coverage, one row per
(ancestor, descendant) key, every direct edge present at depth 1, no missing node references, no cycles, and the
closure equals an on-demand recursive traversal of the edges. Also reports which relationship each closure mixes.

  .venv/bin/python -I scripts/validate_closure.py            # uses scripts/q.py's ECT warehouse
"""
from __future__ import annotations

import os
import subprocess
import sys
import json

T = "eli_test_classic_catalog.care_protocol_terminology"
PAIRS = [("icd10_hier", "icd10_closure"), ("rxnorm_hier", "rxnorm_closure")]
Q = os.path.join(os.path.dirname(__file__), "q.py")


def sql(stmt: str) -> list[dict]:
    out = subprocess.run([sys.executable, "-I", Q, stmt, "--json"], capture_output=True, text=True, check=True).stdout
    return json.loads(out[out.index("["):]) if "[" in out else []


def one(stmt: str):
    rows = sql(stmt)
    return next(iter(rows[0].values())) if rows else None


def main():
    ok = True
    for hier, clos in PAIRS:
        h, c = f"{T}.{hier}", f"{T}.{clos}"
        checks = {
            "nodes": f"SELECT count(*) FROM {h}",
            "self rows missing": f"SELECT count(*) FROM {h} n LEFT ANTI JOIN {c} x ON x.ancestor_code = n.code "
                                 f"AND x.descendant_code = n.code AND x.depth = 0",
            "duplicate keys": f"SELECT count(*) FROM (SELECT ancestor_code, descendant_code FROM {c} "
                              f"GROUP BY 1, 2 HAVING count(*) > 1)",
            "direct edges not at depth 1": f"SELECT count(*) FROM {h} e LEFT ANTI JOIN {c} x ON x.ancestor_code = "
                                           f"e.parent_code AND x.descendant_code = e.code AND x.depth = 1 "
                                           f"WHERE e.parent_code IS NOT NULL",
            "parents missing as nodes": f"SELECT count(*) FROM {h} e LEFT ANTI JOIN {h} p ON p.code = e.parent_code "
                                        f"WHERE e.parent_code IS NOT NULL",
            "closure rows with unknown nodes": f"SELECT count(*) FROM {c} x LEFT ANTI JOIN {h} n "
                                               f"ON n.code = x.descendant_code",
            "cycles (non-self rows a->a)": f"SELECT count(*) FROM {c} WHERE ancestor_code = descendant_code AND depth > 0",
            "rows differing from a recursive traversal": f"""
                WITH RECURSIVE walk (ancestor_code, descendant_code, depth) AS (
                  SELECT code, code, 0 FROM {h}
                  UNION ALL
                  SELECT w.ancestor_code, e.code, w.depth + 1 FROM walk w JOIN {h} e ON e.parent_code = w.descendant_code
                ), want AS (SELECT ancestor_code, descendant_code, min(depth) AS depth FROM walk GROUP BY 1, 2)
                SELECT count(*) FROM (
                  (SELECT * FROM want EXCEPT SELECT ancestor_code, descendant_code, depth FROM {c})
                  UNION ALL (SELECT ancestor_code, descendant_code, depth FROM {c} EXCEPT SELECT * FROM want))""",
        }
        print(f"== {clos} (edges: {hier})")
        for name, stmt in checks.items():
            v = int(one(stmt) or 0)
            bad = name != "nodes" and v != 0
            ok &= not bad
            print(f"  {'FAIL' if bad else 'ok  '} {name}: {v}")
        mix = sql(f"SELECT regexp_extract(parent_code, '^(DRUGCLASS)', 1) <> '' AS from_class, count(*) AS n "
                  f"FROM {h} WHERE parent_code IS NOT NULL GROUP BY 1") if hier.startswith("rxnorm") else []
        if mix:
            kinds = {("class -> ingredient" if r["from_class"] in (True, "true") else "ingredient -> product"): r["n"]
                     for r in mix}
            print(f"  note relationships mixed in one closure: {kinds}")
    print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
