"""Apply Unity Catalog metric views from committed *.metric_view.sql definitions (serverless task).

Reproducible-by-code: the metric-view DDL lives in src/semantic/metric_views/*.metric_view.sql (source of
truth). This task substitutes {catalog}/{schema}/{semantic_schema} and runs CREATE OR REPLACE VIEW ... WITH
METRICS via spark.sql. Metric-view DDL runs on any compute at DBR 17.3+ (incl. serverless), matching the rest
of our setup stack.

The metric views are created in {semantic_schema} (a separate schema from the base {schema}) while their
`source:` still points at the gold_adherence_* tables in {schema}. Keeping the views out of the base schema
means an ontology/graph scan scoped to {schema} never ingests them (they are a BI/Genie consumption layer,
not base data). See ADR-0013.

Run order: AFTER the `measures` pipeline (metric views read gold_adherence_*). See resources/jobs.yml (semantic job).
"""
import argparse
import glob
import os
import re


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--schema", required=True, help="Base schema holding the gold_adherence_* source tables.")
    ap.add_argument("--semantic_schema", required=True,
                    help="Schema the metric views are created in (kept separate from --schema so an ontology "
                         "scan of the base schema never sees the views). See ADR-0013.")
    ap.add_argument("--src_dir", required=True, help="Dir holding *.metric_view.sql (workspace file path).")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.src_dir, "*.metric_view.sql")))
    if not files:
        raise SystemExit(f"No *.metric_view.sql files found in {args.src_dir}")

    for path in files:
        with open(path) as f:
            # Only {catalog}/{schema}/{semantic_schema} are placeholders; use replace (not .format) so YAML
            # braces survive. Replace {semantic_schema} before {schema} so the longer token wins.
            ddl = (f.read().replace("{catalog}", args.catalog)
                           .replace("{semantic_schema}", args.semantic_schema)
                           .replace("{schema}", args.schema))
        print(f"Applying metric view from {os.path.basename(path)} ...")
        spark.sql(ddl)  # noqa: F821 (spark provided by the serverless runtime)
        # CREATE OR REPLACE VIEW drops the view's tags, so governance is re-applied on every run: the
        # certification system tag + the governed `Clinical Domain` tag (key-only policy). Without this each
        # `semantic` run silently un-certifies every metric view.
        m = re.search(r"CREATE OR REPLACE VIEW\s+([\w.]+)", ddl)
        if m:
            view = m.group(1)
            spark.sql(f"SET TAG ON TABLE {view} `system.certification_status` = `certified`")  # noqa: F821
            spark.sql(f"SET TAG ON TABLE {view} `Clinical Domain`")  # noqa: F821
        print(f"  OK: {os.path.basename(path)} (certified, Clinical Domain)")

    print(f"Applied {len(files)} metric view(s) into {args.catalog}.{args.semantic_schema} "
          f"(sources in {args.catalog}.{args.schema}).")


if __name__ == "__main__":
    main()
