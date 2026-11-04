"""Ad-hoc read-only query helper against ECT. Usage: .venv/bin/python scripts/q.py "SELECT ..." [--json]
Reads SQL from argv[1] (or stdin if '-'). Prints rows as a table, or JSON with --json. Dev helper only.
"""
import json
import sys
import time

from databricks.sdk import WorkspaceClient

WH = "5cc64ecfbccf59b1"  # Serverless Starter Warehouse (ECT)


def run(sql: str) -> list[dict]:
    w = WorkspaceClient(profile="ECT")
    resp = w.statement_execution.execute_statement(warehouse_id=WH, statement=sql, wait_timeout="50s")
    for _ in range(30):
        st = resp.status.state.value if resp.status and resp.status.state else "UNKNOWN"
        if st == "SUCCEEDED":
            break
        if st in ("FAILED", "CANCELED", "CLOSED"):
            msg = resp.status.error.message if resp.status and resp.status.error else st
            raise SystemExit(f"SQL {st}: {msg}")
        time.sleep(2)
        resp = w.statement_execution.get_statement(resp.statement_id)
    man = resp.manifest
    res = resp.result
    if not man or not man.schema or not man.schema.columns:
        return []
    cols = [c.name for c in man.schema.columns]
    return [dict(zip(cols, r)) for r in (res.data_array or [])] if res else []


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--json"]
    as_json = "--json" in sys.argv
    sql = sys.stdin.read() if (not args or args[0] == "-") else args[0]
    rows = run(sql)
    if as_json:
        print(json.dumps(rows, default=str, indent=2))
    else:
        if not rows:
            print("(no rows)")
        else:
            cols = list(rows[0].keys())
            print(" | ".join(cols))
            print("-" * 60)
            for r in rows[:50]:
                print(" | ".join(str(r.get(c))[:40] for c in cols))
            if len(rows) > 50:
                print(f"... (+{len(rows) - 50} more)")
