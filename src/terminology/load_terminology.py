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
    # Catalog + schemas are created declaratively by the bundle (resources/schemas.yml).

    loads = {
        "icd10cm_subset.csv": "icd10_hier",
        "loinc_subset.csv": "loinc",
        "rxnorm_statins.csv": "rxnorm_statin",
        "rxnorm_hier.csv": "rxnorm_hier",
        "loinc_parts.csv": "loinc_parts",
        "value_sets_demo.csv": "value_set_segment",
    }
    comments = {
        "icd10_hier": "ICD-10-CM adjacency list (code, parent_code, name). Source tree for icd10_closure. Curated demo subset (diabetes), ADR-0007.",
        "loinc": "LOINC code subset (loinc_code, long_common_name, concept) for demo measures: A1c, eGFR, uACR, BP, BMI, PHQ. LOINC (c) Regenstrief, used under LOINC License.",
        "rxnorm_statin": "RxNorm statin ingredients (rxcui, ingredient) for the Statin Therapy (SPD) measure.",
        "rxnorm_hier": "RxNorm adjacency (code, parent_code, name): statin ingredient -> clinical drug. Source tree for rxnorm_closure, so SPD resolves ingredient value sets to the clinical-drug codes actually prescribed (subsumption). Curated demo subset, ADR-0007.",
        "loinc_parts": "LOINC multiaxial Part edges (loinc_code, predicate, part): typed axes has_component/has_system/has_method. A graph (not a tree): 'all A1c regardless of method' = terms sharing Component LP-HBA1C. Curated demo subset (LOINC License), ADR-0010.",
        "value_set_segment": "Cross-branch demo value sets / cohorts (the segment table; not NCQA/VSAC). Named sets spanning the hierarchy, incl. CARDIORENAL_COHORT (diabetes+CKD+HF).",
    }
    for csv_name, table in loads.items():
        path = os.path.join(args.src_dir, csv_name)  # local FS or /Workspace FUSE path
        df = spark.createDataFrame(pd.read_csv(path, dtype=str))
        fqn = f"{args.catalog}.{args.schema}.{table}"
        df.write.mode("overwrite").option("overwriteSchema", True).saveAsTable(fqn)
        safe_comment = comments[table].replace("'", "''")  # escape single quotes for the SQL string literal
        spark.sql(f"COMMENT ON TABLE {fqn} IS '{safe_comment}'")
        print(f"loaded {df.count():>4} rows -> {fqn}")


if __name__ == "__main__":
    main()
