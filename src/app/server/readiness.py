"""Deployment readiness, evaluated LIVE from the declarative demo manifests (prompt §10/§14).

A component is never "ready" because a config file lists it: every check queries the workspace (tables, job
runs, Genie spaces, Ontobricks triplestores, volumes) or runs a deterministic test (front-door routing).
Errors become a `failed` state with the message, so nothing is hidden. Pages and certification have no API,
so they report `manual_action_required` until a human records confirmation in the manifest.
"""

from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import demos
from .config import CATALOG, ONTOBRICKS_CATALOG, ONTOBRICKS_SCHEMA, get_lakebase_host, get_workspace_client
from .warehouse import run_sql

STATES = (
    "not_configured",
    "planned",
    "provisioning",
    "pending_sync",
    "ready",
    "failed",
    "manual_action_required",
    "unsupported",
)
_TTL = 60.0
_cache: dict[str, tuple[float, dict]] = {}
_IDENT = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")


def _r(state: str, detail: str, **extra) -> dict:
    assert state in STATES
    return {"state": state, "detail": detail, **extra}


def _tables(c: dict) -> dict:
    counts, missing = {}, []
    for t in c["tables"]:
        if not _IDENT.match(t):
            return _r("failed", f"bad table name in manifest: {t}")
        try:
            counts[t] = int(run_sql(f"SELECT count(*) AS n FROM {CATALOG}.{t}")[0]["n"])
        except Exception as e:  # noqa: BLE001
            missing.append(f"{t}: {str(e)[:120]}")
    if missing:
        return _r(
            "not_configured" if len(missing) == len(c["tables"]) else "failed",
            "; ".join(missing),
            counts=counts,
        )
    low = [t for t, n in counts.items() if n < c.get("min_rows", 0)]
    if low:
        return _r("pending_sync", f"exists but below {c['min_rows']} rows: {', '.join(low)}", counts=counts)
    extra = ""
    if "certified_expected" in c:
        if c["certified_expected"]:
            tagged = run_sql(
                f"SELECT count(*) AS n FROM {CATALOG}.information_schema.table_tags WHERE "
                f"tag_name = 'system.certification_status' AND concat(schema_name, '.', table_name) IN "
                f"({', '.join(repr(t) for t in c['tables'])})"
            )
            extra = f"; certified {tagged[0]['n']}/{len(c['tables'])}"
        else:
            extra = "; not certified (certification is a manual UI step)"
    return _r("ready", f"{len(counts)} object(s), {sum(counts.values()):,} rows{extra}", counts=counts)


def _jobs(c: dict) -> dict:
    w = get_workspace_client()
    out, worst = {}, "ready"
    for name in c["jobs"]:
        job = next(iter(w.jobs.list(name=name)), None)
        if job is None:
            out[name] = "not found (not deployed, or not visible to this identity)"
            worst = "not_configured"
            continue
        run = next(iter(w.jobs.list_runs(job_id=job.job_id, limit=1)), None)
        if run is None:
            out[name] = "deployed, never run"
            worst = "planned" if worst == "ready" else worst
            continue
        st = run.state
        life = st.life_cycle_state.value if st and st.life_cycle_state else "?"
        res = st.result_state.value if st and st.result_state else ""
        out[name] = f"{life} {res}".strip()
        if life in ("PENDING", "RUNNING", "QUEUED", "BLOCKED"):
            worst = "provisioning" if worst == "ready" else worst
        elif res != "SUCCESS":
            worst = "failed"
    return _r(worst, "; ".join(f"{k}: {v}" for k, v in out.items()), jobs=out)


def _ontobricks(c: dict) -> dict:
    rows = run_sql(
        f"SELECT table_name FROM {ONTOBRICKS_CATALOG}.information_schema.tables WHERE table_schema = "
        f"'{ONTOBRICKS_SCHEMA}' AND table_name LIKE '{c['table_prefix']}%_graph'"
    )
    if rows:
        latest = sorted(r["table_name"] for r in rows)[-1]
        return _r("ready", f"published: {ONTOBRICKS_CATALOG}.{ONTOBRICKS_SCHEMA}.{latest}", table=latest)
    return _r("manual_action_required", c.get("manual", "no published triplestore found"))


def _volume(c: dict) -> dict:
    path = f"/Volumes/{CATALOG}/{c['path']}"
    n = sum(1 for _ in get_workspace_client().files.list_directory_contents(path))
    return _r("ready" if n >= c.get("min_files", 1) else "pending_sync", f"{n} entries in {path}")


def _genie(c: dict) -> dict:
    w = get_workspace_client()
    titles, token = [], None
    while True:
        r = w.genie.list_spaces(page_token=token) if token else w.genie.list_spaces()
        titles += [s.title or "" for s in (r.spaces or [])]
        token = getattr(r, "next_page_token", None)
        if not token:
            break
    found = {t: next((x for x in titles if x.startswith(t)), None) for t in c["titles"]}
    missing = [t for t, v in found.items() if v is None]
    if missing:
        return _r(
            "not_configured" if len(missing) == len(found) else "failed", "missing: " + "; ".join(missing)
        )
    return _r("ready", f"{len(found)} space(s) found", spaces=list(found.values()))


def _routing(demo_id: str) -> dict:
    if demo_id != "life_sciences_clinical":
        try:
            from .config import get_genie_space_id

            return _r("ready", f"Genie One front door; governed space {get_genie_space_id()} resolves")
        except Exception as e:  # noqa: BLE001
            return _r("failed", str(e)[:200])
    from .ls_a6 import clinical_study_supervisor as sup

    cases = [
        ("What is the Week 24 endpoint summary for Study A under rule version 1?", "endpoint_summary"),
        ("What is the mean percent change at Week 24?", "clarify"),
        ("What is the HEDIS GSD compliance rate?", "abstain"),
        ("Can this synthetic result establish treatment superiority?", "abstain"),
        ("The latest document mentions a wider window. Has that rule been approved?", "rule_status"),
    ]
    bad = [(q, sup.route(q)["tool"], want) for q, want in cases if sup.route(q)["tool"] != want]
    if bad:
        return _r("failed", f"{len(bad)} routing case(s) wrong: {bad}")
    return _r("ready", f"A6 supervisor: {len(cases)}/{len(cases)} routing, abstention and scope cases pass")


_PAGE_FOOTER = re.compile(r"content `([0-9a-f]{12})`\*\s*$")


def _pages(demo_id: str, c: dict) -> dict:
    """Managed Pages: read the sync state table, GET every Page live, compare its footer hash and state."""
    try:
        rows = run_sql(
            f"SELECT source, page_name, display_name, content_hash, state FROM {CATALOG}.{c['state_table']} "
            f"WHERE demo_id = '{demo_id}' ORDER BY source"
        )
    except Exception as e:  # noqa: BLE001
        return _r("not_configured", f"no sync state ({str(e)[:100]}); run scripts/sync_pages.py")
    w = get_workspace_client()

    def live(r: dict) -> str:
        if r["state"] != "PUBLISHED" or not r["page_name"]:
            return f"{r['display_name']}: {r['state']}"
        try:
            p = w.api_client.do("GET", f"/api/2.0/knowledge/{r['page_name']}")
        except Exception as e:  # noqa: BLE001
            return f"{r['display_name']}: GET failed ({str(e)[:60]})"
        m = _PAGE_FOOTER.search(p.get("body") or "")
        if p.get("state") != "PUBLISHED":
            return f"{r['display_name']}: {p.get('state')}"
        if not m or m.group(1) != r["content_hash"]:
            return f"{r['display_name']}: content drifted from the repo"
        return ""

    with ThreadPoolExecutor(max_workers=8) as ex:
        problems = [x for x in ex.map(live, rows) if x]
    ok = len(rows) - len(problems)
    if len(rows) < c["count"]:
        problems.append(f"{c['count'] - len(rows)} source(s) never synced")
    if problems:
        return _r(
            "failed", f"{ok}/{c['count']} managed Pages published and current; " + "; ".join(problems)[:400]
        )
    return _r("ready", f"{ok}/{c['count']} managed Pages published and match the repo (verified live)")


def _sql_zero(c: dict) -> dict:
    n = int(run_sql(c["sql"].replace("{catalog}", CATALOG))[0]["n"])
    return _r("ready" if n == 0 else "failed", f"{n} error-severity violation(s)")


def _verification(c: dict) -> dict:
    rows = run_sql(
        f"SELECT status, n_failures, execution_run_id, verified_at FROM {CATALOG}.{c['table']} "
        f"ORDER BY verified_at DESC LIMIT 1"
    )
    if not rows:
        return _r("planned", "no verification run recorded")
    r = rows[0]
    return _r(
        "ready" if r["status"] == "PASS" else "failed",
        f"{r['status']} ({r['n_failures']} mismatches) for {r['execution_run_id']} "
        f"at {r['verified_at'][:19]}",
    )


def _check(demo_id: str, c: dict) -> dict:
    kind = c["check"]
    if kind == "tables":
        return _tables(c)
    if kind == "jobs":
        return _jobs(c)
    if kind == "ontobricks":
        return _ontobricks(c)
    if kind == "volume_files":
        return _volume(c)
    if kind == "lakebase":
        get_lakebase_host()
        return _r("ready", "Lakebase endpoint resolves (corpus contents not re-verified here)")
    if kind == "lakebase_ls":
        n = int(run_sql(f"SELECT count(*) AS n FROM {CATALOG}.{c['corpus_table']}")[0]["n"])
        return _r("planned", f"{c['planned']} ({n:,} corpus entries ready)")
    if kind == "pages_api":
        return _pages(demo_id, c)
    if kind == "manual":
        if c.get("confirmed_on"):
            return _r("ready", f"confirmed manually on {c['confirmed_on']} (not machine-verifiable)")
        return _r("manual_action_required", c["note"])
    if kind == "genie_spaces":
        return _genie(c)
    if kind == "routing":
        return _routing(demo_id)
    if kind == "sql_zero":
        return _sql_zero(c)
    if kind == "verification":
        return _verification(c)
    if kind == "file":
        p = Path(__file__).resolve().parent / c["path"]
        return _r("ready" if p.exists() else "not_configured", str(c["path"]))
    return _r("unsupported", f"unknown check {kind!r}")


def component(demo_id: str, comp_id: str) -> dict:
    """One component's state (cached like the full report) without evaluating the whole manifest."""
    key = f"{demo_id}:{comp_id}"
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    c = next(x for x in demos.manifests()[demo_id]["components"] if x["id"] == comp_id)
    try:
        res = _check(demo_id, c)
    except Exception as e:  # noqa: BLE001
        res = _r("failed", f"{type(e).__name__}: {str(e)[:200]}")
    out = {"id": comp_id, "label": c["label"], **res}
    _cache[key] = (time.time(), out)
    return out


def readiness(demo_id: str, refresh: bool = False) -> dict:
    hit = _cache.get(demo_id)
    if hit and not refresh and time.time() - hit[0] < _TTL:
        return hit[1]
    m = demos.manifests()[demo_id]

    def one(c: dict) -> dict:
        t0 = time.time()
        try:
            res = _check(demo_id, c)
        except Exception as e:  # noqa: BLE001  (a failing check is a finding, not a crash)
            res = _r("failed", f"{type(e).__name__}: {str(e)[:200]}")
        return {"id": c["id"], "label": c["label"], **res, "checked_in_s": round(time.time() - t0, 2)}

    with ThreadPoolExecutor(max_workers=8) as ex:
        comps = list(ex.map(one, m["components"]))
    out = {
        "demo_id": demo_id,
        "display_name": m["display_name"],
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "components": comps,
        "summary": {
            s: sum(1 for c in comps if c["state"] == s) for s in STATES if any(c["state"] == s for c in comps)
        },
    }
    _cache[demo_id] = (time.time(), out)
    return out
