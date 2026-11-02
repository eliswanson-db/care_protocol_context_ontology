"""Thin read-only SQL-warehouse execution helper (Databricks SDK StatementExecution).

Parameterized only via named markers we control server-side (e.g. :patient_id, :my) — never string-built
from request input. Returns list[dict] keyed by column name. Synchronous; FastAPI runs route handlers in a
threadpool.
"""
from typing import Any

from databricks.sdk.service.sql import StatementParameterListItem

from .config import get_warehouse_id, get_workspace_client


def run_sql(statement: str, params: dict[str, Any] | None = None, *, timeout: str = "50s") -> list[dict]:
    w = get_workspace_client()
    sdk_params = None
    if params:
        sdk_params = [StatementParameterListItem(name=k, value=(None if v is None else str(v)))
                      for k, v in params.items()]
    resp = w.statement_execution.execute_statement(
        warehouse_id=get_warehouse_id(),
        statement=statement,
        parameters=sdk_params,
        wait_timeout=timeout,
    )
    if resp.status and resp.status.state and resp.status.state.value not in ("SUCCEEDED",):
        msg = resp.status.error.message if resp.status.error else resp.status.state.value
        raise RuntimeError(f"SQL failed: {msg}")
    result = resp.result
    manifest = resp.manifest
    if not result or not manifest or not manifest.schema or not manifest.schema.columns:
        return []
    cols = [c.name for c in manifest.schema.columns]
    rows = result.data_array or []
    return [dict(zip(cols, r)) for r in rows]
