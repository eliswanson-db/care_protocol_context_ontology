"""App-level demo isolation (ADR-0023), no workspace needed: the scoping dependency runs before any SQL.

- every /api router is bound to exactly one demo, except an explicit demo-agnostic allowlist
- a cross-demo request is refused with 409, an unknown demo with 400
- the app's copies of the life-sciences A6 modules are byte-identical to src/mcp (scripts/sync_app_modules.py)

    python3 -I tests/test_ls_app_isolation.py   (or pytest)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "app"))

from fastapi.testclient import TestClient  # noqa: E402

import app as app_module  # noqa: E402

AGNOSTIC = {"/api/health", "/api/demos", "/api/meta", "/api/readiness"}
client = TestClient(app_module.app)


def _demo_of(dep) -> str | None:
    """The demo a require_demo(...) dependency is bound to (from its closure), or None."""
    if not getattr(dep, "__qualname__", "").startswith("require_demo"):
        return None
    return next((c.cell_contents for c in (dep.__closure__ or ()) if isinstance(c.cell_contents, str)), None)


def api_routes() -> list[tuple[str, list[str]]]:
    """(full path, [demo bindings]) for every /api route. FastAPI 0.16x keeps included routers as
    _IncludedRouter wrappers (no .path), so flatten them; a check over zero routes must not pass."""
    out = []
    for r in app_module.app.routes:
        ctx = getattr(r, "include_context", None)
        if ctx is not None:
            demos = [d for d in (_demo_of(x.dependency) for x in ctx.dependencies) if d]
            for child in ctx.included_router.routes:
                out.append((ctx.prefix + child.path, demos))
        elif getattr(r, "path", "").startswith("/api/"):
            out.append((r.path, [d for d in (_demo_of(x.call) for x in r.dependant.dependencies) if d]))
    return [(p, d) for p, d in out if p.startswith("/api/")]


def test_every_api_route_is_bound_to_one_demo():
    routes = api_routes()
    assert len(routes) > 20, f"found only {len(routes)} routes: the introspection is broken"
    bad = []
    for path, demos in routes:
        if path in AGNOSTIC:
            if demos:
                bad.append((path, "should be demo-agnostic", demos))
        elif len(demos) != 1:
            bad.append((path, "needs exactly one demo binding", demos))
        elif (demos[0] == "life_sciences_clinical") != path.startswith("/api/ls/"):
            bad.append((path, "bound to the wrong demo for its prefix", demos))
    assert not bad, bad


def test_cross_demo_requests_are_refused():
    ls_h = {"X-Demo-Id": "life_sciences_clinical"}
    hedis_h = {"X-Demo-Id": "healthcare_hedis"}
    assert client.get("/api/drift", headers=ls_h).status_code == 409
    assert client.get("/api/ontology/graph", headers=ls_h).status_code == 409
    assert client.get("/api/ls/tracers", headers=hedis_h).status_code == 409
    assert client.get("/api/ls/tracers").status_code == 409  # no header defaults to HEDIS
    assert client.get("/api/ls/overview?demo=healthcare_hedis").status_code == 409
    assert client.get("/api/ls/tracers", headers={"X-Demo-Id": "nope"}).status_code == 400


def test_app_a6_copies_are_identical():
    for f in ("clinical_study_tools.py", "clinical_study_supervisor.py"):
        a = (ROOT / "src/mcp" / f).read_bytes()
        b = (ROOT / "src/app/server/ls_a6" / f).read_bytes()
        assert a == b, f"{f} drifted: run scripts/sync_app_modules.py"



def test_genie_trace_labels_retrieval_by_demo():
    from server.genie_trace import demo_of

    ls = "life_sciences_clinical"
    assert demo_of("Protocol amendments (CSL-A) Week 24 analysis window", "Clinical Domain") == ls
    assert demo_of("eli_test_classic_catalog.clinical_study_semantic.endpoint_result_metrics") == ls
    assert demo_of("Measurement Year", "Clinical Domain") == "healthcare_hedis"  # shared domain, no LS marker
    assert demo_of("care_protocol_semantic.protocol_adherence_metrics: A1c >= 9%") == "healthcare_hedis"
    assert demo_of("Settlement Window", "Fincorp Payments") == "other"


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                fails += 1
                print(f"FAIL {name}: {e}")
    sys.exit(1 if fails else 0)
