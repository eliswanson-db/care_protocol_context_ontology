# Databricks notebook source
# MAGIC %md
# MAGIC # Measure Trend & Drift Forecast — is any clinic quietly slipping?
# MAGIC
# MAGIC Two views of HEDIS performance:
# MAGIC 1. a **current scorecard** across all diabetes measures (GSD, KED, BPD, SPD, EED, MAD) from the Gold layer;
# MAGIC 2. a **temporal drift watch** on protocol **Step-3** (A1c follow-up within 90 days of an at/above-target
# MAGIC    trigger) — per clinic, each clinic vs **its own** trailing baseline, with a naive next-month forecast.
# MAGIC
# MAGIC The temporal view is the operational one: an annual ranking hides a clinic whose rate *dropped* mid-year
# MAGIC (the "A Monday with Genie" signal). Numpy-only trend fit — cheap on serverless; reads only, writes nothing.
# MAGIC
# MAGIC | Layer | Asset |
# MAGIC |---|---|
# MAGIC | Gold measures | `care_protocol.gold_adherence_{gsd,ked,bpd,spd,eed,mad}` |
# MAGIC | Gold process | `care_protocol.gold_protocol_adherence` (trigger_ts, followup_within_90d, clinic_id) |
# MAGIC | Semantic | `care_protocol_semantic.protocol_adherence_metrics` (the governed Step-3 rate) |
# MAGIC | Watch | `care_protocol.protocol_watch_findings` (the precomputed drift log) |
# MAGIC
# MAGIC *Synthetic · HEDIS-aligned · Not NCQA-certified · Not for clinical use.*

# COMMAND ----------

dbutils.widgets.text("catalog", "eli_test_classic_catalog")
dbutils.widgets.text("measurement_year", "2025")
CATALOG = dbutils.widgets.get("catalog")
MY = int(dbutils.widgets.get("measurement_year"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1 · Current measure scorecard (all six diabetes measures)

# COMMAND ----------

import pandas as pd
# The compliance rules live in the certified metric views (gold is an evidence base) -- read the governed numbers.
VIEWS = {  # measure -> (metric view, numerator measure, rate measure)
    "gsd": ("gsd_compliance_metrics", "Compliant Patients", "GSD Compliance Rate"),
    "ked": ("ked_compliance_metrics", "Compliant Patients", "KED Compliance Rate"),
    "bpd": ("bpd_compliance_metrics", "Controlled Patients", "BPD Compliance Rate"),
    "spd": ("spd_compliance_metrics", "On Statin Patients", "SPD Compliance Rate"),
    "eed": ("eed_compliance_metrics", "Eye Exam Patients", "EED Compliance Rate"),
    "mad": ("mad_compliance_metrics", "Adherent Patients", "MAD Adherence Rate"),
}
rows = []
for m, (view, num, rate) in VIEWS.items():
    r = spark.sql(f"""
        SELECT '{m.upper()}' AS measure,
               MEASURE(`Eligible Patients`)  AS eligible,
               MEASURE(`{num}`)              AS compliant,
               ROUND(MEASURE(`{rate}`), 4)   AS rate
        FROM {CATALOG}.care_protocol_semantic.{view}
        WHERE `Measurement Year` = {MY}
    """).toPandas()
    rows.append(r)
scorecard = pd.concat(rows, ignore_index=True)
print(f"MY{MY} diabetes measure scorecard:")
display(scorecard)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2 · Protocol Step-3 adherence by clinic × month

# COMMAND ----------

monthly = spark.sql(f"""
    SELECT clinic_id,
           date_trunc('month', trigger_ts) AS month,
           COUNT(*)                         AS triggers,
           CAST(AVG(CASE WHEN followup_within_90d THEN 1.0 ELSE 0.0 END) AS DOUBLE) AS step3_rate
    FROM {CATALOG}.care_protocol.gold_protocol_adherence
    WHERE measurement_year = {MY} AND trigger_ts IS NOT NULL
    GROUP BY clinic_id, date_trunc('month', trigger_ts)
    HAVING COUNT(*) >= 5          -- small-N gate: ignore months with too few triggers
    ORDER BY clinic_id, month
""").toPandas()
monthly["month"] = pd.to_datetime(monthly["month"])
pivot = monthly.pivot(index="month", columns="clinic_id", values="step3_rate").astype(float)
print("Step-3 follow-up rate by clinic × month (small-N months dropped):")
display(pivot.round(3))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3 · Linear trend + naive next-month forecast per clinic

# COMMAND ----------

import numpy as np
fc = []
for clinic in pivot.columns:
    s = pivot[clinic].dropna()
    if len(s) < 4:
        continue
    x = np.arange(len(s))
    slope, intercept = np.polyfit(x, s.values, 1)
    forecast = float(np.clip(slope * len(s) + intercept, 0, 1))
    fc.append({"clinic_id": clinic, "months": len(s), "latest_rate": round(float(s.iloc[-1]), 3),
               "trend_per_month": round(float(slope), 4), "next_month_forecast": round(forecast, 3)})
trend = pd.DataFrame(fc).sort_values("trend_per_month")
print("trend (most negative = declining fastest):")
display(trend)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4 · Drift: trailing-3-month vs each clinic's OWN prior baseline

# COMMAND ----------

drift = []
for clinic in pivot.columns:
    s = pivot[clinic].dropna()
    if len(s) < 5:
        continue
    trailing = s.iloc[-3:].mean()
    baseline = s.iloc[:-3].mean()
    drift.append({"clinic_id": clinic, "own_baseline": round(float(baseline), 3),
                  "trailing_3mo": round(float(trailing), 3), "delta": round(float(trailing - baseline), 3)})
drift = pd.DataFrame(drift).sort_values("delta")
drift["flag"] = np.where(drift["delta"] <= -0.15, "HIGH", np.where(drift["delta"] <= -0.07, "WATCH", "ok"))
print("self-referential drift (negative delta = dropped vs own history):")
display(drift)

# Cross-check against the precomputed watch log.
try:
    watch = spark.sql(f"""
        SELECT clinic_id, as_of, finding_type, delta
        FROM {CATALOG}.care_protocol.protocol_watch_findings
        WHERE finding_type = 'STEP_DRIFT' ORDER BY delta LIMIT 5""").toPandas()
    print("precomputed protocol_watch_findings (for cross-check):")
    display(watch)
except Exception as e:  # noqa: BLE001
    print("watch findings not available:", e)

# COMMAND ----------

# MAGIC %md
# MAGIC **Reading it:** the annual scorecard in §1 ranks clinics, but §4 is the operational signal — a clinic whose
# MAGIC trailing quarter fell vs **its own** earlier baseline (expected: CLINIC-08, a mid-year PCP handoff). The
# MAGIC governed Step-3 rate lives in `care_protocol_semantic.protocol_adherence_metrics`; this notebook keeps a
# MAGIC fresh temporal read beside the precomputed `protocol_watch_findings`.
