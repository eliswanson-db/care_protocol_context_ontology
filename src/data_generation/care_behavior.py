"""Generative care-behavior model — realistic, emergent heterogeneity (NOT point injection).

The problem this solves: raw Synthea is stationary and uniform — every care-process rate is flat, so the
protocol watch has nothing to detect, MAD saturates at PDC=1.0, and nobody is in poor control. The WRONG fix
is to slam a few patients to extremes or cliff-drop one unit in Q3 — an analyst would spot that as fake, and
it pre-wires the answer.

Instead, every cohort patient gets a seeded behavioral model and the aggregate rates — and all their variation
across clinics, panels, and time — EMERGE from thousands of individual deterministic Bernoulli draws:

  latent factors   engagement E_p (drawn); complexity C_p (REAL: distinct ICD-10 codes the patient carries);
                    adherence a_p and glycemic control, both functions of the above
  structure         patient -> panel (PCP) -> clinic; clinics ordered along a complexity gradient
  group effect      provider/panel random effect u_k (smooth spread, not two buckets)
  time              mild seasonality + ONE clinic's mid-year coverage disruption that adds a GRADUAL, decaying
                    gap term (ramps then recovers — never a cliff), confounded with that clinic's higher
                    patient complexity (so a naive look blames case-mix, not the disruption)

Three measure-relevant outputs, kept cleanly separable so recomputed golds == model truth:
  * PROTOCOL follow-up: triggers are the RECORDED bronze high-A1c results (we do not rewrite A1c values, so no
    self-satisfying adjacent tests). For each trigger, follow-up is a modeled Bernoulli draw; a followed
    trigger emits a MARKED recheck A1c (excluded from triggers) that the protocol measure counts.
  * MEDICATION adherence: fills modeled per 30-day cycle, kept with prob a_p -> continuous PDC.
  * GLYCEMIC control: a patient ATTRIBUTE (glycemic_poor + modeled_a1c) on the roster, read by GSD. It does NOT
    edit the observation stream, so it can't perturb protocol triggers.

Nothing is set to an answer. clinic_id / panel_id / glycemic_poor / the transition are plain DIMENSIONS; the
cause of any drift is discoverable only by joining drift x clinic x transition x case-mix x time. Draws are
deterministic (seeded xxhash) so golds are reproducible.

Writes panel_roster / panel_pcp_transition / the effective event layer (care_order_results, care_order_med),
and prints the distributions. Measures reads this layer (ADR-0012).

Serverless spark_python_task. Runs AFTER epicize, BEFORE measures. Idempotent (rebuilds from pristine bronze).
"""
import argparse

from pyspark.sql import SparkSession, functions as F
from pyspark.sql.window import Window

N_PANELS = 40
N_CLINICS = 8                     # ~5 panels/clinic -> the disrupted clinic has enough triggers to show drift
MY = 2025
MY_START, MY_END = f"{MY}-01-01", f"{MY}-12-31"
A1C_TRIGGER = 7.0
FOLLOWUP_DAYS = 90
TRANSITION_DATE = f"{MY}-07-15"
GAP_RECOVERY_DAYS = 150
RECHECK_TAG = "Hemoglobin A1c (recheck)"

FU_B0 = 0.20                      # baseline timely-follow-up ~ logistic(0.20) ≈ 55%
FU_BE = 1.30
FU_BC = -0.45
FU_SIGMA = 0.55
FU_SEASON = 0.15
FU_GAP_PEAK = 1.80

AD_B0, AD_BE, AD_BC, AD_SIGMA = 1.1, 0.9, -0.3, 0.35
CT_B0, CT_ADH, CT_BE = 0.85, 1.70, 0.50                # P(controlled); ~17% poor


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--schema", default="care_protocol")
    ap.add_argument("--seed", default="20261029")
    ap.add_argument("--intensity", type=float, default=1.0, help="Scales the clinic disruption severity (0..1).")
    args = ap.parse_args()

    spark = SparkSession.builder.getOrCreate()
    g = f"{args.catalog}.{args.schema}"
    term = f"{args.catalog}.care_protocol_terminology"
    seed = args.seed

    def u(stream, *cols):
        parts = [F.lit(f"{seed}:{stream}")] + [(F.col(c) if isinstance(c, str) else c).cast("string") for c in cols]
        return F.pmod(F.xxhash64(F.concat_ws("|", *parts)), F.lit(1_000_000)).cast("double") / F.lit(1_000_000.0)

    def unorm(stream, *cols):
        s = sum((u(f"{stream}{i}", *cols) for i in range(4)), F.lit(0.0))
        return (s - F.lit(2.0)) / F.lit(0.5774)

    sig = lambda x: F.lit(1.0) / (F.lit(1.0) + F.exp(-x))

    # ---------- cohort + REAL complexity ----------
    closure = (spark.table(f"{term}.icd10_closure").where(F.col("ancestor_code").isin("E10", "E11", "E13"))
               .select("descendant_code").distinct())
    dx = spark.table(f"{g}.bronze_pat_enc_dx").where(F.col("icd10_code").isNotNull())
    cohort = (dx.join(closure, dx["icd10_code"] == closure["descendant_code"]).select("patient_id").distinct())
    complexity = dx.groupBy("patient_id").agg(F.countDistinct("icd10_code").alias("complexity"))
    cstats = complexity.join(cohort, "patient_id").agg(
        F.avg("complexity").alias("m"), F.stddev_pop("complexity").alias("sd")).collect()[0]
    c_mean, c_sd = cstats["m"], (cstats["sd"] or 1.0)

    patients = spark.table(f"{g}.bronze_patient")
    roster = (cohort.join(patients, "patient_id").join(complexity, "patient_id", "left")
              .withColumn("complexity", F.coalesce("complexity", F.lit(1)))
              .withColumn("age", (F.datediff(F.lit(MY_END), F.col("birth_date")) / 365.25).cast("int"))
              .withColumn("c_std", (F.col("complexity") - F.lit(c_mean)) / F.lit(c_sd))
              .withColumn("engagement", u("eng", "patient_id"))
              .withColumn("panel_num", F.pmod(F.xxhash64(F.concat_ws("|", F.lit(f"{seed}:panel"), F.col("patient_id"))),
                                              F.lit(N_PANELS)))
              .withColumn("panel_id", F.concat(F.lit("PANEL-"), F.lpad(F.col("panel_num").cast("string"), 2, "0")))
              .withColumn("pcp_id", F.concat(F.lit("PCP-"), F.lpad(F.col("panel_num").cast("string"), 2, "0"))))

    panel_eff = roster.select("panel_id").distinct().withColumn("u_panel", unorm("prov", "panel_id"))
    panel_mix = roster.groupBy("panel_id").agg(F.avg("c_std").alias("panel_c_std"), F.count("*").alias("panel_n"))
    clinic_assign = (panel_mix.withColumn("clinic_num", F.ntile(N_CLINICS).over(Window.orderBy("panel_c_std")))
                     .withColumn("clinic_id", F.concat(F.lit("CLINIC-"), F.lpad(F.col("clinic_num").cast("string"), 2, "0")))
                     .select("panel_id", "clinic_id", "clinic_num"))
    drift_clinic = f"CLINIC-{N_CLINICS:02d}"
    print(f"care_behavior: disrupted clinic = {drift_clinic} (highest-complexity site; the confound is real).")
    roster = (roster.join(panel_eff, "panel_id").join(clinic_assign, "panel_id")
              .withColumn("is_handoff", F.col("clinic_id") == F.lit(drift_clinic)))

    transition = spark.createDataFrame(
        [(drift_clinic, "departure+locum", TRANSITION_DATE, GAP_RECOVERY_DAYS,
          "Mid-year PCP departure at the clinic; panel covered by a locum. The diabetes follow-up order set was "
          "not carried over cleanly, so timely A1c rechecks degrade for a few months, then partially recover.")],
        "clinic_id string, change_type string, transition_date string, recovery_days int, narrative string"
    ).withColumn("transition_date", F.to_date("transition_date"))

    # ---------- latents: adherence a_p + glycemic control (a patient attribute, not a stream edit) ----------
    adh = roster.withColumn("a_p", sig(F.lit(AD_B0) + F.lit(AD_BE) * (F.col("engagement") - F.lit(0.5))
                                       + F.lit(AD_BC) * F.col("c_std") + F.lit(AD_SIGMA) * F.col("u_panel")))
    control = (adh.withColumn("p_ctrl", sig(F.lit(CT_B0) + F.lit(CT_ADH) * (F.col("a_p") - F.lit(0.5))
                                            + F.lit(CT_BE) * (F.col("engagement") - F.lit(0.5))))
               .withColumn("glycemic_poor", u("ctrl", "patient_id") >= F.col("p_ctrl"))
               .withColumn("modeled_a1c", F.when(u("ctrl", "patient_id") >= F.col("p_ctrl"),
                                                 F.round(F.lit(9.3) + u("ctrlv", "patient_id") * F.lit(2.4), 1))))

    # ---------- triggers = RECORDED bronze high A1c (values untouched) ----------
    a1c_codes = (spark.table(f"{term}.loinc_parts")
                 .where((F.col("part") == "LP-HBA1C") & (F.col("predicate") == "has_component"))
                 .select("loinc_code").distinct())
    a1c_list = [r["loinc_code"] for r in a1c_codes.collect()]
    recheck_code = a1c_list[0]
    obs = spark.table(f"{g}.bronze_order_results")
    a1c = (obs.where(F.col("loinc_code").isin(a1c_list)).where(F.year("result_ts") == MY)
           .withColumn("value_num", F.expr("try_cast(value as double)")))
    triggers = (a1c.where(F.col("value_num") >= A1C_TRIGGER).join(cohort, "patient_id")
                .select("patient_id", F.col("result_ts").alias("trigger_ts"), F.col("value_num").alias("trigger_a1c"), F.col("units"))
                .join(roster.select("patient_id", "engagement", "c_std", "u_panel", "panel_id", "clinic_id", "is_handoff"), "patient_id"))

    days_since = F.datediff(F.col("trigger_ts"), F.to_date(F.lit(TRANSITION_DATE)))
    gap = (F.when(F.col("is_handoff") & (days_since >= 0) & (days_since <= GAP_RECOVERY_DAYS),
                  F.lit(FU_GAP_PEAK * args.intensity) * (F.lit(1.0) - days_since / F.lit(float(GAP_RECOVERY_DAYS))))
           .otherwise(F.lit(0.0)))
    season = F.lit(FU_SEASON) * F.sin(F.lit(2 * 3.14159 / 365.0) * F.dayofyear("trigger_ts"))
    logit_fu = (F.lit(FU_B0) + F.lit(FU_BE) * (F.col("engagement") - F.lit(0.5)) + F.lit(FU_BC) * F.col("c_std")
                + F.lit(FU_SIGMA) * F.col("u_panel") + season - gap)
    triggers = (triggers.withColumn("p_fu", sig(logit_fu))
                .withColumn("followed", u("fu", "patient_id", "trigger_ts") < F.col("p_fu")))

    # Followed -> a MARKED recheck A1c at offset 14..85d (excluded from triggers by its description).
    followed = (triggers.where("followed")
                .withColumn("off_days", F.lit(14) + (u("off", "patient_id", "trigger_ts") * F.lit(71)).cast("int"))
                .withColumn("followup_ts", F.expr("trigger_ts + make_interval(0,0,0, off_days, 0,0,0)")))
    recheck_rows = (followed
                    .withColumn("rc_val", F.round(F.lit(6.7) + unorm("rcval", "patient_id", "trigger_ts") * F.lit(0.6), 1))
                    .select("patient_id", F.lit(None).cast("string").alias("encounter_id"),
                            F.col("followup_ts").cast("timestamp").alias("result_ts"), F.lit(recheck_code).alias("loinc_code"),
                            F.lit(RECHECK_TAG).alias("description"),
                            F.col("rc_val").cast("string").alias("value"),
                            F.coalesce(F.col("units"), F.lit("%")).alias("units")))
    care_order_results = obs.unionByName(recheck_rows)

    # ---------- medication fills with realistic gaps (continuous PDC) ----------
    biguanide = (spark.table(f"{term}.rxnorm_closure").where(F.col("ancestor_code") == "DRUGCLASS-BIGUANIDE")
                 .select("descendant_code").distinct())
    med = spark.table(f"{g}.bronze_order_med")
    cohort_big = (med.join(biguanide, med["rxnorm_code"] == biguanide["descendant_code"]).join(cohort, "patient_id")
                  .groupBy("patient_id").agg(F.min(F.to_date("start_ts")).alias("rx_start"),
                                             F.max(F.coalesce(F.to_date("stop_ts"), F.to_date(F.lit(MY_END)))).alias("rx_stop"),
                                             F.first("rxnorm_code").alias("rxnorm_code"),
                                             F.first("description").alias("description"),
                                             F.first("encounter_id").alias("encounter_id")))
    cohort_big = (cohort_big
                  .withColumn("rx_start", F.greatest("rx_start", F.to_date(F.lit(MY_START))))
                  .withColumn("rx_stop", F.least("rx_stop", F.to_date(F.lit(MY_END))))
                  .where(F.col("rx_stop") > F.col("rx_start"))
                  .join(adh.select("patient_id", "a_p"), "patient_id"))
    cycles = (cohort_big
              .withColumn("n_cyc", F.greatest(F.lit(1), (F.datediff("rx_stop", "rx_start") / 30).cast("int")))
              .withColumn("cyc", F.explode(F.expr("sequence(0, n_cyc - 1)")))
              .withColumn("cyc_start", F.expr("rx_start + make_interval(0,0,0, cyc*30, 0,0,0)"))
              .withColumn("keep", u("fill", "patient_id", F.col("cyc")) < F.col("a_p")))
    modeled_fills = (cycles.where("keep")
                     .select("patient_id", "encounter_id",
                             F.col("cyc_start").cast("timestamp").alias("start_ts"),
                             F.expr("cyc_start + make_interval(0,0,0,30,0,0,0)").cast("timestamp").alias("stop_ts"),
                             "rxnorm_code", "description"))
    big_codes = [r["descendant_code"] for r in biguanide.collect()]
    keep_med = (med.join(cohort.withColumn("in_cohort", F.lit(True)), "patient_id", "left")
                .withColumn("is_cohort_big", F.col("in_cohort").isNotNull() & F.col("rxnorm_code").isin(big_codes))
                .where(~F.col("is_cohort_big")).select(med.columns))
    care_order_med = keep_med.unionByName(modeled_fills)

    # ---------- WRITE outputs ----------
    roster_out = roster.join(control.select("patient_id", "glycemic_poor", "modeled_a1c", "a_p"), "patient_id", "left")
    (roster_out.select("patient_id", "clinic_id", "panel_id", "pcp_id", "age", "complexity", "c_std",
                       F.round("engagement", 3).alias("engagement"), F.round("u_panel", 3).alias("provider_effect"),
                       F.round("a_p", 3).alias("adherence_propensity"), "glycemic_poor", "modeled_a1c", "is_handoff")
     .write.mode("overwrite").option("overwriteSchema", True).saveAsTable(f"{g}.panel_roster"))
    transition.write.mode("overwrite").option("overwriteSchema", True).saveAsTable(f"{g}.panel_pcp_transition")
    care_order_results.write.mode("overwrite").option("overwriteSchema", True).saveAsTable(f"{g}.care_order_results")
    care_order_med.write.mode("overwrite").option("overwriteSchema", True).saveAsTable(f"{g}.care_order_med")

    # ================= DISTRIBUTION REPORT =================
    print("\n================ CARE-BEHAVIOR MODEL — DISTRIBUTIONS ================")
    print(f"cohort={cohort.count()}  clinics={N_CLINICS}  panels={N_PANELS}  seed={seed}  intensity={args.intensity}")
    psize = roster.groupBy("panel_id").count().agg(
        F.min("count").alias("mn"), F.expr("percentile(count,0.5)").alias("md"), F.max("count").alias("mx")).collect()[0]
    print(f"\nPanel sizes: min={psize['mn']} median={psize['md']} max={psize['mx']}")
    overall_fu = triggers.agg(F.avg(F.col("followed").cast("int"))).collect()[0][0]
    print(f"Triggers={triggers.count()}  overall timely-follow-up rate: {overall_fu:.1%}")

    clinic_fu = (triggers.groupBy("clinic_id", "is_handoff")
                 .agg(F.count("*").alias("triggers"), F.round(F.avg(F.col("followed").cast("int")), 3).alias("fu_rate")))
    print("\nClinic follow-up rate (disrupted clinic flagged; low but overlapping = realistic):")
    clinic_fu.orderBy("fu_rate").show(N_CLINICS, truncate=False)

    pre_post = (triggers.withColumn("period", F.when(F.col("trigger_ts") < F.to_date(F.lit(TRANSITION_DATE)), "1_pre").otherwise("2_post"))
                .groupBy("is_handoff", "period").agg(F.count("*").alias("triggers"),
                                                     F.round(F.avg(F.col("followed").cast("int")), 3).alias("fu_rate"))
                .orderBy("is_handoff", "period"))
    print(f"Follow-up BEFORE vs AFTER the {TRANSITION_DATE} transition (disrupted clinic vs rest):")
    pre_post.show(truncate=False)

    quarterly = (triggers.withColumn("q", F.concat(F.lit("Q"), F.quarter("trigger_ts")))
                 .groupBy("q").agg(
                     F.round(F.avg(F.when(F.col("is_handoff"), F.col("followed").cast("int"))), 3).alias("disrupted_clinic"),
                     F.sum(F.col("is_handoff").cast("int")).alias("disrupted_triggers"),
                     F.round(F.avg(F.when(~F.col("is_handoff"), F.col("followed").cast("int"))), 3).alias("rest")).orderBy("q"))
    print("Quarterly follow-up — disrupted clinic vs rest (transition mid-Q3):")
    quarterly.show(truncate=False)

    print("Confound — avg complexity, disrupted clinic vs rest:")
    roster.groupBy("is_handoff").agg(F.round(F.avg("complexity"), 2).alias("avg_complexity"),
                                     F.count("*").alias("patients")).show(truncate=False)

    pdc = (modeled_fills.groupBy("patient_id").agg(F.sum(F.datediff("stop_ts", "start_ts")).alias("cov"))
           .join(cohort_big.withColumn("period", F.datediff("rx_stop", "rx_start") + F.lit(1)).select("patient_id", "period"), "patient_id")
           .withColumn("pdc", F.least(F.lit(1.0), F.col("cov") / F.col("period"))))
    ps = pdc.agg(F.expr("percentile(pdc,0.1)").alias("p10"), F.expr("percentile(pdc,0.5)").alias("p50"),
                 F.expr("percentile(pdc,0.9)").alias("p90"), F.avg("pdc").alias("mean"),
                 F.avg((F.col("pdc") >= 0.8).cast("int")).alias("adh")).collect()[0]
    print(f"\nMAD PDC: p10={ps['p10']:.2f} p50={ps['p50']:.2f} p90={ps['p90']:.2f} mean={ps['mean']:.2f} adherent(>=0.8)={ps['adh']:.1%}")
    pc = control.join(cohort, "patient_id").agg(F.avg(F.col("glycemic_poor").cast("int"))).collect()[0][0]
    print(f"Poor control (glycemic_poor attribute, read by GSD as a1c_gt9): {pc:.1%}  (target ~15-20%)")
    print("\n============ care_order_* + panel_roster written. ============")


if __name__ == "__main__":
    main()
