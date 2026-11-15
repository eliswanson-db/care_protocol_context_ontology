"""Health check. Per-demo metadata moved to routes/demos.py (/api/meta reads the active demo)."""

from fastapi import APIRouter

from ..config import IS_DATABRICKS_APP

router = APIRouter()


@router.get("/health")
def health():
    return {"ok": True, "deployed": IS_DATABRICKS_APP}
