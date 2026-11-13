"""Synthetic EDC export generator — Clinical Study Context & Evidence Lab (SYNTHETIC; ADR-0024).

Writes raw, EDC-shaped CSV exports (strings exactly as a site would key them: 'lb', partial dates, blanks) for
studies CSL-A and CSL-B, plus the hand-authored named fixtures, to a landing directory (a UC volume in a job,
a local dir in tests). The Lakeflow pipeline ingests these into bronze.

Determinism: every random draw is a hash of (seed, salt, subject key[, slot]) via xxhash64, so the output does
not depend on Spark partitioning or execution order. dbldatagen builds the subject master with
randomSeedMethod='hash_fieldname'. Outputs are written sorted, one file per table.

The story planted in the data (all synthetic):
  * SITE-118 (CSL-A) systematically schedules Week 24 visits 8-13 days late. Under the original +/-7-day
    window those participants have no evaluable endpoint; Amendment 1 (+/-14) recovers them.
  * Placebo participants at US sites start commercial GLP-1 RAs during treatment (an intercurrent event),
    which makes them major protocol deviations, excluded from the per-protocol set.
  * Obstructive-sleep-apnea-only participants (BMI 27-30) screen-fail until Amendment 2 (2025-11-01).
  * A few participants are enrolled in error (exclusionary history recorded, EDC says eligible).

    python -m clinical_study.generate --out /Volumes/<cat>/clinical_study/raw_edc --scale demo --seed 2026
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import date
from pathlib import Path

import yaml
from pyspark.sql import Column, DataFrame, SparkSession, Window
from pyspark.sql import functions as F

from clinical_study.standardize import HERE, load_registry

GENERATOR_VERSION = "1.0.0"
DATA_CUTOFF = "2026-10-31"
LB_PER_KG = 1 / 0.45359237
KG_PER_STONE = 6.35029318

SCALES = {"small": {"CSL-A": 320, "CSL-B": 200}, "demo": {"CSL-A": 5600, "CSL-B": 3400}}

STUDY_CFG = {
    "CSL-A": {
        "sites": 40,
        "site_base": 101,
        "enroll": ("2025-01-20", "2025-12-15"),
        "screen_gap": (14, 28),
        "drug_ratio": 2 / 3,
        "late_site": "SITE-118",
        "disc_rate": 0.18,
        "profiles": [
            ("BMI30", 50),
            ("BMI27_WRC", 17),
            ("OSA_ONLY", 5),
            ("LOOKALIKE_ONLY", 2),
            ("BMI_LOW", 5),
            ("EXCL_MH", 5),
            ("CI_ONLY", 1),
            ("CM_PRE", 3),
            ("OTHER_FAIL", 6),
            ("DRUG_ALLERGY", 3),
            ("AGE_OUT", 1),
            ("ERROR_ENROLLED", 0.5),
        ],
        "age": (18, 75),
    },
    "CSL-B": {
        "sites": 30,
        "site_base": 201,
        "enroll": ("2025-02-15", "2025-11-30"),
        "screen_gap": (10, 21),
        "drug_ratio": 1 / 2,
        "late_site": None,
        "disc_rate": 0.12,
        "profiles": [
            ("ELIG_T2D", 74),
            ("NO_T2D", 4),
            ("BMI_LOW", 5),
            ("EXCL_MH", 5),
            ("CI_ONLY", 1),
            ("CM_PRE", 3),
            ("OTHER_FAIL", 6),
            ("DRUG_ALLERGY", 2),
            ("AGE_OUT", 1),
            ("ERROR_ENROLLED", 0.5),
        ],
        "age": (18, 80),
    },
}
COUNTRIES = [
    ("US", 35),
    ("CA", 8),
    ("GB", 10),
    ("DE", 10),
    ("PL", 10),
    ("ES", 8),
    ("MX", 7),
    ("JP", 6),
    ("AU", 6),
]
AMENDMENT_2 = "2025-11-01"


# -------------------------------------------------------------------------------------- deterministic draws
def U(seed: int, salt: str, *cols) -> Column:
    """Uniform [0,1) from a hash of (seed, salt, cols). Independent of partitioning."""
    h = F.xxhash64(F.lit(seed), F.lit(salt), *[c if isinstance(c, Column) else F.lit(c) for c in cols])
    return F.pmod(h, F.lit(2147483647)).cast("double") / F.lit(2147483647.0)


def N(seed: int, salt: str, *cols) -> Column:
    """Standard normal via Box-Muller on two hashed uniforms."""
    u1 = F.greatest(U(seed, salt + ":a", *cols), F.lit(1e-12))
    u2 = U(seed, salt + ":b", *cols)
    return F.sqrt(-2.0 * F.log(u1)) * F.cos(2 * math.pi * u2)


def pick(u: Column, items: list, weights: list[float]) -> Column:
    """Weighted categorical choice; never uniform unless the weights say so."""
    total, acc, expr = float(sum(weights)), 0.0, None
    for it, w in zip(items, weights, strict=True):
        acc += w / total
        expr = F.when(u < acc, F.lit(it)) if expr is None else expr.when(u < acc, F.lit(it))
    return expr.otherwise(F.lit(items[-1]))


def fmt_date(c: Column) -> Column:
    return F.date_format(c, "yyyy-MM-dd")


# ----------------------------------------------------------------------------------------------- vocabulary
def load_terms() -> dict:
    with open(HERE / "fixtures" / "generator_terms.yaml", encoding="utf-8") as f:
        t = yaml.safe_load(f)
    import csv

    from clinical_study.eligibility import STD

    with open(STD / "kb_concept.csv", encoding="utf-8") as f:
        rx = {r["label"]: r["concept_id"] for r in csv.DictReader(f) if r["scheme"] == "RXNORM"}
    for grp in t["drugs"].values():
        for d in grp:
            if d["ingredient"] not in rx:
                raise ValueError(f"generator drug '{d['ingredient']}' not in the KB")
            d["rxnorm"] = rx[d["ingredient"]]
    return t


def term_df(spark: SparkSession, terms: dict) -> DataFrame:
    rows = []
    for cat, items in terms["conditions"].items():
        tot = sum(i["weight"] for i in items)
        acc = 0.0
        for i in items:
            lo = acc
            acc += i["weight"] / tot
            rows.append((cat, i["mondo"], i["verbatim"], lo, acc))
    return spark.createDataFrame(
        rows, "category string, mondo_id string, verbatims array<string>, lo double, hi double"
    )


# ----------------------------------------------------------------------------------------- sites & subjects
def sites_df(spark: SparkSession, seed: int) -> DataFrame:
    import random

    rows = []
    for study, cfg in STUDY_CFG.items():
        rnd = random.Random(f"{seed}:{study}:sites")
        cw = [w for _, w in COUNTRIES]
        for i in range(cfg["sites"]):
            site = f"SITE-{cfg['site_base'] + i}"
            country = rnd.choices([c for c, _ in COUNTRIES], cw)[0]
            if site == cfg["late_site"]:
                country = "US"
            weight = round(rnd.lognormvariate(0, 0.6), 4)  # skewed recruitment
            if site == cfg["late_site"]:
                weight = max(weight, 1.6)  # a high-enrolling site, so its scheduling problem matters
            rows.append((study, site, country, weight, i))
    return spark.createDataFrame(
        rows, "study_id string, site_id string, country string, recruit_w double, site_ix int"
    )


def subjects(spark: SparkSession, seed: int, scale: str) -> DataFrame:
    import dbldatagen as dg

    sites = sites_df(spark, seed)
    out = []
    for study, cfg in STUDY_CFG.items():
        n = SCALES[scale][study]

        # dbldatagen's random=True columns (rand(seed), distribution UDFs) are not stable under a different
        # execution layout, so every draw is a hash expression of (seed, field, subject id). The spec stays
        # declarative; the output is byte-identical however Spark partitions the work.
        def h(field: str) -> str:
            return f"pmod(xxhash64({seed}, '{field}', '{study}', id), 2147483647) / 2147483647.0"

        base = (
            dg.DataGenerator(spark, name=f"{study}_subjects", rows=n, partitions=4, randomSeed=seed)
            .withIdOutput()
            .withColumn("study_id", "string", values=[study])
            .withColumn(
                "sex", "string", expr=f"case when {h('sex')} < 0.62 then 'F' else 'M' end", baseColumn="id"
            )
            # enrollment ramps up: skewed toward later in the window
            .withColumn("enroll_frac", "double", expr=f"pow({h('enroll')}, 0.7)", baseColumn="id")
            .build()
            .withColumn("subj_ix", F.col("id").cast("long"))
            .drop("id")
        )
        # weighted site choice
        srows = [r for r in sites.where(F.col("study_id") == study).orderBy("site_ix").collect()]
        site = pick(
            U(seed, "site", F.lit(study), F.col("subj_ix")),
            [r.site_id for r in srows],
            [r.recruit_w for r in srows],
        )
        start, end = (date.fromisoformat(d) for d in cfg["enroll"])
        span = (end - start).days
        prof = pick(
            U(seed, "profile", F.lit(study), F.col("subj_ix")),
            [p for p, _ in cfg["profiles"]],
            [w for _, w in cfg["profiles"]],
        )
        df = (
            base.withColumn("site_id", site)
            .withColumn("profile", prof)
            .withColumn("screening_date", F.date_add(F.lit(start), (F.col("enroll_frac") * span).cast("int")))
        )
        out.append(df)
    df = out[0].unionByName(out[1])
    df = df.join(sites.select("study_id", "site_id", "country"), ["study_id", "site_id"])
    # per-site sequence -> USUBJID like CSL-A-118-0007
    w = Window.partitionBy("study_id", "site_id").orderBy("screening_date", "subj_ix")
    df = df.withColumn("site_seq", F.row_number().over(w)).withColumn(
        "usubjid",
        F.concat_ws(
            "-",
            F.col("study_id"),
            F.regexp_extract("site_id", r"(\d+)", 1),
            F.lpad(F.col("site_seq").cast("string"), 4, "0"),
        ),
    )
    k = F.col("usubjid")
    lo_age = F.when(F.col("study_id") == "CSL-A", 18).otherwise(18)
    hi_age = F.when(F.col("study_id") == "CSL-A", 75).otherwise(80)
    age = F.round(F.lit(51.0) + 11.0 * N(seed, "age", k))
    df = df.withColumn(
        "age",
        F.when(F.col("profile") == "AGE_OUT", hi_age + 1 + (U(seed, "ageout", k) * 4).cast("int"))
        .otherwise(F.least(F.greatest(age, lo_age), hi_age))
        .cast("int"),
    )
    height = F.when(F.col("sex") == "F", 163.0 + 6.5 * N(seed, "ht", k)).otherwise(
        177.0 + 7.0 * N(seed, "ht", k)
    )
    df = df.withColumn("height_cm", F.round(F.least(F.greatest(height, F.lit(145.0)), F.lit(203.0)), 1))
    u_bmi = U(seed, "bmi", k)
    bmi = (
        F.when(F.col("profile").isin("BMI27_WRC", "OSA_ONLY", "LOOKALIKE_ONLY"), 27.2 + 2.6 * u_bmi)
        .when(F.col("profile") == "BMI_LOW", 24.2 + 2.6 * u_bmi)
        .when(
            F.col("study_id") == "CSL-B",
            27.4 + F.least(-7.0 * F.log(F.greatest(u_bmi, F.lit(1e-9))), F.lit(22.0)),
        )
        .otherwise(30.3 + F.least(-6.5 * F.log(F.greatest(u_bmi, F.lit(1e-9))), F.lit(19.0)))
    )
    df = df.withColumn("bmi_true", bmi).withColumn(
        "screen_wt_kg", F.round(F.col("bmi_true") * (F.col("height_cm") / 100.0) ** 2, 1)
    )
    # eligibility by construction (the pipeline re-derives it independently from the ontology)
    elig = F.col("profile").isin("BMI30", "BMI27_WRC", "DRUG_ALLERGY", "ELIG_T2D") | (
        (F.col("profile") == "OSA_ONLY") & (F.col("screening_date") >= F.lit(AMENDMENT_2))
    )
    randomized = (elig & (F.col("profile") != "OTHER_FAIL")) | (F.col("profile") == "ERROR_ENROLLED")
    fail_reason = (
        F.when(
            F.col("profile") == "OTHER_FAIL",
            pick(
                U(seed, "ofail", k),
                ["WITHDRAWAL BY SUBJECT", "LAB EXCLUSION", "LOST TO FOLLOW-UP"],
                [55, 30, 15],
            ),
        )
        .when(
            F.col("profile").isin("BMI_LOW", "OSA_ONLY", "LOOKALIKE_ONLY", "NO_T2D", "AGE_OUT"),
            F.lit("INCLUSION CRITERIA NOT MET"),
        )
        .when(F.col("profile").isin("EXCL_MH", "CI_ONLY"), F.lit("EXCLUSION CRITERIA MET"))
        .when(F.col("profile") == "CM_PRE", F.lit("PROHIBITED MEDICATION"))
    )
    gap_lo = F.when(F.col("study_id") == "CSL-A", 14).otherwise(10)
    gap_hi = F.when(F.col("study_id") == "CSL-A", 28).otherwise(21)
    gap = gap_lo + (U(seed, "gap", k) * (gap_hi - gap_lo + 1)).cast("int")
    drug_ratio = F.when(F.col("study_id") == "CSL-A", 2 / 3).otherwise(0.5)
    never_dosed = U(seed, "nodose", k) < 0.004
    df = (
        df.withColumn("randomized", randomized)
        .withColumn("edc_eligible", F.when(randomized, "Y").otherwise("N"))
        .withColumn("screen_fail_reason", F.when(~randomized, fail_reason))
        .withColumn("rand_date", F.when(randomized, F.date_add("screening_date", gap)))
        .withColumn(
            "armcd", F.when(randomized, F.when(U(seed, "arm", k) < drug_ratio, "CSL101").otherwise("PBO"))
        )
        .withColumn("dosed", randomized & ~never_dosed)
        .withColumn("dose_minute", (8 * 60 + U(seed, "dosetime", k) * 180).cast("int"))
        .withColumn(
            "protocol_version_recorded",
            F.when(F.col("study_id") == "CSL-B", "1.0")
            .when(F.col("screening_date") >= F.lit(AMENDMENT_2), "3.0")
            .when(F.col("screening_date") >= F.lit("2025-09-01"), "2.0")
            .otherwise("1.0"),
        )
    )
    # discontinuation (day after first dose), skewed early
    dur = F.when(F.col("study_id") == "CSL-A", 505).otherwise(364)
    disc_p = F.when(F.col("study_id") == "CSL-A", 0.18).otherwise(0.12)
    disc = F.when(
        F.col("dosed") & (U(seed, "disc", k) < disc_p),
        (dur * F.pow(U(seed, "discday", k), 1.4)).cast("int") + 2,
    )
    df = df.withColumn("disc_day", disc).withColumn(
        "disc_reason",
        F.when(
            F.col("disc_day").isNotNull(),
            pick(
                U(seed, "discwhy", k),
                ["ADVERSE EVENT", "WITHDRAWAL BY SUBJECT", "LOST TO FOLLOW-UP", "OTHER"],
                [35, 35, 20, 10],
            ),
        ),
    )
    # individual response (% change at plateau) and on-treatment GLP-1 start (intercurrent event)
    resp = F.when(F.col("armcd") == "CSL101", -13.5 + 6.0 * N(seed, "resp", k)).otherwise(
        -2.2 + 3.5 * N(seed, "resp", k)
    )
    glp_p = (
        F.when((F.col("armcd") == "PBO") & (F.col("country") == "US"), 0.07)
        .when(F.col("dosed"), 0.008)
        .otherwise(0.0)
    )
    df = df.withColumn("resp_pct", resp).withColumn(
        "glp1_start_day",
        F.when(F.col("dosed") & (U(seed, "glp", k) < glp_p), (30 + U(seed, "glpday", k) * 270).cast("int")),
    )
    return df


# --------------------------------------------------------------------------------------------- child tables
def schedule_df(spark: SparkSession, reg: dict) -> DataFrame:
    rows = []
    for study, s in reg["studies"].items():
        for e in s["encounters"]:
            rows.append((study, e["visit"], e["visitnum"], e["target_day"]))
    return spark.createDataFrame(rows, "study_id string, visit string, visitnum int, target_day int")


def visits(subj: DataFrame, sched: DataFrame, seed: int) -> DataFrame:
    """Scheduled + unscheduled visit dates (actual): discontinuation, missed visits and the cutoff apply."""
    s = subj.where("randomized").join(sched, "study_id")
    k, v = F.col("usubjid"), F.col("visit")
    first = F.col("rand_date")
    jitter = F.least(F.greatest(F.round(2.2 * N(seed, "jit", k, v)), F.lit(-6)), F.lit(6)).cast("int")
    late118 = (F.col("site_id") == F.col("late_site")) & (v == "WEEK 24") & (U(seed, "late", k) < 0.7)
    late_any = (v == "WEEK 24") & (U(seed, "late2", k) < 0.03)
    jitter = (
        F.when(late118, 8 + (U(seed, "lated", k) * 6).cast("int"))
        .when(late_any, 8 + (U(seed, "late2d", k) * 9).cast("int"))
        .otherwise(jitter)
    )
    day = F.when(v == "SCREENING", F.datediff("screening_date", first))
    day = day.when(v == "BASELINE", F.lit(0)).when(
        v == "RUN-IN", F.lit(-7) + (U(seed, "runin", k) * 3 - 1).cast("int")
    )
    day = day.otherwise(F.col("target_day") - 1 + jitter)
    s = s.withColumn("late_site", F.when(F.col("study_id") == "CSL-A", F.lit("SITE-118")))
    s = s.withColumn("offset", day).withColumn("svdate", F.date_add(first, F.col("offset")))
    missed = (U(seed, "miss", k, v) < 0.03) & ~v.isin("SCREENING", "BASELINE", "RUN-IN")
    keep = (
        ~missed
        & (F.col("svdate") <= F.lit(DATA_CUTOFF))
        & (
            F.col("disc_day").isNull()
            | (F.col("offset") + 1 <= F.col("disc_day"))
            | v.isin("SCREENING", "RUN-IN")
        )
        & (F.col("dosed") | v.isin("SCREENING", "RUN-IN"))
    )
    sched_v = s.where(keep).select("study_id", "usubjid", "visit", "visitnum", "offset", "svdate")
    uns = (
        s.where(keep & ~v.isin("SCREENING", "RUN-IN") & (U(seed, "uns", k, v) < 0.035))
        .withColumn("offset", F.col("offset") + 1 + (U(seed, "unsd", k, v) * 12).cast("int"))
        .withColumn("svdate", F.date_add(first, F.col("offset")))
        .where(F.col("svdate") <= F.lit(DATA_CUTOFF))
        .select(
            "study_id",
            "usubjid",
            F.concat(F.lit("UNSCHEDULED "), F.col("visitnum").cast("string"), F.lit(".01")).alias("visit"),
            (F.col("visitnum") + F.lit(0.01)).alias("visitnum"),
            "offset",
            "svdate",
        )
    )
    return sched_v.withColumn("visitnum", F.col("visitnum").cast("double")).unionByName(uns)


def vitals(subj: DataFrame, sv: DataFrame, seed: int) -> DataFrame:
    """Weight at every visit (plus height at screening; BP/pulse/waist), recorded as sites key them."""
    s = subj.select(
        "usubjid",
        "study_id",
        "country",
        "screening_date",
        "height_cm",
        "screen_wt_kg",
        "armcd",
        "resp_pct",
        "glp1_start_day",
        "dose_minute",
        "randomized",
        "rand_date",
    )
    k = F.col("usubjid")
    # screening-only rows for screen failures
    sf = s.where(~F.col("randomized")).select(
        "usubjid",
        "study_id",
        F.lit("SCREENING").alias("visit"),
        F.lit(1.0).alias("visitnum"),
        F.lit(None).cast("int").alias("offset"),
        F.col("screening_date").alias("svdate"),
    )
    allv = sv.unionByName(sf)
    x = allv.join(s, ["usubjid", "study_id"])
    v = F.col("visit")
    t = F.col("offset") + 1  # study day for post-dose visits
    w0 = F.col("screen_wt_kg") + (-0.4 + 0.7 * N(seed, "w0", k))
    tau = F.when(F.col("armcd") == "CSL101", 60.0).otherwise(45.0)
    trend = F.when(t > 1, F.col("resp_pct") * (1 - F.exp(-(t - 1) / tau))).otherwise(F.lit(0.0))
    glp = F.when(
        F.col("glp1_start_day").isNotNull() & (t > F.col("glp1_start_day")),
        -8.0 * (1 - F.exp(-(t - F.col("glp1_start_day")) / 50.0)),
    ).otherwise(F.lit(0.0))
    kg = F.when(v == "SCREENING", F.col("screen_wt_kg")).otherwise(
        w0 * (1 + (trend + glp) / 100.0) + 0.55 * N(seed, "wn", k, v)
    )
    x = x.withColumn("kg", kg)
    # time-of-day: baseline weighed before the dose (96%), without a time (3%), after the dose (1%)
    ub = U(seed, "bltime", k)
    minute = F.when(
        v == "BASELINE",
        F.when(ub < 0.96, F.col("dose_minute") - 15 - (U(seed, "blmin", k) * 45).cast("int"))
        .when(ub < 0.99, F.lit(None))
        .otherwise(F.col("dose_minute") + 20),
    )
    x = x.withColumn("minute", minute.cast("int"))
    rows = [x.withColumn("vstestcd", F.lit("WEIGHT"))]
    rows.append(x.where(v == "SCREENING").withColumn("vstestcd", F.lit("HEIGHT")))
    for tc in ("SYSBP", "DIABP", "PULSE"):
        rows.append(x.where(~v.startswith("UNSCHEDULED")).withColumn("vstestcd", F.lit(tc)))
    rows.append(
        x.where(v.isin("BASELINE", "WEEK 24", "WEEK 72", "WEEK 52")).withColumn("vstestcd", F.lit("WSTCIR"))
    )
    y = rows[0]
    for r in rows[1:]:
        y = y.unionByName(r)
    tc = F.col("vstestcd")
    us = F.col("country") == "US"
    u_unit = U(seed, "unit", k, v, tc)
    unit = (
        F.when(
            tc == "WEIGHT",
            F.when(us & (u_unit < 0.8), "lb")
            .when((F.col("country") == "GB") & (u_unit < 0.004), "st")
            .otherwise("kg"),
        )
        .when(tc.isin("HEIGHT", "WSTCIR"), F.when(us & (u_unit < 0.8), "in").otherwise("cm"))
        .when(tc.isin("SYSBP", "DIABP"), F.lit("mmHg"))
        .otherwise(F.lit("bpm"))
    )
    val = (
        F.when(
            tc == "WEIGHT",
            F.when(unit == "lb", F.col("kg") * LB_PER_KG)
            .when(unit == "st", F.col("kg") / KG_PER_STONE)
            .otherwise(F.col("kg")),
        )
        .when(tc == "HEIGHT", F.when(unit == "in", F.col("height_cm") / 2.54).otherwise(F.col("height_cm")))
        .when(
            tc == "WSTCIR",
            (F.col("kg") * 0.62 + 52 + 3 * N(seed, "waist", k, v))
            / F.when(unit == "in", 2.54).otherwise(1.0),
        )
        .when(tc == "SYSBP", 131 + 0.25 * (F.col("kg") - F.col("screen_wt_kg")) + 13 * N(seed, "sbp", k, v))
        .when(tc == "DIABP", 82 + 0.12 * (F.col("kg") - F.col("screen_wt_kg")) + 8 * N(seed, "dbp", k, v))
        .otherwise(F.when(F.col("armcd") == "CSL101", 76).otherwise(73) + 8 * N(seed, "pulse", k, v))
    )
    digits = F.when(tc.isin("SYSBP", "DIABP", "PULSE"), 0).otherwise(1)
    y = y.withColumn("vsorresu_raw", unit).withColumn("value", val).withColumn("digits", digits)
    # data-quality noise (small, realistic rates). Eligibility-critical screening fields (weight, height)
    # are hard-required by EDC edit checks, so they never get it.
    critical = (v == "SCREENING") & tc.isin("WEIGHT", "HEIGHT")
    q = F.when(critical, F.lit(0.5)).otherwise(U(seed, "dq", k, v, tc))
    status = F.when(q < 0.007, "NOT DONE")
    y = (
        y.withColumn("vsstat", status)
        .withColumn(
            "vsorres_raw",
            F.when(q < 0.010, F.lit(""))
            .when((q < 0.0105) & (tc == "WEIGHT"), F.lit("0"))
            .otherwise(
                F.when(F.col("digits") == 0, F.round("value").cast("int").cast("string")).otherwise(
                    F.format_number(F.col("value"), 1)
                )
            ),
        )
        .withColumn(
            "vsorresu_raw",
            F.when((q > 0.9985) & (tc == "WEIGHT"), F.lit("")).otherwise(F.col("vsorresu_raw")),
        )
        .withColumn("vsorres_raw", F.regexp_replace("vsorres_raw", ",", ""))
    )
    hhmm = F.concat(
        F.lit("T"),
        F.lpad((F.col("minute") / 60).cast("int").cast("string"), 2, "0"),
        F.lit(":"),
        F.lpad((F.col("minute") % 60).cast("string"), 2, "0"),
    )
    y = y.withColumn(
        "vsdtc",
        F.concat(fmt_date(F.col("svdate")), F.when(F.col("minute").isNotNull(), hhmm).otherwise(F.lit(""))),
    )
    # duplicate entry (same timestamp, value, unit) for 0.25% of weight records
    dup = y.where((tc == "WEIGHT") & (U(seed, "dup", k, v) < 0.0025))
    y = y.unionByName(dup)
    order = Window.partitionBy("usubjid").orderBy(
        "svdate", "visitnum", "vstestcd", "vsorres_raw", F.col("minute").asc_nulls_first()
    )
    y = y.withColumn("vsseq", F.row_number().over(order))
    return y.select(
        F.concat(F.lit("EDC-VS-"), k, F.lit("-"), F.col("vsseq").cast("string")).alias("record_id"),
        "study_id",
        "usubjid",
        "vsseq",
        "visit",
        F.col("visitnum").cast("string").alias("visitnum"),
        "vsdtc",
        "vstestcd",
        F.col("vsorres_raw").alias("vsorres"),
        F.col("vsorresu_raw").alias("vsorresu"),
        F.coalesce(F.col("vsstat"), F.lit("")).alias("vsstat"),
    )


def exposure(subj: DataFrame, sv: DataFrame) -> DataFrame:
    """One EX record per dosing period: from each dosing visit to the day before the next one."""
    dosing = sv.where(~F.col("visit").isin("SCREENING", "RUN-IN") & ~F.col("visit").startswith("UNSCHEDULED"))
    s = subj.where("dosed").select("usubjid", "armcd", "dose_minute", "disc_day")
    d = dosing.join(s, "usubjid")
    w = Window.partitionBy("usubjid").orderBy("offset")
    d = d.withColumn("next_offset", F.lead("offset").over(w)).withColumn("exseq", F.row_number().over(w))
    end_off = F.coalesce(
        F.col("next_offset") - 1,
        F.least(F.coalesce(F.col("disc_day") - 1, F.col("offset") + 27), F.col("offset") + 27),
    )
    start = F.concat(
        fmt_date(F.col("svdate")),
        F.when(
            F.col("visit") == "BASELINE",
            F.concat(
                F.lit("T"),
                F.lpad((F.col("dose_minute") / 60).cast("int").cast("string"), 2, "0"),
                F.lit(":"),
                F.lpad((F.col("dose_minute") % 60).cast("string"), 2, "0"),
            ),
        ).otherwise(F.lit("")),
    )
    return d.select(
        F.concat(F.lit("EDC-EX-"), F.col("usubjid"), F.lit("-"), F.col("exseq").cast("string")).alias(
            "record_id"
        ),
        "study_id",
        "usubjid",
        "exseq",
        F.when(F.col("armcd") == "CSL101", "CSL-101").otherwise("PLACEBO").alias("extrt"),
        F.when(F.col("armcd") == "CSL101", "10").otherwise("0").alias("exdose"),
        F.lit("mg").alias("exdosu"),
        F.lit("SUBCUTANEOUS").alias("exroute"),
        F.lit("1 TIME PER WEEK").alias("exdosfrq"),
        start.alias("exstdtc"),
        fmt_date(F.date_add(F.col("svdate"), (end_off - F.col("offset")).cast("int"))).alias("exendtc"),
    )


def medical_history(spark: SparkSession, subj: DataFrame, terms: DataFrame, seed: int) -> DataFrame:
    """MH slots by profile. Slot 0 is the profile's anchor; later slots add realistic co-occurring history."""
    p, st = F.col("profile"), F.col("study_id")
    slots = spark.range(6).withColumnRenamed("id", "slot")
    x = subj.crossJoin(slots)
    k, sl = F.col("usubjid"), F.col("slot")
    u = U(seed, "mhp", k, sl)
    no_wrc = p.isin("OSA_ONLY", "LOOKALIKE_ONLY")
    anchor = (
        F.when(p == "BMI27_WRC", "wrc")
        .when(p == "OSA_ONLY", "osa")
        .when(p == "LOOKALIKE_ONLY", "non_member_lookalike")
        .when(p == "EXCL_MH", "exclusion")
        .when(p == "CI_ONLY", "ci_only")
        .when(p == "DRUG_ALLERGY", "drug_allergy")
        .when(p == "ERROR_ENROLLED", F.when(U(seed, "err", k) < 0.6, "exclusion").otherwise("ci_only"))
    )
    cat = (
        F.when(
            sl == 0,
            F.when(st == "CSL-B", F.when(p == "NO_T2D", F.lit(None)).otherwise(F.lit("t2d"))).otherwise(
                anchor
            ),
        )
        .when(
            sl == 1,
            F.when(st == "CSL-B", anchor).when(
                ~no_wrc & (u < F.when(p == "BMI30", 0.62).otherwise(0.4)), "wrc"
            ),
        )
        .when(sl == 2, F.when(~no_wrc & (u < 0.3), F.when(p == "NO_T2D", "wrc_not_t2d").otherwise("wrc")))
        .when(
            sl == 3,
            F.when((st == "CSL-A") & p.isin("BMI30", "BMI27_WRC") & (u < 0.22), "osa").when(
                (st == "CSL-B") & (u < 0.03), "b_retinopathy"
            ),
        )
        .when(sl == 4, F.when(u < 0.55, "background"))
        .when(sl == 5, F.when(u < 0.25, "background"))
    )
    x = x.withColumn("category", cat).where(F.col("category").isNotNull())
    # special categories resolve to fixed terms
    fixed = {"t2d": "MONDO:0005148", "drug_allergy": "MONDO:0000775", "b_retinopathy": "MONDO:0005266"}
    tsel = F.col("category")
    x = x.withColumn(
        "lookup_cat", F.when(tsel == "wrc_not_t2d", "wrc").when(tsel.isin(*fixed), None).otherwise(tsel)
    )
    x = x.withColumn("ut", U(seed, "mht", k, sl))
    t = terms.withColumnRenamed("category", "t_cat")
    joined = x.join(
        t,
        (F.col("lookup_cat") == F.col("t_cat")) & (F.col("ut") >= F.col("lo")) & (F.col("ut") < F.col("hi")),
        "left",
    )
    vb = F.col("verbatims")
    fixed_expr = (
        F.when(tsel == "t2d", F.lit(fixed["t2d"]))
        .when(tsel == "drug_allergy", F.lit(fixed["drug_allergy"]))
        .when(tsel == "b_retinopathy", F.lit(fixed["b_retinopathy"]))
    )
    fixed_verb = (
        F.when(tsel == "t2d", F.lit("type 2 diabetes"))
        .when(tsel == "drug_allergy", F.lit("penicillin allergy"))
        .when(tsel == "b_retinopathy", F.lit("background diabetic retinopathy"))
    )
    j = joined.withColumn("mondo", F.coalesce(fixed_expr, F.col("mondo_id"))).withColumn(
        "term",
        F.coalesce(fixed_verb, F.element_at(vb, (U(seed, "verb", k, sl) * F.size(vb)).cast("int") + 1)),
    )
    j = j.where(~((tsel == "wrc_not_t2d") & (F.col("mondo") == "MONDO:0005148")))
    # Study B allows diabetic retinopathy history (EXC-MH except_roots): never use it as a B exclusion anchor
    b_ret = (F.col("study_id") == "CSL-B") & (tsel == "exclusion") & (F.col("mondo") == "MONDO:0005266")
    j = j.withColumn(
        "term", F.when(b_ret, F.lit("chronic pancreatitis")).otherwise(F.col("term"))
    ).withColumn("mondo", F.when(b_ret, F.lit("MONDO:0005003")).otherwise(F.col("mondo")))
    j = j.dropDuplicates(["usubjid", "mondo"])
    yr = F.year("screening_date") - 1 - (U(seed, "mhy", k, sl) * 14).cast("int")
    mo = F.lpad((1 + (U(seed, "mhm", k, sl) * 12).cast("int")).cast("string"), 2, "0")
    onset = F.when(U(seed, "mhprec", k, sl) < 0.4, F.concat(yr.cast("string"), F.lit("-"), mo)).otherwise(
        yr.cast("string")
    )
    w = Window.partitionBy("usubjid").orderBy("slot", "mondo")
    j = j.withColumn("mhseq", F.row_number().over(w))
    return j.select(
        F.concat(F.lit("EDC-MH-"), k, F.lit("-"), F.col("mhseq").cast("string")).alias("record_id"),
        "study_id",
        "usubjid",
        "mhseq",
        F.col("term").alias("mhterm"),
        F.col("mondo").alias("mhdecod_mondo"),
        onset.alias("mhstdtc"),
    )


def con_meds(spark: SparkSession, subj: DataFrame, mh: DataFrame, terms: dict, seed: int) -> DataFrame:
    bg = spark.createDataFrame(
        [
            (d["with"], d["rxnorm"], d["ingredient"], d["verbatim"], float(d["weight"]))
            for d in terms["drugs"]["background"]
        ],
        "mondo string, rxnorm string, ingredient string, verbatims array<string>, w double",
    )
    tot = bg.groupBy("mondo").agg(F.sum("w").alias("tw"))
    cum = Window.partitionBy("mondo").orderBy("rxnorm").rowsBetween(Window.unboundedPreceding, 0)
    bg = (
        bg.join(tot, "mondo")
        .withColumn("hi", F.sum("w").over(cum) / F.col("tw"))
        .withColumn("lo", F.col("hi") - F.col("w") / F.col("tw"))
    )
    m = mh.select("usubjid", "mhseq", F.col("mhdecod_mondo").alias("mondo")).join(
        subj.select("usubjid", "screening_date", "profile", "rand_date", "glp1_start_day"), "usubjid"
    )
    k = F.col("usubjid")
    m = m.where(U(seed, "cmtake", k, F.col("mhseq")) < 0.75).withColumn(
        "u", U(seed, "cmpick", k, F.col("mhseq"))
    )
    a = m.join(bg, "mondo").where((F.col("u") >= F.col("lo")) & (F.col("u") < F.col("hi")))
    start_bg = F.date_add("screening_date", -(60 + (U(seed, "cmst", k, F.col("rxnorm")) * 2500).cast("int")))
    a = a.select(
        "usubjid",
        "rxnorm",
        "verbatims",
        fmt_date(start_bg).alias("cmstdtc"),
        F.lit("").alias("cmendtc"),
        F.lit(1).alias("src"),
    )

    # prohibited pre-screening (CM_PRE): stopped 10-85 days before screening, or still ongoing
    def drug_rows(group: str) -> DataFrame:
        rows = [(d["rxnorm"], d["verbatim"], float(d["weight"])) for d in terms["drugs"][group]]
        return spark.createDataFrame(rows, "rxnorm string, verbatims array<string>, w double")

    pre = drug_rows("prohibited_pre_screening")
    pre_items = [r.rxnorm for r in pre.collect()]
    pre_w = [r.w for r in pre.collect()]
    s = subj.where(F.col("profile") == "CM_PRE")
    s = s.withColumn("rxnorm", pick(U(seed, "prerx", k), pre_items, pre_w)).join(pre.drop("w"), "rxnorm")
    ongoing = U(seed, "preon", k) < 0.3
    s = s.select(
        "usubjid",
        "rxnorm",
        "verbatims",
        fmt_date(F.date_add("screening_date", -(120 + (U(seed, "prest", k) * 200).cast("int")))).alias(
            "cmstdtc"
        ),
        F.when(ongoing, F.lit(""))
        .otherwise(fmt_date(F.date_add("screening_date", -(10 + (U(seed, "preend", k) * 75).cast("int")))))
        .alias("cmendtc"),
        F.lit(2).alias("src"),
    )
    ont = drug_rows("on_treatment_glp1")
    ont_items = [r.rxnorm for r in ont.collect()]
    ont_w = [r.w for r in ont.collect()]
    g = subj.where(F.col("glp1_start_day").isNotNull())
    g = g.withColumn("rxnorm", pick(U(seed, "glprx", k), ont_items, ont_w)).join(ont.drop("w"), "rxnorm")
    g = g.select(
        "usubjid",
        "rxnorm",
        "verbatims",
        fmt_date(F.date_add("rand_date", F.col("glp1_start_day") - 1)).alias("cmstdtc"),
        F.lit("").alias("cmendtc"),
        F.lit(3).alias("src"),
    )
    allcm = a.unionByName(s).unionByName(g).dropDuplicates(["usubjid", "rxnorm", "src"])
    allcm = allcm.join(subj.select("usubjid", "study_id"), "usubjid")
    w = Window.partitionBy("usubjid").orderBy("cmstdtc", "rxnorm")
    allcm = allcm.withColumn("cmseq", F.row_number().over(w))
    vb = F.col("verbatims")
    return allcm.select(
        F.concat(F.lit("EDC-CM-"), k, F.lit("-"), F.col("cmseq").cast("string")).alias("record_id"),
        "study_id",
        "usubjid",
        "cmseq",
        F.element_at(vb, (U(seed, "cmverb", k, F.col("rxnorm")) * F.size(vb)).cast("int") + 1).alias("cmtrt"),
        F.col("rxnorm").alias("cmdecod_rxnorm"),
        "cmstdtc",
        "cmendtc",
    )


def disposition(subj: DataFrame) -> DataFrame:
    sf = subj.where(~F.col("randomized")).select(
        "study_id",
        "usubjid",
        F.lit("SCREEN FAILURE").alias("dsdecod"),
        F.col("screen_fail_reason").alias("dsterm"),
        fmt_date(F.date_add("screening_date", 7)).alias("dsstdtc"),
    )
    rnd = subj.where("randomized").select(
        "study_id",
        "usubjid",
        F.lit("RANDOMIZED").alias("dsdecod"),
        F.lit("RANDOMIZED").alias("dsterm"),
        fmt_date("rand_date").alias("dsstdtc"),
    )
    nd = subj.where(F.col("randomized") & ~F.col("dosed")).select(
        "study_id",
        "usubjid",
        F.lit("WITHDRAWAL BY SUBJECT").alias("dsdecod"),
        F.lit("withdrew before first dose").alias("dsterm"),
        fmt_date(F.date_add("rand_date", 1)).alias("dsstdtc"),
    )
    disc = subj.where(F.col("disc_day").isNotNull()).select(
        "study_id",
        "usubjid",
        F.col("disc_reason").alias("dsdecod"),
        F.col("disc_reason").alias("dsterm"),
        fmt_date(F.date_add("rand_date", F.col("disc_day") - 1)).alias("dsstdtc"),
    )
    dur = F.when(F.col("study_id") == "CSL-A", 505).otherwise(364)
    done = (
        subj.where(F.col("dosed") & F.col("disc_day").isNull())
        .withColumn("end", F.date_add("rand_date", dur + 7))
        .where(F.col("end") <= F.lit(DATA_CUTOFF))
        .select(
            "study_id",
            "usubjid",
            F.lit("COMPLETED").alias("dsdecod"),
            F.lit("COMPLETED").alias("dsterm"),
            fmt_date("end").alias("dsstdtc"),
        )
    )
    out = (
        sf.unionByName(rnd)
        .unionByName(nd)
        .unionByName(disc.where(F.col("dsstdtc") <= F.lit(DATA_CUTOFF)))
        .unionByName(done)
    )
    w = Window.partitionBy("usubjid").orderBy("dsstdtc", "dsdecod")
    out = out.withColumn("dsseq", F.row_number().over(w))
    return out.select(
        F.concat(F.lit("EDC-DS-"), F.col("usubjid"), F.lit("-"), F.col("dsseq").cast("string")).alias(
            "record_id"
        ),
        "study_id",
        "usubjid",
        "dsseq",
        "dsdecod",
        "dsterm",
        "dsstdtc",
    )


# ------------------------------------------------------------------------------------------- named fixtures
def named_rows() -> dict[str, list[dict]]:
    """The hand-authored participants in the same raw schema (strings exactly as in the YAML)."""
    with open(HERE / "fixtures" / "named_participants.yaml", encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    out: dict[str, list[dict]] = {t: [] for t in ("subjects", "vs", "ex", "mh", "cm", "ds", "sv")}
    for p in spec["participants"]:
        study = p.get("study_id", "CSL-A")
        d = {**spec["defaults"][study], **p, "study_id": study}
        u = d["usubjid"]
        first = d["exposures"][0]["exstdtc"][:10] if d["exposures"] else None
        out["subjects"].append(
            {
                "record_id": f"EDC-DM-{u}",
                "study_id": study,
                "site_id": d["site"],
                "country": "US",
                "usubjid": u,
                "screening_date": d["screening_date"],
                "age": str(d["age"]),
                "sex": d["sex"],
                "screen_outcome": "RANDOMIZED" if d["randomized"] else "SCREEN FAILED",
                "screen_fail_reason": "" if d["randomized"] else "SEE ELIGIBILITY",
                "rand_date": first or (d["screening_date"] if d["randomized"] else ""),
                "armcd": d["arm"] if d["randomized"] else "",
                "edc_eligible": d["edc_eligible"],
                "protocol_version_recorded": "",
                "named_fixture": "Y",
            }
        )
        for w in d["weights"]:
            out["vs"].append(
                {
                    "record_id": f"EDC-VS-{u}-W{w['vsseq']}",
                    "study_id": study,
                    "usubjid": u,
                    "vsseq": str(w["vsseq"]),
                    "visit": w["visit"],
                    "visitnum": "",
                    "vsdtc": w["vsdtc"],
                    "vstestcd": "WEIGHT",
                    "vsorres": w["orres"],
                    "vsorresu": w["unit"],
                    "vsstat": w.get("status") or "",
                }
            )
        out["vs"].append(
            {
                "record_id": f"EDC-VS-{u}-H1",
                "study_id": study,
                "usubjid": u,
                "vsseq": "900",
                "visit": "SCREENING",
                "visitnum": "",
                "vsdtc": d["screening_date"],
                "vstestcd": "HEIGHT",
                "vsorres": str(d["height_cm"]),
                "vsorresu": "cm",
                "vsstat": "",
            }
        )
        for i, e in enumerate(d["exposures"], 1):
            out["ex"].append(
                {
                    "record_id": f"EDC-EX-{u}-{i}",
                    "study_id": study,
                    "usubjid": u,
                    "exseq": str(i),
                    "extrt": "CSL-101",
                    "exdose": str(e["exdose"]),
                    "exdosu": e["exdosu"],
                    "exroute": "SUBCUTANEOUS",
                    "exdosfrq": "1 TIME PER WEEK",
                    "exstdtc": e["exstdtc"],
                    "exendtc": "",
                }
            )
        for m in d.get("mh", []):
            out["mh"].append(
                {
                    "record_id": f"EDC-MH-{u}-{m['mhseq']}",
                    "study_id": study,
                    "usubjid": u,
                    "mhseq": str(m["mhseq"]),
                    "mhterm": m["term"],
                    "mhdecod_mondo": m["mondo_id"],
                    "mhstdtc": str(m.get("mhstdtc", "")),
                }
            )
        for m in d.get("cm", []):
            out["cm"].append(
                {
                    "record_id": f"EDC-CM-{u}-{m['cmseq']}",
                    "study_id": study,
                    "usubjid": u,
                    "cmseq": str(m["cmseq"]),
                    "cmtrt": m["term"],
                    "cmdecod_rxnorm": m["rxnorm"],
                    "cmstdtc": str(m.get("cmstdtc", "")),
                    "cmendtc": str(m.get("cmendtc", "")),
                }
            )
        out["ds"].append(
            {
                "record_id": f"EDC-DS-{u}-1",
                "study_id": study,
                "usubjid": u,
                "dsseq": "1",
                "dsdecod": "RANDOMIZED" if d["randomized"] else "SCREEN FAILURE",
                "dsterm": "RANDOMIZED" if d["randomized"] else "SEE ELIGIBILITY",
                "dsstdtc": first or d["screening_date"],
            }
        )
    return out


# -------------------------------------------------------------------------------------------- orchestration
def to_strings(df: DataFrame) -> DataFrame:
    return df.select([F.coalesce(F.col(c).cast("string"), F.lit("")).alias(c) for c in df.columns])


def generate(spark: SparkSession, out: str, scale: str = "demo", seed: int = 2026) -> dict:
    reg = load_registry()
    terms = load_terms()
    subj = subjects(spark, seed, scale)
    sv = visits(subj, schedule_df(spark, reg), seed)
    tables: dict[str, DataFrame] = {
        "subjects": subj.select(
            F.concat(F.lit("EDC-DM-"), F.col("usubjid")).alias("record_id"),
            "study_id",
            "site_id",
            "country",
            "usubjid",
            fmt_date("screening_date").alias("screening_date"),
            "age",
            "sex",
            F.when(F.col("randomized"), "RANDOMIZED").otherwise("SCREEN FAILED").alias("screen_outcome"),
            "screen_fail_reason",
            fmt_date("rand_date").alias("rand_date"),
            "armcd",
            "edc_eligible",
            "protocol_version_recorded",
            F.lit("N").alias("named_fixture"),
        ),
        "vs": vitals(subj, sv, seed),
        "ex": exposure(subj, sv),
        "mh": medical_history(spark, subj, term_df(spark, terms), seed),
        "ds": disposition(subj),
        "sv": sv.select(
            F.concat(F.lit("EDC-SV-"), F.col("usubjid"), F.lit("-"), F.col("visit")).alias("record_id"),
            "study_id",
            "usubjid",
            "visit",
            F.col("visitnum").cast("string").alias("visitnum"),
            fmt_date("svdate").alias("svstdtc"),
        ),
    }
    tables["cm"] = con_meds(spark, subj, tables["mh"], terms, seed)
    named = named_rows()
    counts = {}
    for name, df in tables.items():
        df = to_strings(df)
        if named.get(name):
            cols = df.columns
            nd = spark.createDataFrame(
                [{c: r.get(c, "") for c in cols} for r in named[name]], ", ".join(f"{c} string" for c in cols)
            )
            df = df.unionByName(nd)
        keys = [c for c in ("study_id", "usubjid", "record_id") if c in df.columns]
        df = df.repartition(1).sortWithinPartitions(*keys)
        df.write.mode("overwrite").option("header", True).option("quoteAll", True).csv(f"{out}/{name}")
        counts[name] = df.count()
    manifest = {
        "generator_version": GENERATOR_VERSION,
        "seed": seed,
        "scale": scale,
        "data_cutoff": DATA_CUTOFF,
        "registry_version": reg["registry_version"],
        "row_counts": counts,
        "synthetic": True,
        "note": "SYNTHETIC educational data. Not derived from any real trial or product.",
    }
    if out.startswith("/Volumes/") or Path(out).parent.exists():
        Path(out).mkdir(parents=True, exist_ok=True)
        Path(out, "_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--scale", choices=sorted(SCALES), default="demo")
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()
    spark = SparkSession.builder.getOrCreate()
    print(json.dumps(generate(spark, a.out, a.scale, a.seed), indent=2))


if __name__ == "__main__":
    main()
