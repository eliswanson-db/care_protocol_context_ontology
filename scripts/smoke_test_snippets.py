"""Smoke-test every curated SQL asset against the live warehouse (demo-safety net).

The Genie example-SQL snippets (`*.geniespace.json` -> instructions.example_question_sqls) and the AI/BI
dashboard dataset queries (`*.lvdash.json` -> datasets[].queryLines) are demo-critical: a snippet that no longer
executes is a silent demo failure (a renamed metric-view measure, a dropped column, a typo). This runs each one
on the SQL warehouse and reports pass/fail. Deterministic (it executes the SQL; it does NOT exercise Genie's
NL->SQL, which is non-deterministic -- that's the benchmark's job).

Shells out to the `databricks` CLI (api post /api/2.0/sql/statements) so it needs no Python SDK install.

Usage:
  python scripts/smoke_test_snippets.py --warehouse_id <WH> --profile ECT
  python scripts/smoke_test_snippets.py --warehouse_id <WH> --profile ECT --resources_dir resources
"""
import argparse
import glob
import json
import os
import subprocess


def _flatten(v):
    """A snippet SQL / queryLines is a list of string fragments; join to one statement."""
    return ("".join(v) if isinstance(v, list) else str(v)).strip()


def _run(sql, warehouse_id, profile):
    """Execute one statement via the databricks CLI. Returns (ok, state, error_message)."""
    payload = json.dumps({"warehouse_id": warehouse_id, "statement": sql, "wait_timeout": "50s"})
    try:
        out = subprocess.run(
            ["databricks", "api", "post", "/api/2.0/sql/statements", "--profile", profile, "--json", payload],
            capture_output=True, text=True, timeout=120)
        d = json.loads(out.stdout) if out.stdout.strip() else {}
    except Exception as e:  # noqa: BLE001
        return False, "EXCEPTION", str(e)
    status = d.get("status", {}) or {}
    state = status.get("state", "UNKNOWN")
    err = (status.get("error", {}) or {}).get("message", "") or (out.stderr.strip() if not d else "")
    return state == "SUCCEEDED", state, err


def collect(resources_dir):
    """Return [(asset_label, question_or_name, sql), ...] across all Genie spaces + dashboards."""
    items = []
    for path in sorted(glob.glob(os.path.join(resources_dir, "*.geniespace.json"))):
        doc = json.load(open(path))
        base = os.path.basename(path)
        for ex in doc.get("instructions", {}).get("example_question_sqls", []):
            q = _flatten(ex.get("question", ""))
            items.append((f"genie:{base}", q, _flatten(ex.get("sql", ""))))
    for path in sorted(glob.glob(os.path.join(resources_dir, "*.lvdash.json"))):
        doc = json.load(open(path))
        base = os.path.basename(path)
        for ds in doc.get("datasets", []):
            items.append((f"dash:{base}", ds.get("name", "?"), _flatten(ds.get("queryLines", ""))))
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--warehouse_id", required=True)
    ap.add_argument("--profile", default="ECT")
    ap.add_argument("--resources_dir", default="resources")
    args = ap.parse_args()

    items = collect(args.resources_dir)
    print(f"Smoke-testing {len(items)} curated SQL assets on warehouse {args.warehouse_id}...\n")

    fails = []
    by_asset = {}
    for label, name, sql in items:
        ok, state, err = _run(sql, args.warehouse_id, args.profile)
        by_asset.setdefault(label, [0, 0])
        by_asset[label][0 if ok else 1] += 1
        if not ok:
            fails.append((label, name, state, err[:200], sql[:160]))
        print(f"  [{'OK ' if ok else 'XX '}] {label:<34} {name[:60]}")

    print("\n=== by asset ===")
    for label in sorted(by_asset):
        passed, failed = by_asset[label]
        print(f"  {label:<34} {passed} pass / {failed} fail")

    n = len(items)
    nfail = len(fails)
    print(f"\n{n - nfail}/{n} passed.")
    if fails:
        print("\n=== FAILURES ===")
        for label, name, state, err, sql in fails:
            print(f"- {label} :: {name}\n    state={state} err={err}\n    sql={sql}")
        raise SystemExit(1)
    print("All curated SQL assets execute.")


if __name__ == "__main__":
    main()
