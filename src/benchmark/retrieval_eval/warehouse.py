"""Minimal SQL executor for the retrieval eval -- resolves the warehouse by NAME (no hardcoded id) and runs
read-only statements via the SDK. Mirrors the app's config conventions (ADR-0018/0019)."""
from __future__ import annotations

import os
from functools import lru_cache

from databricks.sdk import WorkspaceClient

WAREHOUSE_NAME = os.environ.get("CARE_WAREHOUSE_NAME", "Serverless Starter Warehouse")


@lru_cache(maxsize=1)
def _client() -> WorkspaceClient:
    profile = os.environ.get("DATABRICKS_CONFIG_PROFILE") or os.environ.get("DATABRICKS_PROFILE")
    return WorkspaceClient(profile=profile) if profile else WorkspaceClient()


@lru_cache(maxsize=1)
def _warehouse_id() -> str:
    if os.environ.get("CARE_WAREHOUSE_ID"):
        return os.environ["CARE_WAREHOUSE_ID"]
    for wh in _client().warehouses.list():
        if wh.name == WAREHOUSE_NAME:
            return wh.id
    raise RuntimeError(f"Warehouse {WAREHOUSE_NAME!r} not found in this workspace.")


def run_sql(sql: str) -> list[dict]:
    """Execute SQL and return rows as list[dict]. Polls to completion (handles a cold/STOPPED warehouse) and
    RAISES on a failed statement rather than silently returning [] (so a broken query is never read as 'empty')."""
    import time

    se = _client().statement_execution
    r = se.execute_statement(warehouse_id=_warehouse_id(), statement=sql, wait_timeout="30s")
    deadline = time.time() + 180
    while r.status and r.status.state and r.status.state.value in ("PENDING", "RUNNING"):
        if time.time() > deadline:
            raise RuntimeError("SQL statement did not finish within 180s (warehouse cold start?)")
        time.sleep(2)
        r = se.get_statement(r.statement_id)
    state = r.status.state.value if r.status and r.status.state else "UNKNOWN"
    if state != "SUCCEEDED":
        err = (r.status.error.message if r.status and r.status.error else state)
        raise RuntimeError(f"SQL {state}: {err}")
    if not (r.result and r.result.data_array):
        return []
    cols = [c.name for c in r.manifest.schema.columns]
    return [dict(zip(cols, row)) for row in r.result.data_array]


def run_scalar(sql: str):
    rows = run_sql(sql)
    return list(rows[0].values())[0] if rows else None
