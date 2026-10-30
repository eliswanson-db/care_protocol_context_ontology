"""Apply Unity Catalog metric views from committed *.metric_view.sql definitions (serverless task).

Reproducible-by-code: the metric-view DDL lives in src/semantic/metric_views/*.metric_view.sql (source of
truth). This task substitutes {catalog}/{schema} and runs CREATE OR REPLACE VIEW ... WITH METRICS via spark.sql.
Metric-view DDL runs on any compute at DBR 17.3+ (incl. serverless), matching the rest of our setup stack.

Run order: AFTER the `measures` pipeline (metric views read gold_adherence_*). See resources/jobs.yml (semantic job).
"""
import argparse
import glob
import os


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--schema", required=True)
    ap.add_argument("--src_dir", required=True, help="Dir holding *.metric_view.sql (workspace file path).")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.src_dir, "*.metric_view.sql")))
    if not files:
        raise SystemExit(f"No *.metric_view.sql files found in {args.src_dir}")

    for path in files:
        with open(path) as f:
            # Only {catalog}/{schema} are placeholders; use replace (not .format) so YAML braces survive.
            ddl = f.read().replace("{catalog}", args.catalog).replace("{schema}", args.schema)
        print(f"Applying metric view from {os.path.basename(path)} ...")
        spark.sql(ddl)  # noqa: F821 (spark provided by the serverless runtime)
        print(f"  OK: {os.path.basename(path)}")

    print(f"Applied {len(files)} metric view(s) into {args.catalog}.{args.schema}.")


if __name__ == "__main__":
    main()
