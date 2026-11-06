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


import re as _re

_FORBIDDEN = _re.compile(r"\b(insert|update|delete|merge|drop|create|alter|truncate|grant|revoke|copy|optimize|vacuum|"
                         r"call|set|use|refresh|msck|analyze|cache|uncache|restore|clone|put|get|remove|execute)\b",
                         _re.I)


def run_readonly(sql: str, row_limit: int = 200) -> list[dict]:
    """Execute agent-written SQL under a strict guard: a single SELECT/WITH statement, no DDL/DML/command keywords,
    results capped. Raises ValueError if the statement is rejected."""
    body = _re.sub(r"'[^']*'", "''", sql)              # ignore string literals when scanning keywords
    body = _re.sub(r"`[^`]*`", "``", body)             # ...and backticked identifiers
    if ";" in body.strip().rstrip(";"):
        raise ValueError("rejected: more than one statement")
    if not _re.match(r"^\s*(\(\s*)*(select|with)\b", body, _re.I):
        raise ValueError("rejected: not a SELECT/WITH query")
    if m := _FORBIDDEN.search(body):
        raise ValueError(f"rejected: forbidden keyword {m.group(0)!r}")
    import time

    se = _client().statement_execution
    r = se.execute_statement(warehouse_id=_warehouse_id(), statement=sql, wait_timeout="30s", row_limit=row_limit)
    deadline = time.time() + 240
    while r.status and r.status.state and r.status.state.value in ("PENDING", "RUNNING"):
        if time.time() > deadline:
            se.cancel_execution(r.statement_id)
            raise RuntimeError("query did not finish within 240s")
        time.sleep(2)
        r = se.get_statement(r.statement_id)
    state = r.status.state.value if r.status and r.status.state else "UNKNOWN"
    if state != "SUCCEEDED":
        raise RuntimeError(f"SQL {state}: {(r.status.error.message if r.status and r.status.error else state)[:300]}")
    if not (r.result and r.result.data_array):
        return []
    cols = [c.name for c in r.manifest.schema.columns]
    return [dict(zip(cols, row)) for row in r.result.data_array]


def fetch_all(sql: str):
    """Yield every row (as a list) of a large result: EXTERNAL_LINKS disposition, JSON_ARRAY chunks, downloaded from
    the presigned links (no auth header -- the links carry their own credentials)."""
    import time

    import requests
    from databricks.sdk.service.sql import Disposition, Format

    se = _client().statement_execution
    r = se.execute_statement(warehouse_id=_warehouse_id(), statement=sql, wait_timeout="30s",
                             disposition=Disposition.EXTERNAL_LINKS, format=Format.JSON_ARRAY)
    deadline = time.time() + 600
    while r.status and r.status.state and r.status.state.value in ("PENDING", "RUNNING"):
        if time.time() > deadline:
            raise RuntimeError("SQL statement did not finish within 600s")
        time.sleep(2)
        r = se.get_statement(r.statement_id)
    if r.status.state.value != "SUCCEEDED":
        raise RuntimeError(f"SQL {r.status.state.value}: {r.status.error.message if r.status.error else ''}")
    chunk = r.result
    while chunk is not None:
        for link in chunk.external_links or []:
            yield from requests.get(link.external_link, timeout=300).json()
        nxt = (chunk.external_links[-1].next_chunk_index if chunk.external_links else None)
        chunk = se.get_statement_result_chunk_n(r.statement_id, nxt) if nxt is not None else None
