"""Demo registry + backend scoping (ADR-0023, prompt §6/§14).

The active demo travels on every API request as the `X-Demo-Id` header (the SPA sets it; `?demo=` works for
deep links). Routers are bound to ONE demo with `require_demo(...)`: a request whose active demo doesn't
match is refused with 409. Isolation is enforced here, in the backend, not by hoping a prompt or a tab keeps
the demos apart. Requests with no demo default to healthcare_hedis, so existing HEDIS deep links keep
working.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from fastapi import HTTPException, Request

MANIFEST_DIR = Path(__file__).resolve().parent / "demo_manifests"
DEFAULT_DEMO = "healthcare_hedis"
HEADER = "X-Demo-Id"


@lru_cache(maxsize=1)
def manifests() -> dict[str, dict]:
    out = {}
    for p in sorted(MANIFEST_DIR.glob("*.yaml")):
        m = yaml.safe_load(p.read_text(encoding="utf-8"))
        out[m["demo_id"]] = m
    return out


def active_demo(request: Request) -> str:
    demo = request.headers.get(HEADER) or request.query_params.get("demo") or DEFAULT_DEMO
    if demo not in manifests():
        raise HTTPException(400, f"unknown demo {demo!r}; one of {sorted(manifests())}")
    return demo


def require_demo(demo_id: str):
    """FastAPI dependency: the route belongs to `demo_id` only."""

    def dep(request: Request) -> str:
        demo = active_demo(request)
        if demo != demo_id:
            raise HTTPException(
                409, f"this endpoint belongs to demo {demo_id!r}, but the active demo is {demo!r}"
            )
        return demo

    return dep


def public_demos() -> list[dict]:
    return [
        {
            "demo_id": k,
            "display_name": m["display_name"],
            "short_name": m["short_name"],
            "disclaimer": m["disclaimer"],
        }
        for k, m in manifests().items()
    ]
