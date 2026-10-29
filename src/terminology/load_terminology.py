"""Load vendored terminology subsets (this directory's CSVs) into Unity Catalog Delta tables.

Self-contained — reads the committed CSVs, no Drive / external download (ADR-0007).
Run as a Databricks notebook/job (wire into resources/jobs.yml) or with Databricks Connect.

Tables written into ${catalog}.${schema}:
  icd10_hier        <- icd10cm_subset.csv     (adjacency; closure_tables.sql builds icd10_closure from it)
  loinc             <- loinc_subset.csv
  rxnorm_statin     <- rxnorm_statins.csv
  value_set_segment <- value_sets_demo.csv    (seeds the segment table)

After this runs, build the closure: run ../semantic/closure_tables.sql on a SQL warehouse.
"""
import argparse
import os

from pyspark.sql import SparkSession


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", default=os.environ.get("CATALOG", "care_protocol_ontology"))
    p.add_argument("--schema", default=os.environ.get("SCHEMA", "care_protocol"))
    # Default: the directory this file lives in (CSVs deploy alongside it with the bundle).
    p.add_argument("--src_dir", default=os.path.dirname(os.path.abspath(__file__)))
    args = p.parse_args()

    spark = SparkSession.builder.getOrCreate()
    spark.sql(f"CREATE CATALOG IF NOT EXISTS {args.catalog}")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {args.catalog}.{args.schema}")

    loads = {
        "icd10cm_subset.csv": "icd10_hier",
        "loinc_subset.csv": "loinc",
        "rxnorm_statins.csv": "rxnorm_statin",
        "value_sets_demo.csv": "value_set_segment",
    }
    for csv_name, table in loads.items():
        path = f"file:{os.path.join(args.src_dir, csv_name)}"
        df = spark.read.option("header", True).option("inferSchema", True).csv(path)
        fqn = f"{args.catalog}.{args.schema}.{table}"
        df.write.mode("overwrite").option("overwriteSchema", True).saveAsTable(fqn)
        print(f"loaded {df.count():>4} rows -> {fqn}")


if __name__ == "__main__":
    main()
