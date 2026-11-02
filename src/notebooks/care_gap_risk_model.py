# Databricks notebook source
# MAGIC %md
# MAGIC # Care-Gap Risk Model — who will miss a HEDIS measure before year-end?
# MAGIC
# MAGIC **Measure:** GSD (Glycemic Status Assessment for Patients With Diabetes).
# MAGIC **Question:** among patients *eligible* for GSD this measurement year, which are most likely to end the
# MAGIC year **NOT_MET** (a care gap) — early enough to intervene?
# MAGIC
# MAGIC This is a **governed, explainable** model: a logistic regression over features drawn from the Gold measure
# MAGIC layer + the terminology closures, trained in-notebook (numpy, no external libraries — cheap on serverless).
# MAGIC It reads only governed assets and writes nothing.
# MAGIC
# MAGIC | Layer | Asset |
# MAGIC |---|---|
# MAGIC | Gold measure | `care_protocol.gold_adherence_gsd` (eligibility, status, gap_reason) |
# MAGIC | Gold measure | `care_protocol.gold_adherence_mad` (medication PDC), `gold_adherence_spd` (statin) |
# MAGIC | Terminology | `care_protocol_terminology.icd10_closure` (diabetic-kidney comorbidity via subsumption) |
# MAGIC | Semantic | `care_protocol_semantic.gsd_compliance_metrics` (the governed rate this rolls up to) |
# MAGIC
# MAGIC *Synthetic · HEDIS-aligned (eCQM-proxied) · Not NCQA-certified · Not for clinical use.*

# COMMAND ----------

dbutils.widgets.text("catalog", "eli_test_classic_catalog")
dbutils.widgets.text("measurement_year", "2025")
CATALOG = dbutils.widgets.get("catalog")
MY = int(dbutils.widgets.get("measurement_year"))
print(f"catalog={CATALOG} measurement_year={MY}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1 · Feature assembly from the Gold + terminology layers
# MAGIC Non-leaky features only — we deliberately **exclude** the A1c result (which mechanically determines GSD
# MAGIC status) and predict from *context*: age, diabetic-kidney comorbidity (resolved by ICD-10 subsumption, not a
# MAGIC flat code list), medication adherence (PDC), and statin therapy. Target = `status = 'NOT_MET'`.

# COMMAND ----------

feat = spark.sql(f"""
WITH kidney AS (            -- diabetic kidney complication via the ICD-10 closure (E1x.2 subtree)
  SELECT DISTINCT c.patient_id
  FROM {CATALOG}.care_protocol.silver_condition c
  JOIN {CATALOG}.care_protocol_terminology.icd10_closure cl ON cl.descendant_code = c.icd10_code
  WHERE cl.ancestor_code IN ('E11.2','E10.2','E13.2')
),
mad AS (SELECT patient_id, pdc FROM {CATALOG}.care_protocol.gold_adherence_mad WHERE measurement_year = {MY})
SELECT g.patient_id, g.age, g.clinic_id, g.panel_id,
       CASE WHEN g.status = 'NOT_MET' THEN 1 ELSE 0 END                 AS gap,
       CASE WHEN k.patient_id IS NOT NULL THEN 1 ELSE 0 END             AS kidney_comorbidity,
       COALESCE(m.pdc, 0.0)                                             AS mad_pdc,
       CASE WHEN m.patient_id IS NULL THEN 1 ELSE 0 END                 AS mad_missing,
       CASE WHEN s.numerator_flag THEN 1 ELSE 0 END                     AS on_statin
FROM {CATALOG}.care_protocol.gold_adherence_gsd g
LEFT JOIN kidney k ON k.patient_id = g.patient_id
LEFT JOIN mad    m ON m.patient_id = g.patient_id
LEFT JOIN {CATALOG}.care_protocol.gold_adherence_spd s
       ON s.patient_id = g.patient_id AND s.measurement_year = {MY}
WHERE g.measurement_year = {MY} AND g.eligible_flag
""").toPandas()

print(f"eligible GSD patients: {len(feat):,} · observed gap rate: {feat['gap'].mean():.1%}")
display(feat.head(10))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2 · Train an explainable logistic regression (numpy, standardized coefficients)

# COMMAND ----------

import numpy as np

FEATURES = ["age", "kidney_comorbidity", "mad_pdc", "mad_missing", "on_statin"]
X = feat[FEATURES].to_numpy(dtype=float)
y = feat["gap"].to_numpy(dtype=float)

mu, sd = X.mean(0), X.std(0) + 1e-9
Xs = (X - mu) / sd
Xb = np.hstack([np.ones((len(Xs), 1)), Xs])

w = np.zeros(Xb.shape[1])
for _ in range(400):                       # batch gradient descent — tiny data, converges fast
    p = 1.0 / (1.0 + np.exp(-Xb @ w))
    w -= 0.3 * (Xb.T @ (p - y)) / len(y)
prob = 1.0 / (1.0 + np.exp(-Xb @ w))


def auc(yt, pr):                            # rank-based ROC-AUC (Mann–Whitney U)
    order = np.argsort(pr)
    ranks = np.empty(len(pr)); ranks[order] = np.arange(1, len(pr) + 1)
    pos, neg = yt == 1, yt == 0
    npos, nneg = pos.sum(), neg.sum()
    return float((ranks[pos].sum() - npos * (npos + 1) / 2) / (npos * nneg)) if npos and nneg else float("nan")


print(f"train ROC-AUC: {auc(y, prob):.3f}")
import pandas as pd
coef = pd.DataFrame({"feature": ["(intercept)"] + FEATURES, "std_coef": w}).sort_values(
    "std_coef", key=lambda s: s.abs(), ascending=False)
print("standardized coefficients (sign = direction of gap risk):")
display(coef)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3 · Highest-risk eligible patients (the intervention worklist)

# COMMAND ----------

feat["gap_risk"] = prob
worklist = feat[feat["gap"] == 0].sort_values("gap_risk", ascending=False)[
    ["patient_id", "clinic_id", "panel_id", "age", "kidney_comorbidity", "mad_pdc", "on_statin", "gap_risk"]
].head(25)
print("top not-yet-gapped patients by predicted GSD-gap risk:")
display(worklist)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4 · Risk concentration by clinic (where to send the outreach)

# COMMAND ----------

by_clinic = (feat.groupby("clinic_id")
             .agg(eligible=("patient_id", "size"), mean_gap_risk=("gap_risk", "mean"),
                  observed_gap_rate=("gap", "mean"))
             .sort_values("mean_gap_risk", ascending=False).reset_index())
display(by_clinic)

# COMMAND ----------

# MAGIC %md
# MAGIC **Reading it:** `mad_missing` and low `mad_pdc` tend to carry the most GSD-gap risk — patients disengaged
# MAGIC from medication are also the ones who skip the A1c draw. The governed GSD rate these roll up to is
# MAGIC `care_protocol_semantic.gsd_compliance_metrics`; this model just ranks *who* inside the denominator is most
# MAGIC likely to become the NOT_MET numerator shortfall. Re-runs hourly so the worklist stays fresh.
