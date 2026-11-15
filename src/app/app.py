"""Care Protocol Context — FastAPI entry point.

Read-only app over the shared catalog: it visualizes the semantic throughline (one patient across every
context layer) + (later) the retrieval arena and benchmark scorecard. Serves the built React SPA from
frontend/dist. Net-new React+FastAPI (ADR: app-framework-react-fastapi) so the Arena/Scorecard tabs can
reuse the repo's Python retrieval/benchmark modules.
"""
import os

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from server.demos import require_demo
from server.routes import (
    arena,
    benchmark,
    demos,
    drift,
    genie,
    health,
    ls,
    ontobricks,
    ontology,
    rag,
    retrieval,
    stage_detail,
    tracer,
)

app = FastAPI(title="Care Protocol Context")

# Demo-agnostic: health, the demo list, per-demo meta, readiness.
app.include_router(health.router, prefix="/api")
app.include_router(demos.router, prefix="/api")

# Backend isolation (ADR-0023): every router belongs to exactly one demo; a request whose active demo
# (X-Demo-Id header / ?demo=) doesn't match gets 409, so a tab can't read the other demo's data by accident.
HEDIS = [Depends(require_demo("healthcare_hedis"))]
for r in (tracer, stage_detail, genie, rag, retrieval, ontobricks, benchmark, arena, drift, ontology):
    app.include_router(r.router, prefix="/api", dependencies=HEDIS)
app.include_router(ls.router, prefix="/api", dependencies=[Depends(require_demo("life_sciences_clinical"))])

_frontend = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.isdir(_frontend):
    app.mount("/assets", StaticFiles(directory=os.path.join(_frontend, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate = os.path.join(_frontend, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(_frontend, "index.html"))
