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
        # One COMMENT statement per line. Drop blanks + '--' comment lines; strip a trailing ';'.
        # Line-based (not split-on-';') so a ';' inside comment text can't break statements.
        stmts = []
        for ln in text.splitlines():
            s = ln.strip()
            if not s or s.startswith("--"):
                continue
            stmts.append(s.rstrip(";").strip())
        print(f"{os.path.basename(path)}: {len(stmts)} statement(s)")
        for stmt in stmts:
            # Best-effort: a COMMENT whose target table/column does not exist yet (e.g. protocol_watch_findings
            # before the watch has run) should warn, not fail the whole job. Comments are idempotent fuel.
            try:
                spark.sql(stmt)  # noqa: F821 (spark provided by the serverless runtime)
                total += 1
            except Exception as e:  # noqa: BLE001
                print(f"  SKIP ({type(e).__name__}): {stmt[:100]}")

    print(f"Applied {total} comment statement(s) across {len(files)} file(s).")


if __name__ == "__main__":
    main()
