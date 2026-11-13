"""Bronze -> SDTM-shaped silver transforms (SYNTHETIC demo; ADR-0024). Pure functions over DataFrames.

The Lakeflow pipeline (src/pipelines/clinical_study.py) wraps these in materialized views; tests run them on
local Spark against generated data. "SDTM-shaped" = SDTM variable names and CDISC CT values for the selected
scope (DM, VS, EX, MH, CM, DS, SV). It is not a conformant, submission-ready SDTM implementation:
MH/CM coding uses MONDO / RxNorm (not MedDRA / WHODrug), carried in demo-extension columns prefixed CPL_.
"""

from __future__ import annotations

from itertools import chain

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F

from clinical_study.engine import UNIT_TO_KG
from clinical_study.standardize import MAPPING_VERSION, RAW_UNIT_TO_CT

RAW_COLUMNS = {
    "subjects": [
        "record_id",
        "study_id",
        "site_id",
        "country",
        "usubjid",
        "screening_date",
        "age",
        "sex",
        "screen_outcome",
        "screen_fail_reason",
        "rand_date",
        "armcd",
        "edc_eligible",
        "protocol_version_recorded",
        "named_fixture",
    ],
    "vs": [
        "record_id",
        "study_id",
        "usubjid",
        "vsseq",
        "visit",
        "visitnum",
        "vsdtc",
        "vstestcd",
        "vsorres",
        "vsorresu",
        "vsstat",
    ],
    "ex": [
        "record_id",
        "study_id",
        "usubjid",
        "exseq",
        "extrt",
        "exdose",
        "exdosu",
        "exroute",
        "exdosfrq",
        "exstdtc",
        "exendtc",
    ],
    "mh": ["record_id", "study_id", "usubjid", "mhseq", "mhterm", "mhdecod_mondo", "mhstdtc"],
    "cm": ["record_id", "study_id", "usubjid", "cmseq", "cmtrt", "cmdecod_rxnorm", "cmstdtc", "cmendtc"],
    "ds": ["record_id", "study_id", "usubjid", "dsseq", "dsdecod", "dsterm", "dsstdtc"],
    "sv": ["record_id", "study_id", "usubjid", "visit", "visitnum", "svstdtc"],
}
ARM_LABEL = {"CSL101": "CSL-101 10 mg once weekly", "PBO": "Placebo once weekly"}
STD_UNIT = {
    "WEIGHT": "kg",
    "HEIGHT": "cm",
    "WSTCIR": "cm",
    "SYSBP": "mmHg",
    "DIABP": "mmHg",
    "PULSE": "beats/min",
    "BMI": "kg/m2",
}
LENGTH_TO_CM = {"cm": 1.0, "in": 2.54}


def _map(d: dict) -> Column:
    return F.create_map(*[F.lit(x) for x in chain.from_iterable(d.items())])


def blank_to_null(c: str) -> Column:
    return F.when(F.trim(F.col(c)) == "", F.lit(None)).otherwise(F.col(c))


def read_raw(spark, path: str, table: str) -> DataFrame:
    """Bronze: the export exactly as delivered (all strings), plus file lineage. Nothing is cleaned here."""
    schema = ", ".join(f"`{c}` string" for c in RAW_COLUMNS[table])
    df = (
        spark.read.option("header", True)
        .option("quote", '"')
        .option("escape", '"')
        .schema(schema)
        .csv(f"{path}/{table}")
        .select("*", "_metadata")
    )
    return df.select(
        *RAW_COLUMNS[table],
        F.col("_metadata.file_path").alias("_source_file"),
        F.lit(table).alias("_source_table"),
    )


# ------------------------------------------------------------------------------------------------------- DM
def dm(subjects: DataFrame, ex: DataFrame) -> DataFrame:
    first = (
        ex.where(blank_to_null("exstdtc").isNotNull())
        .groupBy("usubjid")
        .agg(
            F.min("exstdtc").alias("rfxstdtc"),
            F.max(F.coalesce(blank_to_null("exendtc"), F.col("exstdtc"))).alias("rfxendtc"),
        )
    )
    d = subjects.join(first, "usubjid", "left")
    rnd = F.col("screen_outcome") == "RANDOMIZED"
    dosed = F.col("rfxstdtc").isNotNull()
    return d.select(
        F.col("study_id").alias("STUDYID"),
        F.lit("DM").alias("DOMAIN"),
        F.col("usubjid").alias("USUBJID"),
        F.regexp_extract("usubjid", r"([^-]+)$", 1).alias("SUBJID"),
        F.col("rfxstdtc").alias("RFSTDTC"),
        F.col("rfxstdtc").alias("RFXSTDTC"),
        F.col("rfxendtc").alias("RFXENDTC"),
        F.col("site_id").alias("SITEID"),
        F.col("age").cast("int").alias("AGE"),
        F.lit("YEARS").alias("AGEU"),
        F.col("sex").alias("SEX"),
        F.when(rnd, F.col("armcd")).otherwise(F.lit("SCRNFAIL")).alias("ARMCD"),
        F.when(rnd, _map(ARM_LABEL)[F.col("armcd")]).otherwise(F.lit("Screen Failure")).alias("ARM"),
        F.when(~rnd, F.lit("SCRNFAIL"))
        .when(~dosed, F.lit("NOTTRT"))
        .otherwise(F.col("armcd"))
        .alias("ACTARMCD"),
        F.col("country").alias("COUNTRY"),
        F.col("screening_date").alias("DMDTC"),
        # demo-extension (SUPPDM-like) columns
        F.col("screen_outcome").alias("CPL_SCREEN_OUTCOME"),
        blank_to_null("screen_fail_reason").alias("CPL_SCREEN_FAIL_REASON"),
        blank_to_null("rand_date").alias("CPL_RANDDT"),
        F.col("edc_eligible").alias("CPL_EDC_ELIGIBLE"),
        F.col("named_fixture").alias("CPL_NAMED_FIXTURE"),
        F.col("record_id").alias("CPL_SOURCE_RECORD_ID"),
        F.col("_source_file").alias("CPL_SOURCE_FILE"),
    )


def study_day(dtc: Column, ref: Column) -> Column:
    """SDTM-style --DY: no day 0. NULL when either date is missing/partial."""
    d, r = F.to_date(F.substring(dtc, 1, 10), "yyyy-MM-dd"), F.to_date(F.substring(ref, 1, 10), "yyyy-MM-dd")
    full = (F.length(dtc) >= 10) & (F.length(ref) >= 10)
    delta = F.datediff(d, r)
    return F.when(full, F.when(delta >= 0, delta + 1).otherwise(delta))


# ------------------------------------------------------------------------------------------------------- VS
def vs(vs_raw: DataFrame, dm_df: DataFrame, vstest_labels: dict[str, str]) -> DataFrame:
    # Spark resolves names case-insensitively: rename the raw unit FIRST, or deriving VSORRESU would
    # overwrite it (and the mapping status / CPL_RAW_UNIT would silently be computed from the mapped value).
    v = vs_raw.withColumnRenamed("vsorresu", "_raw_unit")
    raw_unit = F.trim(F.coalesce(F.col("_raw_unit"), F.lit("")))
    ct = F.when(raw_unit == "", F.lit(None)).otherwise(F.coalesce(_map(RAW_UNIT_TO_CT)[raw_unit], raw_unit))
    unit_status = (
        F.when(raw_unit == "", "MISSING")
        .when(_map(RAW_UNIT_TO_CT)[raw_unit].isNotNull(), "MAPPED")
        .otherwise("UNMAPPED_RAW_UNIT")
    )
    v = v.withColumn("VSORRESU", ct).withColumn("CPL_UNIT_MAPPING_STATUS", unit_status)
    num = blank_to_null("vsorres").cast("double")
    tc = F.col("vstestcd")
    factor = (
        F.when(tc == "WEIGHT", _map(UNIT_TO_KG)[F.col("VSORRESU")])
        .when(tc.isin("HEIGHT", "WSTCIR"), _map(LENGTH_TO_CM)[F.col("VSORRESU")])
        .when(tc.isin("SYSBP", "DIABP"), F.when(F.col("VSORRESU") == "mmHg", 1.0))
        .when(tc == "PULSE", F.when(F.col("VSORRESU") == "beats/min", 1.0))
    )
    notdone = F.upper(F.coalesce(F.col("vsstat"), F.lit(""))) == "NOT DONE"
    stresn = F.when(~notdone, num * factor)
    v = v.join(
        dm_df.select(F.col("USUBJID").alias("_dm_id"), "RFSTDTC"), F.col("usubjid") == F.col("_dm_id"), "left"
    )
    return v.select(
        F.col("study_id").alias("STUDYID"),
        F.lit("VS").alias("DOMAIN"),
        F.col("usubjid").alias("USUBJID"),
        F.col("vsseq").cast("int").alias("VSSEQ"),
        tc.alias("VSTESTCD"),
        _map(vstest_labels)[tc].alias("VSTEST"),
        blank_to_null("vsorres").alias("VSORRES"),
        F.col("VSORRESU"),
        F.when(stresn.isNotNull(), F.format_number(stresn, 2)).alias("VSSTRESC"),
        stresn.alias("VSSTRESN"),
        F.when(stresn.isNotNull(), _map(STD_UNIT)[tc]).alias("VSSTRESU"),
        F.when(notdone, F.lit("NOT DONE")).alias("VSSTAT"),
        F.col("visit").alias("VISIT"),
        blank_to_null("visitnum").cast("double").alias("VISITNUM"),
        F.col("vsdtc").alias("VSDTC"),
        study_day(F.col("vsdtc"), F.col("RFSTDTC")).alias("VSDY"),
        F.concat_ws(".", F.col("usubjid"), tc, F.col("vsseq")).alias("CPL_OBS_ID"),
        F.col("CPL_UNIT_MAPPING_STATUS"),
        F.col("_raw_unit").alias("CPL_RAW_UNIT"),
        F.lit(MAPPING_VERSION).alias("CPL_MAPPING_VERSION"),
        F.col("record_id").alias("CPL_SOURCE_RECORD_ID"),
        F.col("_source_file").alias("CPL_SOURCE_FILE"),
    )


# ------------------------------------------------------------------------------------------- EX/MH/CM/DS/SV
def ex(ex_raw: DataFrame, dm_df: DataFrame) -> DataFrame:
    e = ex_raw.join(
        dm_df.select(F.col("USUBJID").alias("_dm_id"), "RFSTDTC"), F.col("usubjid") == F.col("_dm_id"), "left"
    )
    return e.select(
        F.col("study_id").alias("STUDYID"),
        F.lit("EX").alias("DOMAIN"),
        F.col("usubjid").alias("USUBJID"),
        F.col("exseq").cast("int").alias("EXSEQ"),
        F.col("extrt").alias("EXTRT"),
        F.col("exdose").cast("double").alias("EXDOSE"),
        F.col("exdosu").alias("EXDOSU"),
        F.col("exroute").alias("EXROUTE"),
        F.col("exdosfrq").alias("EXDOSFRQ"),
        F.col("exstdtc").alias("EXSTDTC"),
        blank_to_null("exendtc").alias("EXENDTC"),
        study_day(F.col("exstdtc"), F.col("RFSTDTC")).alias("EXSTDY"),
        F.col("record_id").alias("CPL_SOURCE_RECORD_ID"),
        F.col("_source_file").alias("CPL_SOURCE_FILE"),
    )


def mh(mh_raw: DataFrame, labels: DataFrame) -> DataFrame:
    m = mh_raw.join(
        labels.select(F.col("concept_id").alias("mhdecod_mondo"), F.col("label").alias("_lab")),
        "mhdecod_mondo",
        "left",
    )
    return m.select(
        F.col("study_id").alias("STUDYID"),
        F.lit("MH").alias("DOMAIN"),
        F.col("usubjid").alias("USUBJID"),
        F.col("mhseq").cast("int").alias("MHSEQ"),
        F.col("mhterm").alias("MHTERM"),
        F.col("_lab").alias("MHDECOD"),
        blank_to_null("mhstdtc").alias("MHSTDTC"),
        F.col("mhdecod_mondo").alias("CPL_MONDO_ID"),
        F.when(F.col("_lab").isNull(), "UNRESOLVED_CODE").otherwise("RESOLVED").alias("CPL_CODING_STATUS"),
        F.col("record_id").alias("CPL_SOURCE_RECORD_ID"),
        F.col("_source_file").alias("CPL_SOURCE_FILE"),
    )


def cm(cm_raw: DataFrame, labels: DataFrame) -> DataFrame:
    c = cm_raw.join(
        labels.select(F.col("concept_id").alias("cmdecod_rxnorm"), F.col("label").alias("_lab")),
        "cmdecod_rxnorm",
        "left",
    )
    return c.select(
        F.col("study_id").alias("STUDYID"),
        F.lit("CM").alias("DOMAIN"),
        F.col("usubjid").alias("USUBJID"),
        F.col("cmseq").cast("int").alias("CMSEQ"),
        F.col("cmtrt").alias("CMTRT"),
        F.col("_lab").alias("CMDECOD"),
        blank_to_null("cmstdtc").alias("CMSTDTC"),
        blank_to_null("cmendtc").alias("CMENDTC"),
        F.col("cmdecod_rxnorm").alias("CPL_RXNORM_ID"),
        F.when(F.col("_lab").isNull(), "UNRESOLVED_CODE").otherwise("RESOLVED").alias("CPL_CODING_STATUS"),
        F.col("record_id").alias("CPL_SOURCE_RECORD_ID"),
        F.col("_source_file").alias("CPL_SOURCE_FILE"),
    )


def ds(ds_raw: DataFrame) -> DataFrame:
    return ds_raw.select(
        F.col("study_id").alias("STUDYID"),
        F.lit("DS").alias("DOMAIN"),
        F.col("usubjid").alias("USUBJID"),
        F.col("dsseq").cast("int").alias("DSSEQ"),
        F.col("dsterm").alias("DSTERM"),
        F.col("dsdecod").alias("DSDECOD"),
        F.when(F.col("dsdecod").isin("RANDOMIZED"), "PROTOCOL MILESTONE")
        .otherwise("DISPOSITION EVENT")
        .alias("DSCAT"),
        F.col("dsstdtc").alias("DSSTDTC"),
        F.col("record_id").alias("CPL_SOURCE_RECORD_ID"),
        F.col("_source_file").alias("CPL_SOURCE_FILE"),
    )


def sv(sv_raw: DataFrame) -> DataFrame:
    return sv_raw.select(
        F.col("study_id").alias("STUDYID"),
        F.lit("SV").alias("DOMAIN"),
        F.col("usubjid").alias("USUBJID"),
        F.col("visit").alias("VISIT"),
        blank_to_null("visitnum").cast("double").alias("VISITNUM"),
        F.col("svstdtc").alias("SVSTDTC"),
        F.col("record_id").alias("CPL_SOURCE_RECORD_ID"),
        F.col("_source_file").alias("CPL_SOURCE_FILE"),
    )


def vstest_labels(concepts: list[dict], edges: list[dict]) -> dict[str, str]:
    """VSTESTCD -> VSTEST from the vendored CT (C66741 and C67153 terms share an NCIt code)."""
    in_cl = {e["subject"]: e["object"] for e in edges if e["predicate"] == "cdisc:inCodelist"}
    by = {c["concept_id"]: c for c in concepts}
    code_to_cd, code_to_name = {}, {}
    for t, cl in in_cl.items():
        c = by[t]
        if cl == "CDISC_CT:C66741":
            code_to_cd[c["code"]] = c["notation"]
        elif cl == "CDISC_CT:C67153":
            code_to_name[c["code"]] = c["notation"]
    return {cd: code_to_name[code] for code, cd in code_to_cd.items() if code in code_to_name}


def terminology_version(concepts: list[dict]) -> str:
    rel = sorted({c["release"] for c in concepts if c["scheme"] == "CDISC_CT"})
    return f"CDISC SDTM CT {','.join(rel)}"
