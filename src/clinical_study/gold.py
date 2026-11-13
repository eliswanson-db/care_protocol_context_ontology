"""SDTM-shaped silver -> ADaM-shaped gold (SYNTHETIC demo; ADR-0024). Pure functions over DataFrames.

The deterministic engines (engine.py, eligibility.py) run on Spark workers through mapInPandas. Their
modules are shipped BY VALUE (cloudpickle), so workers don't need the package installed. Registry and KB
travel in the closure.

"ADaM-shaped" = analysis-ready, one record per participant x endpoint x rule version with traceability
variables. It is not a validated ADaM (ADSL/ADVS) implementation.
"""

from __future__ import annotations

import hashlib
import json
import zlib
from collections.abc import Iterator

import pandas as pd
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

# Functions/classes only (no module objects as globals): module objects pickle BY REFERENCE and would need the
# package installed on workers; functions and classes from registered modules pickle by value.
from clinical_study.eligibility import (
    ELIGIBILITY_ENGINE_VERSION,
    Ontology,
    assess,
    on_treatment_deviations,
    participant_status,
    screening_vitals,
)
from clinical_study.engine import ENGINE_VERSION, _first_dose, derive, is_dose

GOLD_VERSION = "1.0.0"


def ship_by_value() -> None:
    """Make the deterministic modules travel with the UDF (no install on workers)."""
    try:
        from pyspark import cloudpickle
    except ImportError:  # pragma: no cover
        import cloudpickle
    import clinical_study.eligibility
    import clinical_study.engine
    import clinical_study.gold
    import clinical_study.standardize

    for m in (
        clinical_study.engine,
        clinical_study.eligibility,
        clinical_study.standardize,
        clinical_study.gold,
    ):
        cloudpickle.register_pickle_by_value(m)


def execution_run_id(registry: dict, kb_release: list[str], data_manifest: dict) -> str:
    """Content-addressed run id: same rules + KB + data = same id (reproducible reruns are recognizable)."""
    blob = json.dumps(
        {
            "registry": registry["registry_version"],
            "engine": ENGINE_VERSION,
            "eligibility": ELIGIBILITY_ENGINE_VERSION,
            "gold": GOLD_VERSION,
            "kb": kb_release,
            "data": {k: data_manifest.get(k) for k in ("generator_version", "seed", "scale", "row_counts")},
        },
        sort_keys=True,
    )
    return "RUN-" + hashlib.sha256(blob.encode()).hexdigest()[:16]


# KB payload. Serverless rejects Python broadcast variables, and Spark broadcasts any pickled UDF command over
# ~1 MB. The KB therefore travels as a compact zlib blob (only the fields the engines read) and is rebuilt on
# the worker, once per process.
UDF_PAYLOAD_LIMIT = 512 * 1024


def pack_kb(concepts: list[dict], edges: list[dict]) -> bytes:
    c = [[x["concept_id"], x["scheme"], x["label"], x["release"]] for x in concepts]
    e = [[x["subject"], x["predicate"], x["object"]] for x in edges]
    return zlib.compress(json.dumps({"c": c, "e": e}, separators=(",", ":")).encode(), 9)


_ONTO_CACHE: dict[str, Ontology] = {}


def onto_from_blob(blob: bytes) -> Ontology:
    key = hashlib.sha1(blob).hexdigest()
    if key not in _ONTO_CACHE:
        d = json.loads(zlib.decompress(blob))
        concepts = [{"concept_id": a, "scheme": b, "label": c, "release": r} for a, b, c, r in d["c"]]
        edges = [{"subject": a, "predicate": b, "object": c} for a, b, c in d["e"]]
        _ONTO_CACHE[key] = Ontology(concepts, edges)
    return _ONTO_CACHE[key]


# ------------------------------------------------------------------------------------------ subject bundles
def subject_bundles(dm: DataFrame, vs: DataFrame, ex: DataFrame, mh: DataFrame, cm: DataFrame) -> DataFrame:
    w = (
        vs.where(F.col("VSTESTCD") == "WEIGHT")
        .groupBy("USUBJID")
        .agg(
            F.collect_list(
                F.struct(
                    F.col("CPL_OBS_ID").alias("obs_id"),
                    F.col("VSSEQ").alias("vsseq"),
                    F.col("VISIT").alias("visit"),
                    F.col("VSDTC").alias("vsdtc"),
                    F.col("VSORRES").alias("vsorres"),
                    F.col("VSORRESU").alias("vsorresu"),
                    F.col("VSSTAT").alias("vsstat"),
                    F.col("CPL_SOURCE_RECORD_ID").alias("source_record_id"),
                )
            ).alias("weights")
        )
    )
    h = (
        vs.where((F.col("VSTESTCD") == "HEIGHT") & (F.col("VISIT") == "SCREENING"))
        .groupBy("USUBJID")
        .agg(
            F.min_by(
                F.struct(
                    F.col("CPL_OBS_ID").alias("obs_id"),
                    F.col("VSORRES").alias("vsorres"),
                    F.col("VSORRESU").alias("vsorresu"),
                ),
                F.col("VSSEQ"),
            ).alias("height")
        )
    )
    e = ex.groupBy("USUBJID").agg(
        F.collect_list(
            F.struct(
                F.col("EXSTDTC").alias("exstdtc"),
                F.col("EXDOSE").alias("exdose"),
                F.col("EXTRT").alias("extrt"),
            )
        ).alias("exposures")
    )
    m = mh.groupBy("USUBJID").agg(
        F.collect_list(
            F.struct(F.col("CPL_SOURCE_RECORD_ID").alias("mh_id"), F.col("CPL_MONDO_ID").alias("mondo_id"))
        ).alias("mh")
    )
    c = cm.groupBy("USUBJID").agg(
        F.collect_list(
            F.struct(
                F.col("CPL_SOURCE_RECORD_ID").alias("cm_id"),
                F.col("CPL_RXNORM_ID").alias("rxnorm"),
                F.col("CMSTDTC").alias("cmstdtc"),
                F.col("CMENDTC").alias("cmendtc"),
            )
        ).alias("cm")
    )
    return (
        dm.select(
            "STUDYID",
            "USUBJID",
            "AGE",
            "DMDTC",
            "ARMCD",
            "ACTARMCD",
            "SITEID",
            "COUNTRY",
            "CPL_SCREEN_OUTCOME",
            "CPL_EDC_ELIGIBLE",
            "CPL_NAMED_FIXTURE",
        )
        .join(w, "USUBJID", "left")
        .join(h, "USUBJID", "left")
        .join(e, "USUBJID", "left")
        .join(m, "USUBJID", "left")
        .join(c, "USUBJID", "left")
    )


def _lst(x) -> list[dict]:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return []
    return [dict(i) for i in x]


def _dct(x) -> dict | None:
    return None if x is None or (isinstance(x, float) and pd.isna(x)) else dict(x)


# ---------------------------------------------------------------------------------------------- eligibility
ELIG_SCHEMA = (
    "STUDYID string, USUBJID string, protocol_version string, eligibility_rule_id string, "
    "rule_eligible boolean, criterion_id string, criterion_type string, outcome string, "
    "evidence array<string>, path array<string>, path_labels array<string>, detail string, "
    "eligibility_engine_version string, execution_run_id string"
)

POP_SCHEMA = (
    "STUDYID string, USUBJID string, ARMCD string, SITEID string, COUNTRY string, randomized boolean, "
    "dosed boolean, rule_eligible boolean, edc_eligible string, protocol_version string, "
    "eligibility_rule_id string, FASFL string, PPSFL string, reconciliation string, "
    "deviations array<struct<deviation:string,severity:string,evidence:string,"
    "path:array<string>,drug:string>>, "
    "execution_run_id string"
)


def _assess_row(r: pd.Series, registry: dict, onto: Ontology):
    subj = {
        "study_id": r["STUDYID"],
        "usubjid": r["USUBJID"],
        "screening_date": r["DMDTC"],
        "age": None if pd.isna(r["AGE"]) else int(r["AGE"]),
    }
    sv = screening_vitals(_lst(r["weights"]), _dct(r["height"]))
    return assess(subj, sv, _lst(r["mh"]), _lst(r["cm"]), registry, onto)


def make_eligibility_fn(registry: dict, kb_blob: bytes, run_id: str):
    def fn(it: Iterator[pd.DataFrame]) -> Iterator[pd.DataFrame]:
        onto = onto_from_blob(kb_blob)
        for pdf in it:
            rows = []
            for _, r in pdf.iterrows():
                a = _assess_row(r, registry, onto)
                for c in a.criteria:
                    rows.append(
                        {
                            "STUDYID": a.study_id,
                            "USUBJID": a.usubjid,
                            "protocol_version": a.protocol_version,
                            "eligibility_rule_id": a.eligibility_rule_id,
                            "rule_eligible": a.eligible,
                            "criterion_id": c.criterion_id,
                            "criterion_type": c.criterion_type,
                            "outcome": c.outcome,
                            "evidence": c.evidence,
                            "path": c.path,
                            "path_labels": [onto.label(x) or x for x in c.path],
                            "detail": c.detail,
                            "eligibility_engine_version": a.engine_version,
                            "execution_run_id": run_id,
                        }
                    )
            yield pd.DataFrame(rows, columns=[c.split(" ")[0] for c in ELIG_SCHEMA.split(", ")])

    return fn


def make_population_fn(registry: dict, kb_blob: bytes, run_id: str):
    def fn(it: Iterator[pd.DataFrame]) -> Iterator[pd.DataFrame]:
        onto = onto_from_blob(kb_blob)
        for pdf in it:
            rows = []
            for _, r in pdf.iterrows():
                a = _assess_row(r, registry, onto)
                exps = _lst(r["exposures"])
                randomized = r["CPL_SCREEN_OUTCOME"] == "RANDOMIZED"
                dosed = any(is_dose(e) for e in exps)
                first, _ = _first_dose(exps)
                on_tx = on_treatment_deviations(
                    first.day if first else None, None, _lst(r["cm"]), registry, onto
                )
                st = participant_status(randomized, dosed, a, on_tx)
                rec = (
                    "CONSISTENT"
                    if a.eligible == randomized
                    else "ENROLLED_BUT_RULE_INELIGIBLE"
                    if randomized
                    else "RULE_ELIGIBLE_BUT_NOT_ENROLLED"
                )
                rows.append(
                    {
                        "STUDYID": r["STUDYID"],
                        "USUBJID": r["USUBJID"],
                        "ARMCD": r["ARMCD"],
                        "SITEID": r["SITEID"],
                        "COUNTRY": r["COUNTRY"],
                        "randomized": randomized,
                        "dosed": dosed,
                        "rule_eligible": a.eligible,
                        "edc_eligible": r["CPL_EDC_ELIGIBLE"],
                        "protocol_version": a.protocol_version,
                        "eligibility_rule_id": a.eligibility_rule_id,
                        "FASFL": "Y" if st["fas"] else "N",
                        "PPSFL": "Y" if st["pps"] else "N",
                        "reconciliation": rec,
                        "deviations": [{**d, "path": list(d["path"])} for d in st["deviations"]],
                        "execution_run_id": run_id,
                    }
                )
            yield pd.DataFrame(
                rows,
                columns=[c.split(" ")[0] for c in POP_SCHEMA.split(", ")[:-2]]
                + ["deviations", "execution_run_id"],
            )

    return fn


# ------------------------------------------------------------------------------------------------- endpoint
RESULT_SCHEMA = (
    "STUDYID string, USUBJID string, PARAMCD string, endpoint_id string, endpoint_version string, "
    "rule_version string, protocol_version string, sap_version string, analysis_population_status string, "
    "reference_date string, followup_target_date string, baseline_method string, "
    "baseline_observation_id string, followup_observation_id string, BASE double, AVAL_FU double, "
    "PCHG double, PCHG_DISPLAY double, result_status string, exclusion_reason string, "
    "terminology_version string, engine_version string, execution_run_id string"
)

CAND_SCHEMA = (
    "STUDYID string, USUBJID string, endpoint_id string, rule_version string, obs_id string, "
    "source_record_id string, vsseq int, vsdtc string, visit string, study_day int, weight_kg double, "
    "role string, decision string, reason string, days_from_target int, execution_run_id string"
)

ENDPOINT_FOR = {"CSL-A": "EP-A-WT24", "CSL-B": "EP-B-WT24"}


def _derive_all(r: pd.Series, registry: dict, term_version: str, run_id: str):
    ep_id = ENDPOINT_FOR[r["STUDYID"]]
    ep = registry["endpoints"][ep_id]
    obs = _lst(r["weights"])
    src = {o["obs_id"]: o.get("source_record_id") for o in obs}
    part = {
        "study_id": r["STUDYID"],
        "usubjid": r["USUBJID"],
        "randomized": r["CPL_SCREEN_OUTCOME"] == "RANDOMIZED",
    }
    for rv, rule in sorted(ep["rule_versions"].items()):
        if rule.get("review_state") != "approved":
            continue
        yield (
            ep_id,
            rv,
            src,
            derive(
                part,
                obs,
                _lst(r["exposures"]),
                endpoint_id=ep_id,
                endpoint=ep,
                rule_version=rv,
                terminology_version=term_version,
                execution_run_id=run_id,
            ),
        )


def make_result_fn(registry: dict, term_version: str, run_id: str):
    def fn(it: Iterator[pd.DataFrame]) -> Iterator[pd.DataFrame]:
        for pdf in it:
            rows = []
            for _, r in pdf.iterrows():
                for _ep, _rv, _src, res in _derive_all(r, registry, term_version, run_id):
                    d = res.row()
                    rows.append(
                        {
                            "STUDYID": d["study_id"],
                            "USUBJID": d["participant_id"],
                            "PARAMCD": "WTPCHG24",
                            "endpoint_id": d["endpoint_id"],
                            "endpoint_version": d["endpoint_version"],
                            "rule_version": d["rule_version"],
                            "protocol_version": d["protocol_version"],
                            "sap_version": d["sap_version"],
                            "analysis_population_status": d["analysis_population_status"],
                            "reference_date": d["reference_date"],
                            "followup_target_date": d["followup_target_date"],
                            "baseline_method": d["baseline_method"],
                            "baseline_observation_id": d["baseline_observation_id"],
                            "followup_observation_id": d["followup_observation_id"],
                            "BASE": d["baseline_value"],
                            "AVAL_FU": d["followup_value"],
                            "PCHG": d["analysis_value"],
                            "PCHG_DISPLAY": d["analysis_value_display"],
                            "result_status": d["result_status"],
                            "exclusion_reason": d["exclusion_reason"],
                            "terminology_version": d["terminology_version"],
                            "engine_version": d["engine_version"],
                            "execution_run_id": d["execution_run_id"],
                        }
                    )
            yield pd.DataFrame(rows, columns=[c.split(" ")[0] for c in RESULT_SCHEMA.split(", ")])

    return fn


def make_candidate_fn(registry: dict, term_version: str, run_id: str):
    def fn(it: Iterator[pd.DataFrame]) -> Iterator[pd.DataFrame]:
        for pdf in it:
            rows = []
            for _, r in pdf.iterrows():
                for ep, rv, src, res in _derive_all(r, registry, term_version, run_id):
                    for c in res.candidates:
                        rows.append(
                            {
                                "STUDYID": res.study_id,
                                "USUBJID": res.participant_id,
                                "endpoint_id": ep,
                                "rule_version": rv,
                                "obs_id": c.obs_id,
                                "source_record_id": src.get(c.obs_id),
                                "vsseq": c.vsseq,
                                "vsdtc": c.vsdtc,
                                "visit": c.visit,
                                "study_day": c.study_day,
                                "weight_kg": c.weight_kg,
                                "role": c.role,
                                "decision": c.decision,
                                "reason": c.reason,
                                "days_from_target": c.days_from_target,
                                "execution_run_id": run_id,
                            }
                        )
            out = pd.DataFrame(rows, columns=[c.split(" ")[0] for c in CAND_SCHEMA.split(", ")])
            yield out.astype({"vsseq": "Int64", "study_day": "Int64", "days_from_target": "Int64"})

    return fn


def randomized_bundles(bundles: DataFrame) -> DataFrame:
    return bundles.where(F.col("CPL_SCREEN_OUTCOME") == "RANDOMIZED")


# ------------------------------------------------------------------------------------------ analysis tables
def amendment_impact(
    results: DataFrame, candidates: DataFrame, from_rv: str = "R1", to_rv: str = "R2"
) -> DataFrame:
    """Per participant: what changed between two rule versions, and why (CSL-A Amendment 1)."""
    r = results.where(F.col("endpoint_id") == "EP-A-WT24")
    a = r.where(F.col("rule_version") == from_rv).alias("a")
    b = r.where(F.col("rule_version") == to_rv).alias("b")
    elig = (
        candidates.where(F.col("decision") != "EXCLUDED")
        .groupBy("USUBJID", "rule_version")
        .agg(F.sort_array(F.collect_list("obs_id")).alias("eligible_ids"))
    )
    ea = elig.where(F.col("rule_version") == from_rv).select(
        "USUBJID", F.col("eligible_ids").alias("elig_from")
    )
    eb = elig.where(F.col("rule_version") == to_rv).select("USUBJID", F.col("eligible_ids").alias("elig_to"))
    j = a.join(b, F.col("a.USUBJID") == F.col("b.USUBJID")).select(
        F.col("a.STUDYID").alias("STUDYID"),
        F.col("a.USUBJID").alias("USUBJID"),
        F.lit(from_rv).alias("from_rule_version"),
        F.lit(to_rv).alias("to_rule_version"),
        F.col("a.result_status").alias("status_from"),
        F.col("b.result_status").alias("status_to"),
        F.col("a.followup_observation_id").alias("followup_from"),
        F.col("b.followup_observation_id").alias("followup_to"),
        F.col("a.PCHG").alias("pchg_from"),
        F.col("b.PCHG").alias("pchg_to"),
        F.col("a.exclusion_reason").alias("reason_from"),
        F.col("b.followup_target_date").alias("target_date"),
        F.col("a.execution_run_id").alias("execution_run_id"),
    )
    j = j.join(ea, "USUBJID", "left").join(eb, "USUBJID", "left")
    ce = F.coalesce(F.col("elig_from"), F.array()) != F.coalesce(F.col("elig_to"), F.array())
    cs = ~F.col("followup_from").eqNullSafe(F.col("followup_to"))
    cv = ~F.col("pchg_from").eqNullSafe(F.col("pchg_to"))
    became = (F.col("status_from") != "DERIVED") & (F.col("status_to") == "DERIVED")
    why = (
        F.when(
            became,
            F.concat(
                F.lit("No follow-up within ±7 days under R1 ("),
                F.col("reason_from"),
                F.lit("); R2's ±14-day window admits it."),
            ),
        )
        .when(
            ce & ~cs,
            F.lit("R2 admits an additional in-window candidate, but the closest record is unchanged."),
        )
        .when(cs, F.lit("Selected follow-up record changed."))
        .otherwise(F.lit("No change."))
    )
    return j.select(
        "*",
        ce.alias("eligible_candidates_changed"),
        cs.alias("selected_followup_changed"),
        cv.alias("endpoint_value_changed"),
        became.alias("endpoint_became_derivable"),
        why.alias("explanation"),
    )


def study_summary(results: DataFrame, population: DataFrame) -> DataFrame:
    """Descriptive only (synthetic). Never pooled across studies or rule versions."""
    r = results.join(population.select("USUBJID", "ARMCD", "SITEID", "FASFL", "PPSFL"), "USUBJID")
    out = []
    for popfl in ("FASFL", "PPSFL"):
        g = (
            r.where(F.col(popfl) == "Y")
            .groupBy("STUDYID", "endpoint_id", "rule_version", "protocol_version", "sap_version", "ARMCD")
            .agg(
                F.count("*").alias("n_population"),
                F.sum(F.when(F.col("result_status") == "DERIVED", 1).otherwise(0)).alias("n_derived"),
                F.sum(F.when(F.col("result_status") == "NO_VALID_BASELINE", 1).otherwise(0)).alias(
                    "n_no_baseline"
                ),
                F.sum(F.when(F.col("result_status") == "NO_QUALIFYING_FOLLOWUP", 1).otherwise(0)).alias(
                    "n_no_followup"
                ),
                F.sum(F.when(F.col("result_status") == "NO_REFERENCE_DATE", 1).otherwise(0)).alias(
                    "n_no_reference"
                ),
                F.avg("PCHG").alias("mean_pchg"),
                F.stddev("PCHG").alias("sd_pchg"),
                F.percentile_approx("PCHG", 0.5).alias("median_pchg"),
            )
            .withColumn("population", F.lit(popfl[:3]))
        )
        out.append(g)
    s = out[0].unionByName(out[1])
    return s.withColumn("pct_missing", 1 - F.col("n_derived") / F.col("n_population")).withColumn(
        "disclaimer",
        F.lit("Synthetic, descriptive only. Not evidence of efficacy; no comparative inference."),
    )


def provenance_edges(
    results: DataFrame, candidates: DataFrame, registry: dict, spark: SparkSession
) -> DataFrame:
    """Record-level lineage as typed edges (the same shape the graph mapping uses)."""
    rid = F.concat_ws("|", "USUBJID", "endpoint_id", "rule_version")
    sel = candidates.where(F.col("decision") == "SELECTED")
    e1 = sel.select(
        F.concat_ws("|", "USUBJID", "endpoint_id", "rule_version").alias("subject"),
        F.when(F.col("role") == "BASELINE", "cpl:usesBaselineObservation")
        .otherwise("cpl:usesFollowupObservation")
        .alias("predicate"),
        F.col("obs_id").alias("object"),
        "execution_run_id",
    )
    e2 = candidates.select(
        F.col("obs_id").alias("subject"),
        F.lit("cpl:originatesFrom").alias("predicate"),
        F.col("source_record_id").alias("object"),
        "execution_run_id",
    ).dropDuplicates()
    e3 = results.select(
        rid.alias("subject"),
        F.lit("cpl:derivedUnder").alias("predicate"),
        F.concat_ws(".", "endpoint_id", "rule_version").alias("object"),
        "execution_run_id",
    )
    e4 = results.select(
        rid.alias("subject"),
        F.lit("cpl:generatedBy").alias("predicate"),
        F.col("execution_run_id").alias("object"),
        "execution_run_id",
    )
    rows = []
    for ep_id, ep in registry["endpoints"].items():
        for rv, rule in ep["rule_versions"].items():
            sec = rule["source_section"]
            rows.append((f"{ep_id}.{rv}", "cpl:supportedBy", f"{sec['document']}#{sec['section']}"))
            rows.append((f"{ep_id}.{rv}", "cpl:measures", ep["biomedical_concept"]))
    run = results.select("execution_run_id").limit(1)
    e5 = spark.createDataFrame(rows, "subject string, predicate string, object string").crossJoin(run)
    return e1.unionByName(e2).unionByName(e3).unionByName(e4).unionByName(e5)


def tracer_registry(spark: SparkSession) -> DataFrame:
    from clinical_study.standardize import load_named

    rows = [
        (
            n["participant"]["usubjid"],
            n["participant"]["study_id"],
            f"EDGE-{n['edge_case']:02d}" if n["edge_case"] else f"ELIG-{n['eligibility_case']}",
            n["title"],
        )
        for n in load_named()
    ]
    return spark.createDataFrame(rows, "USUBJID string, STUDYID string, tracer_id string, title string")
