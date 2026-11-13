"""Bundle task: verify deployed gold tables against the hand-authored oracles; record the outcome.

Fails the job (non-zero exit) on any mismatch so a broken refresh is visible, never silently "ready".
Writes one row per run to clinical_study.gold_verification_run (read by the readiness view).
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from pyspark.sql import SparkSession


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--schema", default="clinical_study")
    ap.add_argument("--src_dir", required=True)
    a = ap.parse_args()
    sys.path.insert(0, a.src_dir)
    from clinical_study.verify import check_named

    spark = SparkSession.builder.getOrCreate()
    t = f"{a.catalog}.{a.schema}"
    fixtures = Path(a.src_dir).parent / "tests" / "fixtures" / "life_sciences"
    errs = check_named(
        spark.table(f"{t}.gold_endpoint_result"),
        spark.table(f"{t}.gold_endpoint_candidate"),
        spark.table(f"{t}.gold_participant_population"),
        spark.table(f"{t}.silver_vs"),
        fixtures,
    )
    run_id = spark.table(f"{t}.gold_endpoint_result").select("execution_run_id").limit(1).collect()[0][0]
    row = [
        (
            run_id,
            datetime.now(timezone.utc).isoformat(),
            "PASS" if not errs else "FAIL",
            len(errs),
            "\n".join(errs[:50]),
        )
    ]
    (
        spark.createDataFrame(
            row, "execution_run_id string, verified_at string, status string, n_failures int, failures string"
        )
        .write.mode("append")
        .saveAsTable(f"{t}.gold_verification_run")
    )
    for e in errs:
        print("FAIL", e)
    if errs:
        raise SystemExit(f"gold oracle check FAILED: {len(errs)} mismatch(es) for {run_id}")
    print(f"gold oracle check PASS for {run_id}")


if __name__ == "__main__":
    main()
