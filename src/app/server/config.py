"""Dual-mode auth + config for the Care Protocol Context app.

Local: uses a Databricks CLI profile (DATABRICKS_PROFILE, default ECT).
Databricks Apps: uses the auto-injected service-principal credentials (WorkspaceClient() with no args).

The app is READ-ONLY over the shared catalog (eli_test_classic_catalog) via a SQL warehouse — it reflects
the throughline, it does not mutate it (ADR-0018/ADR-0019; "sync in, confirm writes"). No Lakebase app-state
yet; add it only when a tab needs to persist.
"""
import os
from functools import lru_cache

from databricks.sdk import WorkspaceClient

IS_DATABRICKS_APP = bool(os.environ.get("DATABRICKS_APP_NAME"))

CATALOG = os.environ.get("CARE_CATALOG", "eli_test_classic_catalog")
SCHEMA = os.environ.get("CARE_SCHEMA", "care_protocol")
SCHEMA_SEMANTIC = os.environ.get("CARE_SCHEMA_SEMANTIC", "care_protocol_semantic")
SCHEMA_TERM = os.environ.get("CARE_SCHEMA_TERM", "care_protocol_terminology")
MEASUREMENT_YEAR = int(os.environ.get("CARE_MEASUREMENT_YEAR", "2025"))
# Which workspace arm this deployment represents (labeling only): ECT baseline vs DMVM ontology-ON.
ARM = os.environ.get("CARE_ARM", "local")
CONTEXT_RELEASE = os.environ.get("CARE_CONTEXT_RELEASE", "dev")

# A4 Lakebase RAG (ADR-0014). Postgres is per-workspace; defaults point at the ECT project. Override via env
# for DMVM. Embeddings are not yet populated on either env (RUNBOOK) -> the RAG route runs lexical/BM25 and
# auto-upgrades to hybrid once rag.chunks.embedding is backfilled.
LAKEBASE_HOST = os.environ.get("CARE_LAKEBASE_HOST", "ep-spring-paper-d2objaly.database.us-east-1.cloud.databricks.com")
LAKEBASE_ENDPOINT = os.environ.get("CARE_LAKEBASE_ENDPOINT", "projects/care-protocol/branches/production/endpoints/primary")
LAKEBASE_USER = os.environ.get("CARE_LAKEBASE_USER", "eli.swanson@databricks.com")
LAKEBASE_SEARCH_EXT = os.environ.get("CARE_LAKEBASE_SEARCH_EXT", "1") == "1"


def get_profile() -> str | None:
    """CLI profile for local auth; None in Databricks Apps (ambient SP)."""
    return None if IS_DATABRICKS_APP else os.environ.get("DATABRICKS_PROFILE", "ECT")


@lru_cache(maxsize=1)
def get_workspace_client() -> WorkspaceClient:
    if IS_DATABRICKS_APP:
        return WorkspaceClient()
    profile = os.environ.get("DATABRICKS_PROFILE", "ECT")
    return WorkspaceClient(profile=profile)


@lru_cache(maxsize=1)
def get_warehouse_id() -> str:
    """Warehouse for SQL execution. Explicit env wins; else resolve 'Serverless Starter Warehouse' by name."""
    wid = os.environ.get("CARE_WAREHOUSE_ID")
    if wid:
        return wid
    w = get_workspace_client()
    for wh in w.warehouses.list():
        if wh.name == "Serverless Starter Warehouse":
            return wh.id
    raise RuntimeError("No CARE_WAREHOUSE_ID set and 'Serverless Starter Warehouse' not found.")
