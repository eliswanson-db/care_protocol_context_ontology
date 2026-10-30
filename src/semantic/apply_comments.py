"""Apply column-level UC comments from committed *.comments.sql files (serverless task).

Reproducible-by-code: the COMMENT ON COLUMN statements live in src/semantic/comments/*.comments.sql
(source of truth). This task substitutes {catalog} and runs each statement via spark.sql. COMMENT ON
overwrites, so re-runs are idempotent. These comments are indexed by the Genie Ontology.

Run order: AFTER the `measures` pipeline (silver/gold must exist). See resources/jobs.yml (semantic job).
"""
import argparse
import glob
import os


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--src_dir", required=True, help="Dir holding *.comments.sql (workspace file path).")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.src_dir, "*.comments.sql")))
    if not files:
        raise SystemExit(f"No *.comments.sql files found in {args.src_dir}")

    total = 0
    for path in files:
        with open(path) as f:
            text = f.read().replace("{catalog}", args.catalog)
        # Strip full-line '--' comments FIRST (they may contain ';' or quotes), THEN split on ';'.
        code = "\n".join(ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("--"))
        stmts = [s.strip() for s in code.split(";") if s.strip()]
        print(f"{os.path.basename(path)}: {len(stmts)} statement(s)")
        for stmt in stmts:
            spark.sql(stmt)  # noqa: F821 (spark provided by the serverless runtime)
        total += len(stmts)

    print(f"Applied {total} comment statement(s) across {len(files)} file(s).")


if __name__ == "__main__":
    main()
