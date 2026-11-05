"""Synthesize the SSD behavioral-health cohort (ADR-0015 / ADR-0017).

Why this exists: SSD (Diabetes Screening for People With Schizophrenia or Bipolar Disorder Who Are Using
Antipsychotic Medications) is a CROSS-DOMAIN measure — serious mental illness + antipsychotic dispensing +
a metabolic screen. Synthea (as generated here) produces ZERO of that signal: no F20/F25/F31 diagnoses and
no antipsychotic orders (verified on the 25k population). So the SSD cohort cannot be derived from bronze the
way GSD/KED/BPD/SPD/EED are — it must be synthesized. This script is the behavioral-health analogue of
care_behavior.py (ADR-0012): a seeded, deterministic, EMERGENT synthesis — not point injection.

What it does NOT do: it does not slam a fixed screening rate or hand-pick patients. Every SSD patient gets a
seeded latent engagement; whether they were screened EMERGES from a per-patient Bernoulli draw whose
probability is a logistic of engagement + a smooth per-clinic effect. The aggregate SSD rate and its spread
across clinics fall out of thousands of individual deterministic draws (seeded xxhash), so the recomputed
gold == model truth and the whole thing is reproducible.

Honest cross-domain links, kept real so the graph does the work in measures.py:
  * SMI diagnosis        F20.9 / F25.0 / F31.9 (ICD-10-CM), one per patient (seeded).
  * Antipsychotic disp.  a clinical-drug (SCD) RxNorm code that SUBSUMES to an antipsychotic INGREDIENT via
                         rxnorm_closure — identical mechanism to SPD's statin resolution. The measure proves
                         eligibility through the closure, not a pre-baked flag.
  * Pre-existing DM      the HEDIS SSD exclusion is REAL overlap: an SSD patient who is also in the diabetes
                         cohort (ICD-10 E10/E11/E13 via icd10_closure) is already under diabetes management
                         and is excluded. Not an arbitrary flag — computed from the same closure the cohort
                         measures use.
  * Metabolic screen     glucose (LOINC 2345-7) or HbA1c (4548-4) in the measurement year = the numerator.

Writes ONE effective-layer table: {catalog}.{schema}.care_ssd_cohort (one row per synthesized SSD patient).
measures.py reads it and computes gold_adherence_ssd via the value sets + closure. Runs AFTER epicize
(needs bronze_patient + bronze_pat_enc_dx), independent of the measures pipeline and of care_behavior.
Serverless spark_python_task. Idempotent (overwrite; deterministic from bronze + seed).

Synthetic · HEDIS-aligned (SSD-proxied) · Not NCQA-certified · Not for clinical use.
"""
import argparse

from pyspark.sql import SparkSession, functions as F
from pyspark.sql.window import Window

MY = 2026  # current measurement year, year-to-date; events never exceed the data horizon (~day 302)
MY_START, MY_END = f"{MY}-01-01", f"{MY}-12-31"
N_CLINICS = 8
N_PANELS = 40

SMI_PREVALENCE = 0.055          # share of 18-64 adults flagged SMI-on-antipsychotics (demo denominator ~800)
SMI_CODES = ["F20.9", "F25.0", "F31.9"]   # schizophrenia / schizoaffective / bipolar I (ICD-10-CM)
SMI_NAMES = {"F20.9": "Schizophrenia, unspecified",
             "F25.0": "Schizoaffective disorder, bipolar type",
             "F31.9": "Bipolar disorder, unspecified"}

# Screening (numerator) logistic: baseline ~ sigmoid(0.55) ≈ 63%, spread by engagement + a smooth clinic effect.
SC_B0, SC_BE, SC_SIGMA = 0.55, 1.40, 0.70


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--schema", default="care_protocol")
    ap.add_argument("--seed", default="20261029")
    args = ap.parse_args()

    spark = SparkSession.builder.getOrCreate()
    g = f"{args.catalog}.{args.schema}"
    term = f"{args.catalog}.care_protocol_terminology"
    seed = args.seed

    def u(stream, *cols):
        parts = [F.lit(f"{seed}:{stream}")] + [(F.col(c) if isinstance(c, str) else c).cast("string") for c in cols]
        return F.pmod(F.xxhash64(F.concat_ws("|", *parts)), F.lit(1_000_000)).cast("double") / F.lit(1_000_000.0)

    def unorm(stream, *cols):          # ~N(0,1) from 4 uniforms (same trick as care_behavior)
        s = sum((u(f"{stream}{i}", *cols) for i in range(4)), F.lit(0.0))
        return (s - F.lit(2.0)) / F.lit(0.5774)

    sig = lambda x: F.lit(1.0) / (F.lit(1.0) + F.exp(-x))

    # ---------- base population: adults 18-64 at measurement-year end ----------
    patients = (spark.table(f"{g}.bronze_patient")
                .withColumn("age", (F.datediff(F.lit(MY_END), F.col("birth_date")) / 365.25).cast("int"))
                .where((F.col("age") >= 18) & (F.col("age") <= 64))
                .select("patient_id", "age"))

    # ---------- SMI-on-antipsychotic selection (seeded Bernoulli) ----------
    smi = patients.where(u("ssd_smi", "patient_id") < F.lit(SMI_PREVALENCE))

    # SMI diagnosis: one of three, chosen by a seeded bucket.
    dx_pick = (u("ssd_dx", "patient_id") * F.lit(len(SMI_CODES))).cast("int")
    smi_map = F.create_map(*sum(([F.lit(i), F.lit(c)] for i, c in enumerate(SMI_CODES)), []))
    smi_name_map = F.create_map(*sum(([F.lit(c), F.lit(SMI_NAMES[c])] for c in SMI_CODES), []))
    smi = (smi.withColumn("smi_dx_code", smi_map[dx_pick])
           .withColumn("smi_dx_name", smi_name_map[F.col("smi_dx_code")]))

    # ---------- antipsychotic dispensing: a clinical drug (SCD) that subsumes to an antipsychotic ingredient ----
    # Resolve the demo SSD_ANTIPSYCHOTIC ingredient value set to clinical drugs via the RxNorm closure (same
    # ingredient->SCD subsumption as SPD). The synthesized dispensing event carries a real SCD code so the
    # measure can re-derive eligibility through the graph rather than trusting a flag.
    ingredients = (spark.table(f"{term}.value_set_segment")
                   .where(F.col("segment_id") == "SSD_ANTIPSYCHOTIC")
                   .select(F.col("code").alias("ing")).distinct())
    closure = spark.table(f"{term}.rxnorm_closure")
    scds = (closure.join(ingredients, closure["ancestor_code"] == ingredients["ing"])
            .where(F.col("ancestor_code") != F.col("descendant_code"))        # depth>=1 -> clinical drugs only
            .select(F.col("descendant_code").alias("rxnorm_code"),
                    F.col("descendant_name").alias("rxnorm_desc")).distinct())
    scd_list = [(r["rxnorm_code"], r["rxnorm_desc"]) for r in scds.collect()]
    if not scd_list:
        raise RuntimeError("No antipsychotic clinical drugs in rxnorm_closure. Add SCD children for the "
                           "antipsychotic ingredients to src/terminology/rxnorm_hier.csv and rebuild the "
                           "rxnorm closure (bundle run setup).")
    n_scd = len(scd_list)
    code_map = F.create_map(*sum(([F.lit(i), F.lit(c)] for i, (c, _) in enumerate(scd_list)), []))
    desc_map = F.create_map(*sum(([F.lit(c), F.lit(d)] for (c, d) in scd_list), []))
    ap_pick = (u("ssd_ap", "patient_id") * F.lit(n_scd)).cast("int")
    # Dispensing date: a deterministic day within the measurement year (reproducible from the seed).
    ap_off = (u("ssd_apday", "patient_id") * F.lit(270)).cast("int")
    smi = (smi.withColumn("antipsychotic_rxnorm", code_map[ap_pick])
           .withColumn("antipsychotic_desc", desc_map[F.col("antipsychotic_rxnorm")])
           .withColumn("antipsychotic_ts", F.to_timestamp(F.date_add(F.to_date(F.lit(MY_START)), ap_off))))

    # ---------- pre-existing diabetes exclusion: REAL overlap with the diabetes cohort (icd10 closure) ----------
    dm_closure = (spark.table(f"{term}.icd10_closure").where(F.col("ancestor_code").isin("E10", "E11", "E13"))
                  .select("descendant_code").distinct())
    dx = spark.table(f"{g}.bronze_pat_enc_dx").where(F.col("icd10_code").isNotNull())
    dm_cohort = (dx.join(dm_closure, dx["icd10_code"] == dm_closure["descendant_code"])
                 .select("patient_id").distinct().withColumn("has_preexisting_dm", F.lit(True)))
    smi = (smi.join(dm_cohort, "patient_id", "left")
           .withColumn("has_preexisting_dm", F.coalesce(F.col("has_preexisting_dm"), F.lit(False))))

    # ---------- site structure (sliceability) ----------
    panel_num = F.pmod(F.xxhash64(F.concat_ws("|", F.lit(f"{seed}:ssd_panel"), F.col("patient_id"))), F.lit(N_PANELS))
    clinic_num = F.pmod(F.xxhash64(F.concat_ws("|", F.lit(f"{seed}:ssd_clinic"), F.col("patient_id"))), F.lit(N_CLINICS)) + F.lit(1)
    smi = (smi.withColumn("panel_id", F.concat(F.lit("PANEL-"), F.lpad(panel_num.cast("string"), 2, "0")))
           .withColumn("clinic_id", F.concat(F.lit("CLINIC-"), F.lpad(clinic_num.cast("string"), 2, "0"))))

    # ---------- screening (numerator) — emergent from a seeded logistic ----------
    engagement = u("ssd_eng", "patient_id")
    clinic_eff = unorm("ssd_cliniceff", "clinic_id")              # smooth per-clinic effect (not a hard drift)
    p_screen = sig(F.lit(SC_B0) + F.lit(SC_BE) * (engagement - F.lit(0.5)) + F.lit(SC_SIGMA) * clinic_eff)
    glucose, hba1c = "2345-7", "4548-4"
    smi = (smi.withColumn("engagement", F.round(engagement, 3))
           .withColumn("p_screen", p_screen)
           .withColumn("screened", u("ssd_screen", "patient_id") < F.col("p_screen"))
           .withColumn("screen_loinc", F.when(F.col("screened"),
                                              F.when(u("ssd_test", "patient_id") < F.lit(0.5), F.lit(hba1c)).otherwise(F.lit(glucose))))
           .withColumn("sc_off", (u("ssd_scday", "patient_id") * F.lit(295)).cast("int"))
           .withColumn("screen_ts", F.when(F.col("screened"),
                                           F.to_timestamp(F.date_add(F.to_date(F.lit(MY_START)), F.col("sc_off")))))
           .drop("sc_off", "p_screen"))

    out = smi.select(
        "patient_id", "age", "smi_dx_code", "smi_dx_name",
        "antipsychotic_rxnorm", "antipsychotic_desc", "antipsychotic_ts",
        "has_preexisting_dm", "clinic_id", "panel_id", "engagement",
        "screened", "screen_loinc", "screen_ts")

    fqn = f"{g}.care_ssd_cohort"
    out.write.mode("overwrite").option("overwriteSchema", True).saveAsTable(fqn)
    spark.sql(
        f"COMMENT ON TABLE {fqn} IS 'Synthesized SSD behavioral-health cohort (ADR-0017): one row per SMI "
        f"patient on antipsychotics, aged 18-64. Seeded/deterministic (xxhash); screening is EMERGENT from a "
        f"per-patient logistic, not injected. Antipsychotic dispensing carries a clinical-drug RxNorm code that "
        f"subsumes to an ingredient via rxnorm_closure; pre-existing-DM exclusion is REAL diabetes-cohort "
        f"overlap. Feeds gold_adherence_ssd. Synthetic; HEDIS-aligned (SSD-proxied); not NCQA-certified.'")

    # ---------------- distribution report ----------------
    tot = out.count()
    excl = out.where("has_preexisting_dm").count()
    elig = out.where("NOT has_preexisting_dm").count()
    scr = out.where("NOT has_preexisting_dm AND screened").count()
    print("\n================ SSD COHORT SYNTHESIS — DISTRIBUTIONS ================")
    print(f"seed={seed}  SMI_prevalence(18-64)={SMI_PREVALENCE}  clinical-drug codes={n_scd}")
    print(f"cohort={tot}  excluded(pre-existing DM)={excl}  eligible={elig}  "
          f"screened(eligible)={scr}  SSD rate={scr/elig:.1%}" if elig else "eligible=0")
    print("\nSMI diagnosis mix:")
    out.groupBy("smi_dx_code", "smi_dx_name").count().orderBy("smi_dx_code").show(truncate=False)
    print("Antipsychotic dispensing mix (clinical drug -> via closure to an ingredient):")
    out.groupBy("antipsychotic_rxnorm", "antipsychotic_desc").count().orderBy(F.desc("count")).show(truncate=False)
    print("Eligible SSD screening rate by clinic (emergent spread; no hard drift injected):")
    (out.where("NOT has_preexisting_dm").groupBy("clinic_id")
     .agg(F.count("*").alias("eligible"), F.round(F.avg(F.col("screened").cast("int")), 3).alias("ssd_rate"))
     .orderBy("ssd_rate").show(N_CLINICS, truncate=False))
    print("============ care_ssd_cohort written. ============\n")


if __name__ == "__main__":
    main()
