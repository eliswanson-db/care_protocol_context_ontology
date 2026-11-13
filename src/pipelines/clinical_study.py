# ruff: noqa: F821  -- `spark` is injected by the Lakeflow pipeline runtime
"""Lakeflow Declarative Pipeline — Clinical Study Context & Evidence Lab (SYNTHETIC; ADR-0024).

raw EDC CSV exports (volume) -> bronze_edc_* (as delivered) -> silver_* (SDTM-shaped) -> gold_* (ADaM-shaped
endpoint results with every candidate observation, eligibility, populations, Amendment 1 impact, provenance).
All logic lives in src/clinical_study (unit-tested locally, incl. tests/test_ls_pipeline_local.py); this file
only declares datasets. The KB and the approved rule registry are read from clinical_study_standards
(loaded by the ls_bootstrap job). Not submission-ready SDTM/ADaM.
"""

import json
import sys

import yaml
from pyspark import pipelines as dp
from pyspark.sql import functions as F

sys.path.insert(0, spark.conf.get("cs.src_path"))  # noqa: F821 (spark is provided by the pipeline runtime)

from clinical_study import gold, sdtm  # noqa: E402
from clinical_study.eligibility import Ontology  # noqa: E402

CATALOG = spark.conf.get("cs.catalog")  # noqa: F821
LANDING = spark.conf.get("cs.landing")  # noqa: F821
STD = f"{CATALOG}.clinical_study_standards"

gold.ship_by_value()
_concepts = [r.asDict() for r in spark.table(f"{STD}.kb_concept").collect()]  # noqa: F821  (~4k rows)
_edges = [r.asDict() for r in spark.table(f"{STD}.kb_edge").collect()]  # noqa: F821  (~6k rows)
REGISTRY = yaml.safe_load(spark.table(f"{STD}.rule_registry").collect()[0]["yaml_text"])  # noqa: F821
ONTO = Ontology(_concepts, _edges)
TERM_VERSION = sdtm.terminology_version(_concepts)
VSTEST = sdtm.vstest_labels(_concepts, _edges)
try:
    _manifest = json.loads("".join(r.value for r in spark.read.text(f"{LANDING}/_manifest.json").collect()))  # noqa: F821
except Exception:  # a missing manifest must be visible, not fatal: the run id then says so
    _manifest = {"generator_version": "MISSING_MANIFEST"}
RUN_ID = gold.execution_run_id(REGISTRY, ONTO.release, _manifest)
SYN = (
    "SYNTHETIC demo data (Clinical Study Context & Evidence Lab). Not submission-ready; not for clinical use."
)
PROPS = {"cpl.demo_id": "life_sciences_clinical", "cpl.registry_version": REGISTRY["registry_version"]}


# ---------------------------------------------------------------------------------------------------- bronze
def _bronze(table: str):
    @dp.materialized_view(
        name=f"bronze_edc_{table}",
        table_properties=PROPS,
        comment=f"Raw EDC export '{table}' exactly as delivered (all strings) + source file. {SYN}",
    )
    def _t():
        return sdtm.read_raw(spark, LANDING, table)  # noqa: F821

    return _t


for _t in sdtm.RAW_COLUMNS:
    _bronze(_t)


# ---------------------------------------------------------------------------------------------------- silver
@dp.materialized_view(
    comment=f"SDTM-shaped DM (one row per screened subject; CPL_ = demo extension). {SYN}",
    table_properties=PROPS,
)
@dp.expect("usubjid_present", "USUBJID IS NOT NULL")
@dp.expect("randomized_have_arm", "CPL_SCREEN_OUTCOME <> 'RANDOMIZED' OR ARMCD IN ('CSL101','PBO')")
def silver_dm():
    return sdtm.dm(spark.read.table("bronze_edc_subjects"), spark.read.table("bronze_edc_ex"))  # noqa: F821


@dp.materialized_view(
    comment=f"SDTM-shaped VS: CT units (VSRESU), VSSTRESN in standard units, VSDY, raw unit "
    f"and mapping status kept for lineage. {SYN}",
    table_properties=PROPS,
)
@dp.expect(
    "weight_unit_allowed_by_dss", "VSTESTCD <> 'WEIGHT' OR VSORRESU IS NULL OR VSORRESU IN ('kg','LB','g')"
)
@dp.expect("unit_mapped", "CPL_UNIT_MAPPING_STATUS = 'MAPPED'")
@dp.expect("result_or_not_done", "VSORRES IS NOT NULL OR VSSTAT = 'NOT DONE'")
def silver_vs():
    return sdtm.vs(spark.read.table("bronze_edc_vs"), spark.read.table("silver_dm"), VSTEST)  # noqa: F821


@dp.materialized_view(
    comment=f"SDTM-shaped EX (placebo recorded with EXDOSE 0). {SYN}", table_properties=PROPS
)
def silver_ex():
    return sdtm.ex(spark.read.table("bronze_edc_ex"), spark.read.table("silver_dm"))  # noqa: F821


def _labels():
    return spark.createDataFrame(
        [(c["concept_id"], c["label"]) for c in _concepts],  # noqa: F821
        "concept_id string, label string",
    )


@dp.materialized_view(
    comment=f"SDTM-shaped MH coded to MONDO (CPL_MONDO_ID; MedDRA not used — licensed). {SYN}",
    table_properties=PROPS,
)
@dp.expect("mh_code_resolves", "CPL_CODING_STATUS = 'RESOLVED'")
def silver_mh():
    return sdtm.mh(spark.read.table("bronze_edc_mh"), _labels())  # noqa: F821


@dp.materialized_view(
    comment=f"SDTM-shaped CM coded to RxNorm ingredients (CPL_RXNORM_ID). {SYN}", table_properties=PROPS
)
@dp.expect("cm_code_resolves", "CPL_CODING_STATUS = 'RESOLVED'")
def silver_cm():
    return sdtm.cm(spark.read.table("bronze_edc_cm"), _labels())  # noqa: F821


@dp.materialized_view(comment=f"SDTM-shaped DS. {SYN}", table_properties=PROPS)
def silver_ds():
    return sdtm.ds(spark.read.table("bronze_edc_ds"))  # noqa: F821


@dp.materialized_view(comment=f"SDTM-shaped SV (actual visit dates). {SYN}", table_properties=PROPS)
def silver_sv():
    return sdtm.sv(spark.read.table("bronze_edc_sv"))  # noqa: F821


# ---------------------------------------------------------------------------------------------------- gold
@dp.temporary_view()
def subject_bundle():
    r = spark.read.table  # noqa: F821
    return gold.subject_bundles(
        r("silver_dm"), r("silver_vs"), r("silver_ex"), r("silver_mh"), r("silver_cm")
    )


@dp.materialized_view(
    comment=f"Eligibility per criterion with evidence records and the ontology path that "
    f"decided it (protocol version by screening date). {SYN}",
    table_properties=PROPS,
)
def gold_eligibility_criterion():
    return spark.read.table("subject_bundle").mapInPandas(  # noqa: F821
        gold.make_eligibility_fn(REGISTRY, ONTO, RUN_ID), gold.ELIG_SCHEMA
    )


@dp.materialized_view(
    comment=f"ADSL-like participant analysis context: FAS/PPS flags, major deviations, and "
    f"EDC-vs-rule eligibility reconciliation. {SYN}",
    table_properties=PROPS,
)
def gold_participant_population():
    return spark.read.table("subject_bundle").mapInPandas(  # noqa: F821
        gold.make_population_fn(REGISTRY, ONTO, RUN_ID), gold.POP_SCHEMA
    )


@dp.materialized_view(
    comment=f"ADaM-shaped Week 24 % change in body weight, one row per participant x endpoint x "
    f"approved rule version (PCHG unrounded; PCHG_DISPLAY for display). {SYN}",
    table_properties=PROPS,
)
@dp.expect(
    "derived_has_provenance",
    "result_status <> 'DERIVED' OR (baseline_observation_id IS NOT NULL "
    "AND followup_observation_id IS NOT NULL AND PCHG IS NOT NULL)",
)
def gold_endpoint_result():
    return gold.randomized_bundles(spark.read.table("subject_bundle")).mapInPandas(  # noqa: F821
        gold.make_result_fn(REGISTRY, TERM_VERSION, RUN_ID), gold.RESULT_SCHEMA
    )


@dp.materialized_view(
    comment=f"EVERY candidate weight observation per participant x rule version with its "
    f"decision and reason (not just the winners). {SYN}",
    table_properties=PROPS,
)
def gold_endpoint_candidate():
    return gold.randomized_bundles(spark.read.table("subject_bundle")).mapInPandas(  # noqa: F821
        gold.make_candidate_fn(REGISTRY, TERM_VERSION, RUN_ID), gold.CAND_SCHEMA
    )


@dp.materialized_view(
    comment=f"CSL-A Amendment 1 (R1 +/-7d -> R2 +/-14d): per participant, what changed and why. {SYN}",
    table_properties=PROPS,
)
def gold_amendment_impact():
    return gold.amendment_impact(
        spark.read.table("gold_endpoint_result"),  # noqa: F821
        spark.read.table("gold_endpoint_candidate"),
    )  # noqa: F821


@dp.materialized_view(
    comment=f"Descriptive endpoint summary by study x rule version x arm x population. Never "
    f"pooled across studies or rule versions. {SYN}",
    table_properties=PROPS,
)
def gold_study_summary():
    return gold.study_summary(
        spark.read.table("gold_endpoint_result"),  # noqa: F821
        spark.read.table("gold_participant_population"),
    )  # noqa: F821


@dp.materialized_view(
    comment=f"Record-level provenance edges: result -> observations -> source records; result -> "
    f"rule version -> document section; result -> execution run. {SYN}",
    table_properties=PROPS,
)
def gold_provenance_edge():
    return gold.provenance_edges(
        spark.read.table("gold_endpoint_result"),  # noqa: F821
        spark.read.table("gold_endpoint_candidate"),
        REGISTRY,
        spark,
    )  # noqa: F821


@dp.materialized_view(
    comment=f"Named tracer participants (the 20 endpoint edge cases + 9 eligibility cases). {SYN}",
    table_properties=PROPS,
)
def gold_tracer_registry():
    return gold.tracer_registry(spark).withColumn("execution_run_id", F.lit(RUN_ID))  # noqa: F821
