"""Publish the repo's saved queries (src/semantic/saved_queries/*.sql) to the workspace as Databricks SQL queries.

Why: Genie One mines inferred snippets from saved queries and query history. These are commented queries for real
analyst tasks that restate governed definitions (the metric views' own rules), so the snippets mined from them are
correct by construction. They deliberately avoid the topics of the 8 benchmark questions
(tests/test_saved_queries.py), so no saved query hands Genie Ontology a benchmark answer.

Ownership: every query this script creates carries the tag `care-protocol-managed`; it only ever updates queries with
that tag and never edits or deletes any other query. A managed query no longer in the repo is reported, not deleted.

File format: `-- name: <display name>` and `-- description: <description>` header lines, then the SQL (its other
`--` comments stay in the query text: they are the context).

    .venv/bin/python -I scripts/sync_saved_queries.py --profile ECT            # dry run
    .venv/bin/python -I scripts/sync_saved_queries.py --profile ECT --apply
"""

from __future__ import annotations

import argparse
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import DatabricksError
from databricks.sdk.service.sql import CreateQueryRequestQuery, UpdateQueryRequestQuery

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src/semantic/saved_queries"
TAG = "care-protocol-managed"
WAREHOUSE = "Serverless Starter Warehouse"
FOLDER = "care_protocol_saved_queries"


def load() -> list[dict]:
    out = []
    for p in sorted(SRC.glob("*.sql")):
        lines = p.read_text(encoding="utf-8").splitlines()
        head = {ln.split(":", 1)[0][3:].strip(): ln.split(":", 1)[1].strip()
                for ln in lines if ln.startswith(("-- name:", "-- description:"))}
        body = "\n".join(ln for ln in lines if not ln.startswith(("-- name:", "-- description:"))).strip()
        if not head.get("name") or not head.get("description"):
            raise SystemExit(f"{p.name}: needs `-- name:` and `-- description:` header lines")
        out.append({"file": p.name, "name": head["name"], "description": head["description"], "sql": body})
    names = [q["name"] for q in out]
    if len(names) != len(set(names)):
        raise SystemExit("duplicate query names")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    w = WorkspaceClient(profile=a.profile)
    wh = next((x.id for x in w.warehouses.list() if x.name == WAREHOUSE), None)
    if not wh:
        raise SystemExit(f"warehouse {WAREHOUSE!r} not found")
    folder = f"/Users/{w.current_user.me().user_name}/{FOLDER}"
    managed = {q.display_name: q for q in w.queries.list(page_size=100) if TAG in (q.tags or [])}
    wanted = load()
    failed = 0
    if a.apply:
        w.workspace.mkdirs(folder)
    for q in wanted:
        cur = managed.get(q["name"])
        same = cur and cur.query_text == q["sql"] and cur.description == q["description"] and cur.warehouse_id == wh
        action = "ok    " if same else ("update" if cur else "create")
        if not a.apply or same:
            print(f"{action if a.apply or same else 'would ' + action.strip():<14} {q['name']}")
            continue
        try:
            if cur:
                w.queries.update(cur.id, "display_name,description,query_text,warehouse_id,tags", query=UpdateQueryRequestQuery(
                    display_name=q["name"], description=q["description"], query_text=q["sql"], warehouse_id=wh,
                    tags=[TAG]))
            else:
                w.queries.create(query=CreateQueryRequestQuery(
                    display_name=q["name"], description=q["description"], query_text=q["sql"], warehouse_id=wh,
                    parent_path=folder, tags=[TAG]))
            print(f"{action:<14} {q['name']}")
        except DatabricksError as e:
            failed += 1
            print(f"FAILED         {q['name']}: {str(e).splitlines()[0][:200]}")
    for name in sorted(set(managed) - {q["name"] for q in wanted}):
        print(f"FLAG           {name}: managed query no longer in the repo (not deleted; remove it by hand if unwanted)")
    print(f"\n{len(wanted)} queries in the repo; folder {folder}")
    if failed:
        raise SystemExit(f"{failed} failed")


if __name__ == "__main__":
    main()
