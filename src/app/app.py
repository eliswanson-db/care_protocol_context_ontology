"""Care Protocol Context — FastAPI entry point.

Read-only app over the shared catalog: it visualizes the semantic throughline (one patient across every
context layer) + (later) the retrieval arena and benchmark scorecard. Serves the built React SPA from
frontend/dist. Net-new React+FastAPI (ADR: app-framework-react-fastapi) so the Arena/Scorecard tabs can
reuse the repo's Python retrieval/benchmark modules.
"""
import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from server.routes import genie, health, rag, tracer

app = FastAPI(title="Care Protocol Context")

app.include_router(health.router, prefix="/api")
app.include_router(tracer.router, prefix="/api")
app.include_router(genie.router, prefix="/api")
app.include_router(rag.router, prefix="/api")

_frontend = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.isdir(_frontend):
    app.mount("/assets", StaticFiles(directory=os.path.join(_frontend, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate = os.path.join(_frontend, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(_frontend, "index.html"))
