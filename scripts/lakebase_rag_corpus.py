"""Build the A4 Lakebase RAG serving corpus from the version-controlled care-protocol documents.

Deterministic, reproducible-by-code (ADR-0014): reads the committed corpus — markdown in
docs/care_protocol/corpus/*.md and the HTML care-protocol doc(s) in docs/care_protocol/html/*.html — does
structure-aware chunking that preserves section provenance, and emits idempotent Postgres SQL (to stdout):
INSERTs for rag.documents / rag.chunks / rag.document_acl / rag.group_membership. Pipe into Lakebase AFTER
src/retrieval/lakebase/schema.sql has created the schema:

    EP=projects/care-protocol/branches/production/endpoints/primary
    TOKEN=$(databricks postgres generate-database-credential $EP --profile ECT -o json \
            | python3 -c "import json,sys;print(json.load(sys.stdin)['token'])")
    python scripts/lakebase_rag_corpus.py | \
      PGPASSWORD="$TOKEN" psql "host=<host> user=<you> dbname=databricks_postgres sslmode=require"

Embeddings are added separately (scripts/lakebase_embed.py pattern over rag.chunks) so this step needs no
workspace and is byte-stable — the benchmark tracers stay deterministic. For arbitrary real PDFs the
Databricks-native path is READ_FILES -> ai_parse_document -> ai_prep_search (design doc §6); this local
chunker is the demo's reproducible path over the synthetic corpus.

Document ACLs come from each file's front-matter `access:` list; demo group membership comes from
context/value_set_manifests/rag_access_manifest.yaml. Run with -I (untrusted-input hygiene is irrelevant
here — inputs are our own committed files — but -I keeps it hermetic).
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHUNK_WORDS = 220          # ~500-800 tokens; sections longer than this are split
OVERLAP_WORDS = 30


def sql_str(s: str | None) -> str:
    return "NULL" if s is None else "'" + s.replace("'", "''") + "'"


def sql_int(s) -> str:
    return "NULL" if s in (None, "") else str(int(s))


# ---- front-matter + body parsing ---------------------------------------------------------------
def parse_front_matter(text: str) -> tuple[dict, str]:
    """Parse a simple `key: value` YAML front-matter block (+ one inline list `access: [a, b]`)."""
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return {}, text
    meta: dict = {}
    for line in m.group(1).splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, val = line.split(":", 1)
        key, val = key.strip(), val.strip().strip('"')
        if key == "access":
            meta[key] = [v.strip() for v in val.strip("[]").split(",") if v.strip()]
        elif val in ("null", ""):
            meta[key] = None
        else:
            meta[key] = val
    return meta, m.group(2)


def html_to_sections(html: str) -> list[tuple[str, str]]:
    """Split an HTML doc into (section_path, text) by h1/h2/h3; strip tags. Deterministic."""
    html = re.sub(r"(?is)<style.*?</style>", " ", html)
    parts = re.split(r"(?is)<h[123][^>]*>(.*?)</h[123]>", html)
    sections, heading = [], "Document"
    # parts = [pre, h, body, h, body, ...]
    lead = re.sub(r"(?s)<[^>]+>", " ", parts[0])
    lead = re.sub(r"\s+", " ", lead).strip()
    if lead:
        sections.append(("Preamble", lead))
    for i in range(1, len(parts), 2):
        heading = re.sub(r"(?s)<[^>]+>", " ", parts[i])
        heading = re.sub(r"\s+", " ", heading).strip()
        body = re.sub(r"(?s)<[^>]+>", " ", parts[i + 1]) if i + 1 < len(parts) else ""
        body = re.sub(r"\s+", " ", body).strip()
        if body:
            sections.append((heading, body))
    return sections


def md_to_sections(body: str) -> list[tuple[str, str]]:
    """Split markdown into (section_path, text) by ## / ### headings; drop blockquotes/tables markup lightly."""
    sections, heading, buf = [], "Overview", []
    for line in body.splitlines():
        h = re.match(r"^(#{1,3})\s+(.*)$", line)
        if h:
            if buf:
                sections.append((heading, "\n".join(buf).strip()))
                buf = []
            heading = h.group(2).strip()
        else:
            buf.append(line)
    if buf:
        sections.append((heading, "\n".join(buf).strip()))
    # keep only sections with real prose
    return [(hd, re.sub(r"\n{2,}", "\n", tx).strip()) for hd, tx in sections if tx.strip()]


def chunk_section(text: str) -> list[str]:
    """Split one section into ~CHUNK_WORDS word chunks with small overlap. Deterministic."""
    words = text.split()
    if len(words) <= CHUNK_WORDS:
        return [text.strip()] if text.strip() else []
    chunks, start = [], 0
    while start < len(words):
        chunks.append(" ".join(words[start:start + CHUNK_WORDS]))
        start += CHUNK_WORDS - OVERLAP_WORDS
    return chunks


# ---- manifest (group membership) ---------------------------------------------------------------
def parse_group_membership(path: str) -> dict[str, list[str]]:
    """Parse the `group_membership:` block of the access manifest (two-level: user -> [groups])."""
    if not os.path.exists(path):
        return {}
    lines = open(path).read().splitlines()
    out, in_block, cur = {}, False, None
    for line in lines:
        if re.match(r"^group_membership:\s*$", line):
            in_block = True
            continue
        if in_block:
            if re.match(r"^\S", line):        # dedent to col 0 -> block ended
                break
            u = re.match(r'^\s{2}"?([^":]+)"?:\s*$', line)
            g = re.match(r"^\s{4}-\s*(.+)$", line)
            if u:
                cur = u.group(1).strip()
                out[cur] = []
            elif g and cur is not None:
                out[cur].append(g.group(1).strip().strip('"'))
    return out


# ---- doc loading ---------------------------------------------------------------------------------
def load_docs(corpus_dir: str, html_dir: str) -> list[dict]:
    docs = []
    for path in sorted(glob.glob(os.path.join(corpus_dir, "*.md"))):
        meta, body = parse_front_matter(open(path).read())
        docs.append({"meta": meta, "sections": md_to_sections(body),
                     "hash": hashlib.sha256(body.encode()).hexdigest()[:16], "path": path})
    for path in sorted(glob.glob(os.path.join(html_dir, "*.html"))):
        html = open(path).read()
        title = (re.search(r"(?is)<title>(.*?)</title>", html) or [None, os.path.basename(path)])[1]
        docs.append({"meta": {"doc_id": "CP-DM-2025.1", "title": re.sub(r"\s+", " ", title).strip(),
                              "source": "Synthetic comprehensive diabetes care protocol (lineage anchor).",
                              "license": "synthetic", "measurement_year": "2025",
                              "effective_date": "2025-01-01", "patient_id": None,
                              "access": ["quality_analytics", "care_team"]},
                     "sections": html_to_sections(html),
                     "hash": hashlib.sha256(html.encode()).hexdigest()[:16], "path": path})
    return docs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus_dir", default=os.path.join(REPO, "docs/care_protocol/corpus"))
    ap.add_argument("--html_dir", default=os.path.join(REPO, "docs/care_protocol/html"))
    ap.add_argument("--manifest", default=os.path.join(REPO, "context/value_set_manifests/rag_access_manifest.yaml"))
    ap.add_argument("--emit_demo_roles", action="store_true",
                    help="Also emit NOLOGIN roles for manifest identities + grant to current_user, so the "
                         "negative-security test can SET ROLE to simulate OBO identities (demo only).")
    args = ap.parse_args()

    docs = load_docs(args.corpus_dir, args.html_dir)
    membership = parse_group_membership(args.manifest)

    out = ["-- Generated by scripts/lakebase_rag_corpus.py — do not edit by hand. Idempotent.",
           "BEGIN;"]

    # group membership (seed the authorization table)
    out.append("DELETE FROM rag.group_membership;")
    for user, groups in sorted(membership.items()):
        for g in groups:
            out.append(f"INSERT INTO rag.group_membership (user_id, group_id) VALUES "
                       f"({sql_str(user)}, {sql_str(g)});")

    n_chunks = 0
    for d in docs:
        m = d["meta"]
        doc_id = m["doc_id"]
        out.append(
            "INSERT INTO rag.documents (document_id, title, source, license, measurement_year, "
            "effective_date, supersedes, patient_id, content_hash, active) VALUES ("
            f"{sql_str(doc_id)}, {sql_str(m.get('title'))}, {sql_str(m.get('source'))}, "
            f"{sql_str(m.get('license'))}, {sql_int(m.get('measurement_year'))}, "
            f"{('DATE ' + sql_str(m.get('effective_date'))) if m.get('effective_date') else 'NULL'}, "
            f"{sql_str(m.get('supersedes'))}, {sql_str(m.get('patient_id'))}, {sql_str(d['hash'])}, TRUE) "
            "ON CONFLICT (document_id) DO UPDATE SET title=EXCLUDED.title, source=EXCLUDED.source, "
            "license=EXCLUDED.license, measurement_year=EXCLUDED.measurement_year, "
            "effective_date=EXCLUDED.effective_date, supersedes=EXCLUDED.supersedes, "
            "patient_id=EXCLUDED.patient_id, content_hash=EXCLUDED.content_hash, active=TRUE;")

        # ACLs from front-matter access list (group ALLOW READ)
        out.append(f"DELETE FROM rag.document_acl WHERE document_id = {sql_str(doc_id)};")
        for g in m.get("access", []):
            out.append("INSERT INTO rag.document_acl (document_id, principal_type, principal_id, effect, "
                       f"permission) VALUES ({sql_str(doc_id)}, 'GROUP', {sql_str(g)}, 'ALLOW', 'READ');")

        # chunks (replace this doc's chunks for idempotency; embedding filled in by the embed step)
        out.append(f"DELETE FROM rag.chunks WHERE document_id = {sql_str(doc_id)};")
        pos = 0
        for sec_idx, (section_path, text) in enumerate(d["sections"], start=1):
            for piece in chunk_section(text):
                chunk_id = f"{doc_id}::{pos:04d}"
                tsv = "to_tsvector('english', " + sql_str(piece) + ")"
                out.append(
                    "INSERT INTO rag.chunks (chunk_id, document_id, chunk_position, content, section_path, "
                    "page_start, page_end, body_tsv, active) VALUES ("
                    f"{sql_str(chunk_id)}, {sql_str(doc_id)}, {pos}, {sql_str(piece)}, "
                    f"{sql_str(section_path)}, {sec_idx}, {sec_idx}, {tsv}, TRUE);")
                pos += 1
                n_chunks += 1

    if args.emit_demo_roles:
        out.append("-- Demo-only: simulate OBO identities so the negative-security test can SET ROLE.")
        for user in sorted(membership):
            out.append(f"DO $$ BEGIN CREATE ROLE {sql_ident(user)} NOLOGIN; "
                       "EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
            out.append(f"GRANT {sql_ident(user)} TO CURRENT_USER;")
            out.append(f"GRANT rag_reader TO {sql_ident(user)};")

    out.append("COMMIT;")
    out.append(f"-- documents={len(docs)} chunks={n_chunks} groups={sum(len(v) for v in membership.values())}")
    print("\n".join(out))


def sql_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


if __name__ == "__main__":
    main()
