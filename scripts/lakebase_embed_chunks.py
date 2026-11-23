"""Backfill rag.chunks.embedding — the A4 semantic half — via the governed gte-large-en endpoint (ADR-0014).

Unlike scripts/lakebase_embed.py (which embeds the Pages corpus from version-controlled markdown), the
care-protocol document chunks live IN Postgres (rag.chunks.content). So this reads each chunk from the
Lakebase project, computes a 1024-dim embedding, and writes it back (UPDATE ... WHERE chunk_id=...).

Idempotent: by default embeds only chunks WHERE embedding IS NULL (safe to re-run). Reversible:
`UPDATE rag.chunks SET embedding = NULL;` un-embeds. Run in LOCKSTEP on every workspace's Lakebase project
(Postgres is per-workspace) so the A4 arm stays comparable across ECT (off) and DMVM (on) — ADR-0018.

    # ECT
    python3 -I scripts/lakebase_embed_chunks.py --profile ECT \
        --host ep-spring-paper-d2objaly.database.us-east-1.cloud.databricks.com \
        --user eli.swanson@databricks.com --reindex
    # DMVM (lockstep)
    python3 -I scripts/lakebase_embed_chunks.py --profile DMVM \
        --host ep-divine-wildflower-d2l62zpy.database.us-east-1.cloud.databricks.com \
        --user eli.swanson@databricks.com --reindex

Reproducible-by-code: embeddings derive from the loaded corpus via a governed serving endpoint.
"""
import argparse
import time

import psycopg
from databricks.sdk import WorkspaceClient

EMBED_ENDPOINT = "databricks-gte-large-en"
EP_DEFAULT = "projects/care-protocol/branches/production/endpoints/primary"
ANN_INDEX = "rag.chunks_embedding_ann"
BM25_INDEX = "rag.chunks_body_bm25"  # corpus stats are fixed at build time, so rebuild after a reload


BATCH = 64  # texts per embedding request (one call per chunk made a 7k-chunk load take ~50 minutes)


def embed(w, text):
    return embed_batch(w, [text])[0]


def embed_batch(w, texts):
    r = w.serving_endpoints.query(name=EMBED_ENDPOINT, input=list(texts))
    if getattr(r, "data", None):
        return [d.embedding for d in sorted(r.data, key=lambda d: d.index)]
    return list(r.predictions)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=None)
    ap.add_argument("--host", required=True)
    ap.add_argument("--endpoint", default=EP_DEFAULT)
    ap.add_argument("--user", required=True)
    ap.add_argument("--dbname", default="databricks_postgres")
    ap.add_argument("--all", action="store_true", help="re-embed every chunk (default: only NULL embeddings)")
    ap.add_argument("--reindex", action="store_true", help="REINDEX the ANN and BM25 indexes after backfill")
    ap.add_argument("--dry_run", action="store_true", help="embed + report, write NOTHING")
    args = ap.parse_args()

    w = WorkspaceClient(profile=args.profile) if args.profile else WorkspaceClient()
    token = w.postgres.generate_database_credential(args.endpoint).token
    conn = psycopg.connect(host=args.host, user=args.user, password=token,
                           dbname=args.dbname, sslmode="require")

    where = "" if args.all else "WHERE embedding IS NULL"
    with conn.cursor() as cur:
        cur.execute(f"SELECT chunk_id, content FROM rag.chunks {where} ORDER BY chunk_id")
        rows = cur.fetchall()
    print(f"[{args.profile or 'app'}] chunks to embed: {len(rows)}")

    t0, dim = time.time(), None
    for i in range(0, len(rows), BATCH):
        batch = rows[i:i + BATCH]
        vecs = embed_batch(w, [c or "" for _, c in batch])
        assert len(vecs) == len(batch), (len(vecs), len(batch))
        dim = dim or len(vecs[0])
        params = [("[" + ",".join(f"{x:.6f}" for x in v) + "]", cid) for (cid, _), v in zip(batch, vecs)]
        if not args.dry_run:
            with conn.cursor() as cur:
                cur.executemany("UPDATE rag.chunks SET embedding = %s::vector WHERE chunk_id = %s", params)

    if args.dry_run:
        conn.rollback()
        print(f"dry run: embedded {len(rows)} chunks (dim {dim}); wrote nothing ({round(time.time() - t0, 1)}s)")
        conn.close()
        return

    conn.commit()
    if args.reindex and rows:
        conn.autocommit = True  # REINDEX CONCURRENTLY cannot run inside a transaction block
        with conn.cursor() as cur:
            for ix in (ANN_INDEX, BM25_INDEX):
                cur.execute(f"REINDEX INDEX CONCURRENTLY {ix}")
        conn.autocommit = False

    with conn.cursor() as cur:
        cur.execute("SELECT count(embedding) AS n FROM rag.chunks")
        total = cur.fetchone()[0]
    print(f"[{args.profile or 'app'}] committed {len(rows)} embeddings (dim {dim}); "
          f"rag.chunks now has {total} embedded ({round(time.time() - t0, 1)}s)")
    conn.close()


if __name__ == "__main__":
    main()
