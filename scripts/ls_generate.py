"""Bundle task: generate the synthetic EDC exports into the raw_edc volume (ADR-0024). SYNTHETIC data only.

Overwrites the landing folder for the chosen scale/seed (exports are regenerated deterministically, so a rerun
with the same seed reproduces the same bytes). It never touches bronze/silver/gold tables.
"""

import argparse
import json
import sys

from pyspark.sql import SparkSession


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src_dir", required=True, help="Workspace path of the repo's src/ directory")
    ap.add_argument("--out", required=True, help="/Volumes/<catalog>/clinical_study/raw_edc/current")
    ap.add_argument("--scale", default="demo", choices=["small", "demo"])
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()
    sys.path.insert(0, a.src_dir)
    from clinical_study.generate import generate

    spark = SparkSession.builder.getOrCreate()
    print(json.dumps(generate(spark, a.out, a.scale, a.seed), indent=2))


if __name__ == "__main__":
    main()
