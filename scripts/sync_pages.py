"""Sync Pages from repo markdown to the Pages API (content-as-code; replaces manual Genie Code bulk import).

    .venv/bin/python -I scripts/sync_pages.py --profile ECT --demo life_sciences_clinical --dry-run
    .venv/bin/python -I scripts/sync_pages.py --profile ECT --demo healthcare_hedis

Rules:
- A Page is MANAGED when its body ends with the footer this script writes (source file + content hash). The
  script only ever updates managed Pages. It never edits or deletes a Page it didn't create.
- Matching is by source file (from the footer), so renaming a Page's title in markdown updates it in place.
- Create / update / publish only when the content hash differs (idempotent; re-runs are no-ops).
- Every UNMANAGED Page in the same domain is flagged in a report (never touched): exact-title duplicates,
  older versions of a managed topic, or unrelated. Deciding what to do with them is a human step.
- Writes <catalog>.<schema>.pages_sync_state (one row per managed Page) so readiness can GET each Page live
  and compare its hash.

The Pages API has no related_assets/sources fields, so frontmatter `related_assets` go into the body as text.
API: GET/POST /api/2.0/knowledge/pages, PATCH/DELETE /api/2.0/knowledge/pages/{id} (update_mask required).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml
from databricks.sdk import WorkspaceClient

try:
    ROOT = Path(__file__).resolve().parents[1]
except NameError:  # serverless spark_python_task runs without __file__: pass --repo_dir
    ROOT = Path.cwd()
DEMOS = {
    "healthcare_hedis": {"src": "docs/ontology/pages", "state_table": "care_protocol.pages_sync_state"},
    "life_sciences_clinical": {
        "src": "docs/life_sciences/pages",
        "state_table": "clinical_study.pages_sync_state",
    },
}
FOOTER_RE = re.compile(
    r"\n\n---\n\*Managed by scripts/sync_pages\.py · source `([^`]+)` · content `([0-9a-f]{12})`\*\s*$"
)


def parse_source(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---\n"):
        raise ValueError(f"{path}: missing frontmatter")
    fm, body = raw[4:].split("\n---\n", 1)
    meta = yaml.safe_load(fm)
    body = body.strip()
    assets = meta.get("related_assets") or []
    if assets:
        body += "\n\n**Related assets:** " + ", ".join(f"`{a}`" for a in assets)
    first = re.split(r"\n\s*\n", body, maxsplit=1)[0]
    desc = re.sub(r"[*_`#>|]", "", " ".join(first.split()))
    desc = desc if len(desc) <= 300 else desc[:297].rsplit(" ", 1)[0] + "..."
    syn = sorted({str(s).strip()[:200] for s in (meta.get("synonyms") or []) if str(s).strip()})[:50]
    page = {
        "display_name": meta["name"][:200],
        "description": meta.get("description") or desc,
        "synonyms": syn,
        "body": body,
    }
    h = hashlib.sha256(json.dumps(page, sort_keys=True).encode()).hexdigest()[:12]
    rel = str(path.relative_to(ROOT))
    page["body"] = f"{body}\n\n---\n*Managed by scripts/sync_pages.py · source `{rel}` · content `{h}`*"
    return {"source": rel, "domain_name": meta["domain"], "hash": h, "page": page}


def topic_key(title: str) -> str:
    """'BPD — Blood Pressure ...' and 'BPD (Blood Pressure Control)' -> 'bpd'."""
    return re.split(r"\s+[—(–-]\s*|\s+\(", title.strip(), maxsplit=1)[0].strip().lower()


class Pages:
    def __init__(self, w: WorkspaceClient):
        self.w = w

    def list_domain(self, domain: str) -> list[dict]:
        out, tok = [], None
        while True:
            r = self.w.api_client.do(
                "GET",
                "/api/2.0/knowledge/pages",
                query={"page_size": 100, **({"page_token": tok} if tok else {})},
            )
            out += [p for p in r.get("pages", []) if p.get("domain") == domain]
            tok = r.get("next_page_token")
            if not tok:
                return out

    def get(self, name: str) -> dict:
        return self.w.api_client.do("GET", f"/api/2.0/knowledge/{name}")

    def create(self, domain: str, page: dict) -> dict:
        return self.w.api_client.do(
            "POST", "/api/2.0/knowledge/pages", body={"domain": domain, **page, "state": "PUBLISHED"}
        )

    def update(self, name: str, page: dict) -> dict:
        mask = "display_name,description,synonyms,body,state"
        return self.w.api_client.do(
            "PATCH",
            f"/api/2.0/knowledge/{name}",
            query={"update_mask": mask},
            body={**page, "state": "PUBLISHED"},
        )


def resolve_domain(w: WorkspaceClient, name: str) -> str:
    r = w.api_client.do("GET", "/api/2.0/domains")
    doms = r.get("domains", r) if isinstance(r, dict) else r
    tok = r.get("next_page_token") if isinstance(r, dict) else None
    while tok:
        nxt = w.api_client.do("GET", "/api/2.0/domains", query={"page_token": tok})
        doms += nxt.get("domains", [])
        tok = nxt.get("next_page_token")
    hit = [d for d in doms if d.get("tag_key") == name or d.get("name") == name]
    if len(hit) != 1:
        raise SystemExit(f"domain {name!r}: {len(hit)} matches")
    return f"domains/{hit[0]['domain_id']}"


def write_state(w: WorkspaceClient, catalog: str, table: str, demo: str, rows: list[dict]) -> None:
    wh = next(x.id for x in w.warehouses.list() if x.name == "Serverless Starter Warehouse")

    def sql(s: str) -> None:
        r = w.statement_execution.execute_statement(warehouse_id=wh, statement=s, wait_timeout="50s")
        if r.status.state.value != "SUCCEEDED":
            raise SystemExit(f"state table write failed: {r.status.error.message if r.status.error else ''}")

    fq = f"{catalog}.{table}"
    sql(
        f"CREATE TABLE IF NOT EXISTS {fq} (demo_id string, source string, page_name string, "
        f"display_name string, "
        f"content_hash string, state string, synced_at string) COMMENT 'Managed Pages written by "
        f"scripts/sync_pages.py; readiness GETs each page_name live and compares content_hash.'"
    )
    sql(f"DELETE FROM {fq} WHERE demo_id = '{demo}'")
    if rows:
        esc = lambda v: "NULL" if v is None else "'" + str(v).replace("'", "''") + "'"  # noqa: E731
        vals = ", ".join(
            "("
            + ", ".join(
                esc(r[k])
                for k in (
                    "demo_id",
                    "source",
                    "page_name",
                    "display_name",
                    "content_hash",
                    "state",
                    "synced_at",
                )
            )
            + ")"
            for r in rows
        )
        sql(f"INSERT INTO {fq} VALUES {vals}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile")
    ap.add_argument("--demo", required=True, choices=sorted(DEMOS))
    ap.add_argument("--catalog", default="eli_test_classic_catalog")
    ap.add_argument("--repo_dir", help="bundle root (jobs: ${workspace.file_path}); default: this checkout")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report", help="write the flag report (markdown) here")
    a = ap.parse_args()
    global ROOT
    if a.repo_dir:
        ROOT = Path(a.repo_dir)
    w = WorkspaceClient(profile=a.profile) if a.profile else WorkspaceClient()
    api = Pages(w)
    cfg = DEMOS[a.demo]
    src_dir = ROOT / cfg["src"]
    sources = [parse_source(p) for p in sorted(src_dir.glob("*.md")) if p.name != "README.md"]
    if not sources:
        raise SystemExit(f"no Page sources in {src_dir}")
    domains = {s["domain_name"] for s in sources}
    if len(domains) != 1:
        raise SystemExit(f"sources span several domains: {domains}")
    domain = resolve_domain(w, domains.pop())
    existing = api.list_domain(domain)
    full = {p["name"]: api.get(p["name"]) for p in existing}
    managed = {}
    for name, p in full.items():
        m = FOOTER_RE.search(p.get("body") or "")
        if m:
            managed[m.group(1)] = (name, m.group(2), p)
    plan, rows, now = [], [], datetime.now(timezone.utc).isoformat()
    for s in sources:
        hit = managed.get(s["source"])
        if hit is None:
            action = "create"
        elif hit[1] != s["hash"] or hit[2].get("state") != "PUBLISHED":
            action = "update"
        else:
            action = "unchanged"
        plan.append((action, s, hit[0] if hit else None))
    for action, s, name in plan:
        print(f"  {action:9} {s['page']['display_name'][:70]:70} {s['source']}")
        if a.dry_run:
            continue
        try:
            if action == "create":
                r = api.create(domain, s["page"])
                name = r["name"]
            elif action == "update":
                api.update(name, s["page"])
        except Exception as e:  # noqa: BLE001
            print(f"    FAILED: {str(e)[:300]}")
            rows.append(
                {
                    "demo_id": a.demo,
                    "source": s["source"],
                    "page_name": name,
                    "display_name": s["page"]["display_name"],
                    "content_hash": s["hash"],
                    "state": f"FAILED: {str(e)[:200]}",
                    "synced_at": now,
                }
            )
            continue
        rows.append(
            {
                "demo_id": a.demo,
                "source": s["source"],
                "page_name": name,
                "display_name": s["page"]["display_name"],
                "content_hash": s["hash"],
                "state": "PUBLISHED",
                "synced_at": now,
            }
        )
        time.sleep(0.2)

    # classify against the sources of EVERY demo that uses this domain (they share Clinical Domain)
    all_sources = {
        d: [parse_source(p) for p in sorted((ROOT / c["src"]).glob("*.md")) if p.name != "README.md"]
        for d, c in DEMOS.items()
    }
    owner_of = {s["page"]["display_name"]: d for d, ss in all_sources.items() for s in ss}
    managed_titles = set(owner_of)
    managed_topics = {topic_key(t): t for t in managed_titles}
    managed_names = {r["page_name"] for r in rows} | {v[0] for v in managed.values()}
    flags = []
    for name, p in sorted(full.items(), key=lambda kv: kv[1]["display_name"]):
        if name in managed_names or FOOTER_RE.search(p.get("body") or ""):
            continue  # managed by this or another demo's sync
        t = p["display_name"]
        if t in managed_titles:
            kind, of = "duplicate_title", t
        elif topic_key(t) in managed_topics:
            kind, of = "older_version_of_topic", managed_topics[topic_key(t)]
        else:
            kind, of = "unrelated_or_unknown", None
        if kind != "unrelated_or_unknown" or not FOOTER_RE.search(p.get("body") or ""):
            flags.append(
                {
                    "page": name,
                    "title": t,
                    "state": p.get("state"),
                    "updated": (p.get("update_time") or "")[:10],
                    "owner_ids": p.get("owner_ids"),
                    "kind": kind,
                    "managed_counterpart": of,
                    "counterpart_demo": owner_of.get(of) if of else None,
                }
            )
    print(f"\nflagged unmanaged Pages in {domain}: {len(flags)} (not modified)")
    for f in flags:
        print(f"  {f['kind']:24} {f['state']:9} {f['updated']} {f['title'][:70]}")
    if not a.dry_run:
        write_state(w, a.catalog, cfg["state_table"], a.demo, rows)
    if a.report:
        lines = [
            f"# Unmanaged Pages flagged by sync_pages.py ({a.demo})",
            "",
            f"Domain `{domain}`, checked {now[:19]}Z. **None of these were modified.** Managed Pages "
            f"(created by the sync, footer + hash): {len(rows) if not a.dry_run else len(managed)}.",
            "",
            "| Kind | State | Updated | Title | Managed counterpart | Page |",
            "|---|---|---|---|---|---|",
        ]
        lines += [
            f"| {f['kind']} | {f['state']} | {f['updated']} | {f['title']} | "
            f"{f['managed_counterpart'] or '—'}"
            f"{' (' + f['counterpart_demo'] + ')' if f['counterpart_demo'] else ''} | "
            f"`{f['page']}` |"
            for f in flags
        ]
        Path(a.report).write_text("\n".join(lines) + "\n")
        print(f"report: {a.report}")
    failed = [r for r in rows if r["state"].startswith("FAILED")]
    return 1 if failed else 0


if __name__ == "__main__":
    rc = main()
    if rc:  # serverless (IPython) treats any SystemExit, even 0, as a task failure: raise only on failure
        raise SystemExit(rc)
