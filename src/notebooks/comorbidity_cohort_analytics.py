# Databricks notebook source
# MAGIC %md
# MAGIC # Comorbidity & Cohort Analytics — terminology as data
# MAGIC
# MAGIC Everything here is **resolved by the governed closures/edge tables**, not by string prefixes — the point
# MAGIC the capability-map benchmark makes: a materialized closure *is* the graph for ICD-10 (is-a), and the LOINC
# MAGIC Part table lets us ask "any A1c **regardless of method**" without enumerating codes.
# MAGIC
# MAGIC | Vocabulary | Asset | What it enables |
# MAGIC |---|---|---|
# MAGIC | ICD-10-CM | `care_protocol_terminology.icd10_closure` | diabetic-complication & comorbidity subtrees (is-a rollup) |
# MAGIC | LOINC | `care_protocol_terminology.loinc_parts` | A1c-any-method via the Component Part axis |
# MAGIC | RxNorm | `care_protocol_terminology.rxnorm_closure` | drug-class → clinical-drug subsumption (statins) |
# MAGIC | Value sets | `care_protocol_terminology.value_set_segment` | versioned measure value-set coverage |
# MAGIC
# MAGIC Cohorts source: `care_protocol.silver_condition`, `silver_observation`, `bronze_order_med`,
# MAGIC `silver_diabetes_cohort`. Reads only. *Synthetic · HEDIS-aligned · Not NCQA-certified · Not for clinical use.*

# COMMAND ----------

dbutils.widgets.text("catalog", "eli_test_classic_catalog")
CATALOG = dbutils.widgets.get("catalog")
T = f"{CATALOG}.care_protocol_terminology"
P = f"{CATALOG}.care_protocol"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1 · Diabetic-complication cohorts via the ICD-10 closure (subsumption, not prefix matching)

# COMMAND ----------

complications = spark.sql(f"""
    SELECT CASE
             WHEN cl.ancestor_code IN ('E11.2','E10.2','E13.2') THEN 'diabetic kidney'
             WHEN cl.ancestor_code IN ('E11.3','E10.3','E13.3') THEN 'diabetic retinopathy'
             WHEN cl.ancestor_code IN ('E11.4','E10.4','E13.4') THEN 'diabetic neuropathy'
           END AS complication,
           COUNT(DISTINCT c.patient_id) AS patients
    FROM {P}.silver_condition c
    JOIN {T}.icd10_closure cl ON cl.descendant_code = c.icd10_code
    WHERE cl.ancestor_code IN ('E11.2','E10.2','E13.2','E11.3','E10.3','E13.3','E11.4','E10.4','E13.4')
    GROUP BY 1 ORDER BY patients DESC
""").toPandas()
display(complications)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2 · Comorbidity co-occurrence in the diabetic cohort (diabetes × CKD × heart failure)
# MAGIC CKD = `N18` subtree, HF = `I50` subtree (both resolved through the closure). The triple intersection is the
# MAGIC **cardiorenal** cohort the protocol flags for SGLT2 / ACE-ARB review.

# COMMAND ----------

import pandas as pd
flags = spark.sql(f"""
    WITH dm  AS (SELECT patient_id FROM {P}.silver_diabetes_cohort),
         ckd AS (SELECT DISTINCT c.patient_id FROM {P}.silver_condition c
                   JOIN {T}.icd10_closure cl ON cl.descendant_code=c.icd10_code WHERE cl.ancestor_code='N18'),
         hf  AS (SELECT DISTINCT c.patient_id FROM {P}.silver_condition c
                   JOIN {T}.icd10_closure cl ON cl.descendant_code=c.icd10_code WHERE cl.ancestor_code='I50')
    SELECT dm.patient_id,
           (ckd.patient_id IS NOT NULL) AS has_ckd,
           (hf.patient_id  IS NOT NULL) AS has_hf
    FROM dm LEFT JOIN ckd USING (patient_id) LEFT JOIN hf USING (patient_id)
""").toPandas()
n = len(flags)
cardiorenal = int((flags.has_ckd & flags.has_hf).sum())
cooc = pd.DataFrame({
    "group": ["diabetes (all)", "+ CKD (N18)", "+ heart failure (I50)", "cardiorenal (DM+CKD+HF)"],
    "patients": [n, int(flags.has_ckd.sum()), int(flags.has_hf.sum()), cardiorenal],
})
cooc["pct_of_diabetic"] = (cooc["patients"] / n).round(4)
display(cooc)
print(f"cardiorenal cohort (the SGLT2/ACE-ARB review target): {cardiorenal} patients")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3 · LOINC multiaxial — "any HbA1c, regardless of assay method" (Component Part)

# COMMAND ----------

a1c = spark.sql(f"""
    WITH a1c_component AS (                       -- the Component Part shared by every A1c method
        SELECT DISTINCT part FROM {T}.loinc_parts WHERE predicate='Component' AND loinc_code='4548-4'),
         a1c_loincs AS (
        SELECT DISTINCT lp.loinc_code FROM {T}.loinc_parts lp JOIN a1c_component a ON lp.part=a.part
        WHERE lp.predicate='Component')
    SELECT COUNT(DISTINCT al.loinc_code)   AS a1c_codes_any_method,
           COUNT(DISTINCT o.patient_id)    AS patients_with_a1c
    FROM a1c_loincs al LEFT JOIN {P}.silver_observation o ON o.loinc_code = al.loinc_code
""").toPandas()
display(a1c)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4 · RxNorm drug-class subsumption — diabetics on any statin

# COMMAND ----------

statins = spark.sql(f"""
    SELECT COUNT(DISTINCT m.patient_id) AS diabetics_on_statin
    FROM {P}.bronze_order_med m
    JOIN {T}.rxnorm_closure rc ON rc.descendant_code = m.rxnorm_code AND rc.ancestor_code = 'DRUGCLASS-STATIN'
    WHERE m.patient_id IN (SELECT patient_id FROM {P}.silver_diabetes_cohort)
""").toPandas()
display(statins)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5 · Value-set coverage (which code systems / vintages back each measure segment)

# COMMAND ----------

vs = spark.sql(f"""
    SELECT segment_name, code_system, measurement_year, COUNT(*) AS codes
    FROM {T}.value_set_segment
    GROUP BY segment_name, code_system, measurement_year
    ORDER BY segment_name, measurement_year
""").toPandas()
display(vs)

# COMMAND ----------

# MAGIC %md
# MAGIC **Reading it:** none of these cohorts use a `LIKE 'E11%'` prefix — they traverse the closure, so an
# MAGIC `E11.21` (type-2 diabetes with nephropathy) lands in the kidney cohort automatically. The A1c-any-method
# MAGIC count comes from the Component Part, so a new assay code is covered the day it's added. Re-runs hourly to
# MAGIC keep these governed-terminology reads warm.
