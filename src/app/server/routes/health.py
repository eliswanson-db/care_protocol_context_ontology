"""Health + environment metadata (arm label, catalog, measurement year, context release)."""
from fastapi import APIRouter

from ..config import ARM, CATALOG, CONTEXT_RELEASE, IS_DATABRICKS_APP, MEASUREMENT_YEAR

router = APIRouter()


@router.get("/health")
def health():
    return {"ok": True, "deployed": IS_DATABRICKS_APP}


@router.get("/meta")
def meta():
    """Surfaced in the app header so every view shows arm + data/context version + the synthetic label."""
    return {
        "arm": ARM,
        "catalog": CATALOG,
        "measurement_year": MEASUREMENT_YEAR,
        "context_release": CONTEXT_RELEASE,
        "synthetic": True,
        "disclaimer": "Synthetic Synthea data. HEDIS-aligned demo, not NCQA-certified.",
    }
