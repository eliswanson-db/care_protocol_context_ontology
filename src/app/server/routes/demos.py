"""Demo-agnostic endpoints: the demo list, per-demo metadata, and deployment readiness."""

from fastapi import APIRouter, Request

from .. import demos
from ..config import ARM, CATALOG, CONTEXT_RELEASE, MEASUREMENT_YEAR
from ..readiness import readiness

router = APIRouter()


@router.get("/demos")
def list_demos():
    return {"demos": demos.public_demos(), "default": demos.DEFAULT_DEMO}


@router.get("/meta")
def meta(request: Request):
    """Header metadata for the ACTIVE demo (replaces the HEDIS-only /meta)."""
    demo = demos.active_demo(request)
    m = demos.manifests()[demo]
    base = {
        "demo_id": demo,
        "display_name": m["display_name"],
        "arm": ARM,
        "catalog": CATALOG,
        "context_release": CONTEXT_RELEASE,
        "synthetic": True,
        "disclaimer": m["disclaimer"],
    }
    if demo == "healthcare_hedis":
        base["measurement_year"] = MEASUREMENT_YEAR
    return base


@router.get("/readiness")
def get_readiness(request: Request, refresh: bool = False, all_demos: bool = False):
    if all_demos:
        return {"demos": [readiness(d, refresh) for d in demos.manifests()]}
    return readiness(demos.active_demo(request), refresh)
