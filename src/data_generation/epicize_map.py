"""Crosswalk SNOMED dx -> ICD-10-CM and shape raw Synthea into Clarity-like bronze tables.

Serverless spark task (reads raw_synthea_* tables written by generate_synthea). The crosswalk CSV is read
from the bundle files (src/terminology/snomed_icd10_crosswalk.csv). Writes bronze_* tables into
<catalog>.<schema>. Tracer injection + full measure logic come in P2.
"""
import argparse
import os

import pandas as pd
from pyspark.sql import SparkSession, functions as F


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", default="eli_test_classic_catalog")
    p.add_argument("--schema", default="care_protocol")
    p.add_argument("--src_dir", default=os.getcwd())  # dir holding snomed_icd10_crosswalk.csv
    args = p.parse_args()

    spark = SparkSession.builder.getOrCreate()
    t = f"{args.catalog}.{args.schema}"

    def raw(name: str):
        return spark.table(f"{t}.raw_synthea_{name}")

    cw = spark.createDataFrame(
        pd.read_csv(os.path.join(args.src_dir, "snomed_icd10_crosswalk.csv"), dtype=str)
    ).select(F.col("snomed_code"), F.col("icd10_code"))

    # bronze_patient
    raw("patients").select(
        F.col("Id").alias("patient_id"),
        F.to_date("BIRTHDATE").alias("birth_date"),
        F.to_date("DEATHDATE").alias("death_date"),
        F.col("GENDER").alias("sex"),
        F.col("FIRST").alias("first_name"), F.col("LAST").alias("last_name"),
    ).write.mode("overwrite").option("overwriteSchema", True).saveAsTable(f"{t}.bronze_patient")

    # bronze_pat_enc
    raw("encounters").select(
        F.col("Id").alias("encounter_id"), F.col("PATIENT").alias("patient_id"),
        F.to_timestamp("START").alias("start_ts"), F.to_timestamp("STOP").alias("stop_ts"),
        F.col("ENCOUNTERCLASS").alias("encounter_class"), F.col("DESCRIPTION").alias("description"),
    ).write.mode("overwrite").option("overwriteSchema", True).saveAsTable(f"{t}.bronze_pat_enc")

    # bronze_pat_enc_dx  (SNOMED -> ICD-10-CM; unmapped stays null = a deliberate data gap)
    cond = raw("conditions").select(
        F.col("PATIENT").alias("patient_id"), F.col("ENCOUNTER").alias("encounter_id"),
        F.to_date("START").alias("onset_date"), F.col("CODE").cast("string").alias("snomed_code"),
        F.col("DESCRIPTION").alias("description"),
    )
    cond.join(cw, "snomed_code", "left").write.mode("overwrite").option(
        "overwriteSchema", True).saveAsTable(f"{t}.bronze_pat_enc_dx")

    # bronze_order_results  (observations; LOINC in CODE)
    raw("observations").select(
        F.col("PATIENT").alias("patient_id"), F.col("ENCOUNTER").alias("encounter_id"),
        F.to_timestamp("DATE").alias("result_ts"), F.col("CODE").cast("string").alias("loinc_code"),
        F.col("DESCRIPTION").alias("description"), F.col("VALUE").alias("value"), F.col("UNITS").alias("units"),
    ).write.mode("overwrite").option("overwriteSchema", True).saveAsTable(f"{t}.bronze_order_results")

    # bronze_order_med  (medications; RxNorm in CODE)
    raw("medications").select(
        F.col("PATIENT").alias("patient_id"), F.col("ENCOUNTER").alias("encounter_id"),
        F.to_timestamp("START").alias("start_ts"), F.to_timestamp("STOP").alias("stop_ts"),
        F.col("CODE").cast("string").alias("rxnorm_code"), F.col("DESCRIPTION").alias("description"),
    ).write.mode("overwrite").option("overwriteSchema", True).saveAsTable(f"{t}.bronze_order_med")

    # tracer_registry (stub; populated with planted-tracer expectations in P2)
    spark.sql(
        f"CREATE TABLE IF NOT EXISTS {t}.tracer_registry "
        f"(tracer_id STRING, narrative STRING, patient_id STRING, layer STRING, expected STRING) "
        f"COMMENT 'Planted tracer expectations per layer (populated in P2).'")

    print("epicize complete:", [x.name for x in spark.catalog.listTables(t) if x.name.startswith("bronze_")])


if __name__ == "__main__":
    main()
