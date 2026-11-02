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

# Endpoints are NEVER hardcoded — everything below is a LOGICAL NAME, resolved to the live id/host/space at
# runtime via the SDK, so the app is portable across workspaces (ECT/DMVM) with no per-workspace ids baked in.
WAREHOUSE_NAME = os.environ.get("CARE_WAREHOUSE_NAME", "Serverless Starter Warehouse")
GENIE_SPACE_NAME = os.environ.get("CARE_GENIE_SPACE_NAME", "Care Protocol — HEDIS Diabetes Quality")
# A4 Lakebase (ADR-0014): the project/branch/endpoint PATH is a logical name (same on every workspace); the
# per-workspace host is resolved from it. The connecting Postgres user resolves to the caller identity.
LAKEBASE_ENDPOINT = os.environ.get("CARE_LAKEBASE_ENDPOINT", "projects/care-protocol/branches/production/endpoints/primary")
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
    """Resolve the SQL warehouse by NAME (WAREHOUSE_NAME) — no hardcoded id."""
    w = get_workspace_client()
    for wh in w.warehouses.list():
        if wh.name == WAREHOUSE_NAME:
            return wh.id
    raise RuntimeError(f"Warehouse {WAREHOUSE_NAME!r} not found in this workspace.")


@lru_cache(maxsize=1)
def get_lakebase_host() -> str:
    """Resolve the Lakebase host from the endpoint PATH via the SDK — no hardcoded DNS."""
    ep = get_workspace_client().postgres.get_endpoint(LAKEBASE_ENDPOINT)
    host = ((ep.status.hosts.host if ep.status and ep.status.hosts else None) or "")
    if not host:
        raise RuntimeError(f"No host on Lakebase endpoint {LAKEBASE_ENDPOINT!r}.")
    return host


@lru_cache(maxsize=1)
def get_lakebase_user() -> str:
    """Postgres connecting identity = the caller (current user locally, service principal when deployed)."""
    return os.environ.get("CARE_LAKEBASE_USER") or get_workspace_client().current_user.me().user_name


@lru_cache(maxsize=1)
def get_genie_space_id() -> str:
    """Resolve the governed Genie space by TITLE prefix (GENIE_SPACE_NAME) — no hardcoded space id."""
    r = get_workspace_client().genie.list_spaces()
    for s in (r.spaces or []):
        if s.title and s.title.startswith(GENIE_SPACE_NAME):
            return s.space_id
    raise RuntimeError(f"No Genie space titled like {GENIE_SPACE_NAME!r} in this workspace.")
