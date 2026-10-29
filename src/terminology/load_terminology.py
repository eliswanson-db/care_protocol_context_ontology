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

import pandas as pd
from pyspark.sql import SparkSession


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", default=os.environ.get("CATALOG", "care_protocol_ontology"))
    p.add_argument("--schema", default=os.environ.get("SCHEMA", "care_protocol"))
    # Default src dir: this file's directory for local runs; jobs pass --src_dir explicitly.
    default_src = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
    p.add_argument("--src_dir", default=default_src)
    args = p.parse_args()

    spark = SparkSession.builder.getOrCreate()
    # Catalog is pre-created (ECT Default Storage blocks SQL catalog creation; ADR-0001).
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {args.catalog}.{args.schema}")

    loads = {
        "icd10cm_subset.csv": "icd10_hier",
        "loinc_subset.csv": "loinc",
        "rxnorm_statins.csv": "rxnorm_statin",
        "value_sets_demo.csv": "value_set_segment",
    }
    for csv_name, table in loads.items():
        path = os.path.join(args.src_dir, csv_name)  # local FS or /Workspace FUSE path
        df = spark.createDataFrame(pd.read_csv(path, dtype=str))
        fqn = f"{args.catalog}.{args.schema}.{table}"
        df.write.mode("overwrite").option("overwriteSchema", True).saveAsTable(fqn)
        print(f"loaded {df.count():>4} rows -> {fqn}")


if __name__ == "__main__":
    main()
