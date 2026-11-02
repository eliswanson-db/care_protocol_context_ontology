# Databricks notebook source
# MAGIC %md
# MAGIC # Medication-Adherence Segmentation — who to call first
# MAGIC
# MAGIC **Measure:** MAD (Medication Adherence for Diabetes), numerator = **PDC ≥ 0.80** (proportion of days
# MAGIC covered). The generative care-behavior model (ADR-0012) makes PDC a *continuous* distribution, so there is
# MAGIC real structure to segment — unlike raw Synthea's degenerate 100%.
# MAGIC
# MAGIC We cluster eligible patients into adherence **segments** (numpy KMeans — no external libraries, cheap on
# MAGIC serverless), profile each, and produce a **recoverable-near-miss** outreach worklist (PDC just below the
# MAGIC 0.80 threshold — the highest-ROI intervention target).
# MAGIC
# MAGIC | Layer | Asset |
# MAGIC |---|---|
# MAGIC | Gold measure | `care_protocol.gold_adherence_mad` (pdc, fills, covered_days, period_days) |
# MAGIC | Semantic | `care_protocol_semantic.mad_compliance_metrics` (the governed MAD rate) |
# MAGIC
# MAGIC *Synthetic · HEDIS-aligned · Not NCQA-certified · Not for clinical use.*

# COMMAND ----------

dbutils.widgets.text("catalog", "eli_test_classic_catalog")
dbutils.widgets.text("measurement_year", "2025")
CATALOG = dbutils.widgets.get("catalog")
MY = int(dbutils.widgets.get("measurement_year"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1 · PDC distribution across the eligible MAD population

# COMMAND ----------

import numpy as np, pandas as pd
mad = spark.sql(f"""
    SELECT patient_id, clinic_id, panel_id, age, fills, covered_days, period_days, pdc,
           CASE WHEN numerator_flag THEN 1 ELSE 0 END AS adherent
    FROM {CATALOG}.care_protocol.gold_adherence_mad
    WHERE measurement_year = {MY} AND eligible_flag
""").toPandas()

q = mad["pdc"].quantile([.1, .25, .5, .75, .9]).round(3)
print(f"eligible: {len(mad):,} · adherent (PDC>=0.80): {mad['adherent'].mean():.1%}")
print(f"PDC percentiles  p10={q[.1]}  p25={q[.25]}  p50={q[.5]}  p75={q[.75]}  p90={q[.9]}")
display(mad[["pdc", "fills", "covered_days", "period_days", "age"]].describe().round(2))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2 · KMeans segmentation (numpy) on adherence behavior

# COMMAND ----------

FEATURES = ["pdc", "fills", "covered_days", "age"]
X = mad[FEATURES].to_numpy(dtype=float)
Xs = (X - X.mean(0)) / (X.std(0) + 1e-9)

def kmeans(data, k=4, iters=100, seed=7):
    rng = np.random.default_rng(seed)
    cent = data[rng.choice(len(data), k, replace=False)]
    for _ in range(iters):
        lab = ((data[:, None, :] - cent[None, :, :]) ** 2).sum(2).argmin(1)
        new = np.array([data[lab == j].mean(0) if (lab == j).any() else cent[j] for j in range(k)])
        if np.allclose(new, cent):
            break
        cent = new
    return lab

mad["segment"] = kmeans(Xs, k=4)
# Order/label segments by mean PDC so the labels are stable & meaningful across runs.
order = mad.groupby("segment")["pdc"].mean().sort_values().index.tolist()
labels = ["non-adherent", "at-risk", "borderline", "adherent"]
seg_label = {s: labels[i] for i, s in enumerate(order)}
mad["segment_label"] = mad["segment"].map(seg_label)

profile = (mad.groupby("segment_label")
           .agg(patients=("patient_id", "size"), mean_pdc=("pdc", "mean"),
                mean_fills=("fills", "mean"), adherent_rate=("adherent", "mean"))
           .reindex(labels).round(3))
display(profile)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3 · Recoverable near-miss worklist (PDC 0.60–0.79 — closest to the 0.80 threshold)

# COMMAND ----------

nearmiss = (mad[(mad["pdc"] >= 0.60) & (mad["pdc"] < 0.80)]
            .assign(gap_to_threshold=lambda d: (0.80 - d["pdc"]).round(3))
            .sort_values("gap_to_threshold")[
                ["patient_id", "clinic_id", "panel_id", "age", "pdc", "fills", "gap_to_threshold", "segment_label"]]
            .head(25))
print(f"recoverable near-miss patients (PDC 0.60–0.79): {((mad['pdc'] >= 0.60) & (mad['pdc'] < 0.80)).sum():,}")
display(nearmiss)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4 · Where the non-adherence concentrates (by clinic)

# COMMAND ----------

by_clinic = (mad.groupby("clinic_id")
             .agg(eligible=("patient_id", "size"), mean_pdc=("pdc", "mean"), adherent_rate=("adherent", "mean"))
             .sort_values("adherent_rate").round(3).reset_index())
display(by_clinic)

# COMMAND ----------

# MAGIC %md
# MAGIC **Reading it:** the governed MAD rate (`care_protocol_semantic.mad_compliance_metrics`) is one number;
# MAGIC this segments the *shape* behind it. The near-miss list is the highest-ROI outreach — a single extra refill
# MAGIC moves them over 0.80. Re-runs hourly so the segments and worklist stay current.
