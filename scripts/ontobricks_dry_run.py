"""Check an OWL + R2RML pair with Ontobricks itself, before Eli imports it. Nothing is saved anywhere.

Ontobricks reads these files differently from Spark: it takes a map's columns from the SQL text, can't resolve
owl:unionOf, keeps one relationship per (source class, property, target class), and resolves relationship endpoints
by entity. So the only reliable pre-import check is Ontobricks' own. This script opens a fresh, temporary session in
the Ontobricks app (your CLI identity; no domain loaded, so no registry write and no edit lock), and in it:

  1. replaces the session ontology with the OWL           (POST /ontology/parse-owl, the UI's "replace" import)
  2. parses the R2RML and stores the mapping in the session (POST /mapping/parse-r2rml + /mapping/save)
  3. runs Mapping -> Diagnostics                           (GET /mapping/diagnostics)
  4. checks nothing was dropped on parse: every TriplesMap in the file is an entity or relationship in the session
  5. runs every parsed entity / relationship query on ECT and reports its row count (the triples a build makes)
  6. closes the session (POST /domain/close)

Exit code 0 only if diagnostics has no errors or warnings, nothing was dropped, and every query returns rows.

    .venv/bin/python -I scripts/ontobricks_dry_run.py --owl src/ontology/life_sciences/clinical_study.owl.ttl \\
        --r2rml src/ontology/life_sciences/clinical_study.r2rml.ttl
    .venv/bin/python -I scripts/ontobricks_dry_run.py --owl src/ontology/care_protocol.owl.ttl \\
        --r2rml src/ontology/care_protocol.r2rml.ttl
"""

from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import rdflib
import requests

ROOT = Path(__file__).resolve().parents[1]
APP = "https://ontobricks-eli-7474653847172668.aws.databricksapps.com"
RR = rdflib.Namespace("http://www.w3.org/ns/r2rml#")


def _token(profile: str) -> str:
    out = subprocess.run(["databricks", "auth", "token", "--profile", profile, "-o", "json"],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)["access_token"]


def _q():
    spec = importlib.util.spec_from_file_location("q", ROOT / "scripts/q.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.run


class Session:
    """A fresh Ontobricks app session (own cookie jar). State-changing calls carry the CSRF cookie as a header,
    exactly as the app's own pages do."""

    def __init__(self, app: str, token: str):
        self.app, self.s = app, requests.Session()
        self.s.headers["Authorization"] = f"Bearer {token}"
        self.s.get(f"{app}/mapping/", timeout=60).raise_for_status()  # sets the session + csrf_token cookies

    def get(self, path: str) -> dict:
        r = self.s.get(f"{self.app}{path}", timeout=600)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, body: dict | None = None) -> dict:
        r = self.s.post(f"{self.app}{path}", json=body or {}, timeout=600,
                        headers={"X-CSRF-Token": self.s.cookies.get("csrf_token", "")})
        r.raise_for_status()
        return r.json()


def file_maps(r2rml: Path) -> list[dict]:
    g = rdflib.Graph().parse(r2rml)
    out = []
    for tm in g.subjects(rdflib.RDF.type, RR.TriplesMap):
        sm = g.value(tm, RR.subjectMap)
        out.append({"name": str(tm).rsplit("#", 1)[-1], "entity": g.value(sm, RR["class"]) is not None,
                    "class": str(g.value(sm, RR["class"]) or ""),
                    "props": sorted(str(g.value(p, RR.predicate)) for p in g.objects(tm, RR.predicateObjectMap)
                                    if g.value(g.value(p, RR.objectMap), RR.template) is not None)})
    return out


def _local(iri: str) -> str:
    return re.split(r"[#/]", iri or "")[-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owl", required=True)
    ap.add_argument("--r2rml", required=True)
    ap.add_argument("--profile", default="ECT")
    ap.add_argument("--app", default=APP)
    ap.add_argument("--no-counts", action="store_true", help="skip running the queries on ECT")
    a = ap.parse_args()
    owl, r2rml = Path(a.owl).read_text(), Path(a.r2rml)

    s = Session(a.app, _token(a.profile))
    info = s.get("/domain/info")
    if info.get("domain_folder") or (info.get("info") or {}).get("status") == "PUBLISHED":
        raise SystemExit(f"fresh session is tied to a domain ({info.get('domain_folder')!r}); not touching it")
    problems: list[str] = []
    try:
        r = s.post("/ontology/parse-owl", {"content": owl})
        if not r.get("success"):
            raise SystemExit(f"parse-owl failed: {r.get('message') or r}")
        print("ontology:", r.get("message") or r.get("stats"))
        r = s.post("/mapping/parse-r2rml", {"content": r2rml.read_text()})
        if not r.get("success"):
            raise SystemExit(f"parse-r2rml failed: {r.get('message') or r}")
        ents, rels = r.get("entities") or [], r.get("relationships") or []
        cfg = s.get("/mapping/load").get("config") or {}
        cfg.update(entities=ents, relationships=rels)
        saved = s.post("/mapping/save", cfg)
        if not saved.get("success"):
            raise SystemExit(f"mapping/save failed: {saved}")
        print(f"mapping: {len(ents)} entities, {len(rels)} relationships parsed")

        # 4. nothing dropped on parse
        fm = file_maps(r2rml)
        want_e = collections.Counter(_local(m["class"]) for m in fm if m["entity"])
        got_e = collections.Counter(_local(e.get("ontology_class") or e.get("class_name")) for e in ents)
        want_r = collections.Counter(_local(p) for m in fm for p in m["props"])  # an entity map's IRI-valued POMs too
        got_r = collections.Counter(_local(x.get("property")) for x in rels)
        for kind, want, got in (("entity", want_e, got_e), ("relationship", want_r, got_r)):
            for k in sorted(set(want) | set(got)):
                if want[k] != got[k]:
                    problems.append(f"parse {kind} {k}: {want[k]} in the file, {got[k]} in Ontobricks")

        # 3. Ontobricks' own diagnostics
        d = s.get("/mapping/diagnostics")
        print("diagnostics:", d.get("summary"))
        for k in ("entities", "relationships", "permissions"):
            for x in d.get(k, []):
                if x.get("status") == "ok":
                    continue
                name = x.get("label") or x.get("table")
                if k == "relationships":
                    name = f"{x.get('source_class')} -{x.get('label')}-> {x.get('target_class')}"
                for c in x.get("checks", [{"check": x.get("check"), "status": x.get("status"),
                                            "detail": x.get("detail")}]):
                    if c.get("status") != "ok":
                        problems.append(f"diagnostics {c['status']}: {name}: {c.get('check')}: "
                                        f"{re.sub(r'n[0-9a-f]{32}b[0-9]+', '<bnode>', c.get('detail') or '')}")

        # 5. what a build would produce
        if not a.no_counts:
            run = _q()
            for kind, items in (("entity", ents), ("relationship", rels)):
                for x in items:
                    sql = x.get("sql_query") or (f"SELECT * FROM {x['table']}" if x.get("table") else None)
                    name = (_local(x.get("ontology_class")) if kind == "entity" else
                            f"{x.get('source_class_label') or _local(x.get('source_class'))} -"
                            f"{_local(x.get('property'))}-> {x.get('target_class_label') or _local(x.get('target_class'))}")
                    try:
                        n = int(run(f"SELECT count(*) AS n FROM ({sql})")[0]["n"])
                    except SystemExit as e:
                        problems.append(f"query fails: {kind} {name}: {e}")
                        continue
                    print(f"  {kind:12} {name:60} {n:>10,} rows")
                    if n == 0:
                        problems.append(f"no rows: {kind} {name}")
    finally:
        s.post("/domain/close")
    print(f"\n{len(problems)} problem(s)")
    for p in problems:
        print("  -", p)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
