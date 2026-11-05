-- Hand-verified gold queries for the capability-map benchmark (see docs/benchmark/ground_truth.yaml,
-- docs/BENCHMARK_CHARTER.md). ONE query per ground-truth question id, delimited by a `-- @id:` header
-- so the benchmark runner can execute each and compare its single scalar result to the ground truth.
--
-- These queries ARE two things at once:
--   1. The ground-truth COMPUTATION: each produces the hand-verified expected value, built by whatever
--      method is correct for that question, independent of any arm. This is the answer key.
--   2. The `closure_sql` ARM reference: fixed-shape SQL over the materialized closure/edge tables
--      (icd10_closure, loinc_parts, rxnorm_closure, value_set_segment, protocol_edges). For classes 2-6
--      this is the query-time resolution approach the benchmark compares against metric_view / rag / graph.
--
-- Scope: classes 1-6 are SQL-computable and live here. Class 7 (definition/provenance) is RAG over the
-- care-protocol PDF/Pages; class 8 (graph-native path/inference) is Ontobricks -- neither is a scalar SQL
-- gold, so they are not in this file (ground_truth.yaml carries their expected facts).
--
-- Placeholders {catalog} / {schema} (medallion+semantic) / {tschema} (terminology) are substituted by the
-- runner. Defaults: {schema}=care_protocol, {tschema}=care_protocol_terminology (ADR-0001).
--
-- Values below are the 25k gold, measurement year 2026 (year-to-date), recomputed 2026-10-30 against the ect target AFTER
-- the generative care-behavior regen (ADR-0012). Each `-- expect:` is the authoritative hand-verified value.

-- =========================================================================================
-- CLASS 1 -- simple KPI (metric view sufficient; control)
-- =========================================================================================

-- @id: kpi_gsd_rate
-- class: 1_simple_kpi  min_approach: metric_view  expect: 0.7424
-- Overall GSD compliance rate = numerator / eligible. A metric view (MEASURE) answers this directly;
-- the raw ratio here is the same number computed from the gold table.
SELECT ROUND(SUM(CASE WHEN evidence_datetime IS NOT NULL THEN 1 ELSE 0 END)
             / SUM(CASE WHEN eligible_flag THEN 1 ELSE 0 END), 4) AS gsd_rate
FROM {catalog}.{schema}.gold_adherence_gsd;

-- @id: kpi_ked_eligible
-- class: 1_simple_kpi  min_approach: metric_view  expect: 2802
SELECT COUNT(*) AS ked_eligible
FROM {catalog}.{schema}.gold_adherence_ked;

-- =========================================================================================
-- CLASS 2 -- single-relation ICD subsumption (closure == graph; prefix LIKE is the fragile approximation)
-- =========================================================================================

-- @id: sub_kidney
-- class: 2_icd_subsumption  min_approach: closure_sql  expect: 1881
-- Diabetes WITH kidney complication = any dx that is a descendant of the diabetic-kidney roots
-- (E11.2 / E10.2 / E13.2) via the is-a closure. Robust to depth; a 'E11.2%' string prefix only approximates it.
SELECT COUNT(DISTINCT dx.patient_id) AS sub_kidney
FROM {catalog}.{schema}.bronze_pat_enc_dx dx
JOIN {catalog}.{tschema}.icd10_closure c ON dx.icd10_code = c.descendant_code
WHERE c.ancestor_code IN ('E11.2', 'E10.2', 'E13.2');

-- @id: sub_retinopathy
-- class: 2_icd_subsumption  min_approach: closure_sql  expect: 393
SELECT COUNT(DISTINCT dx.patient_id) AS sub_retinopathy
FROM {catalog}.{schema}.bronze_pat_enc_dx dx
JOIN {catalog}.{tschema}.icd10_closure c ON dx.icd10_code = c.descendant_code
WHERE c.ancestor_code IN ('E11.3', 'E10.3', 'E13.3');

-- =========================================================================================
-- CLASS 3 -- multiaxial LOINC identity (Component Part edge; beats an enumerated value set)
-- =========================================================================================

-- @id: lab_a1c_any_method
-- class: 3_loinc_multiaxial  min_approach: closure_sql  expect: 9709
-- Every HbA1c regardless of assay method = any observation whose LOINC shares Component LP-HBA1C.
-- The Part edge table derives this; a new A1c code is covered automatically (an enumerated set would miss it).
SELECT COUNT(DISTINCT o.patient_id) AS a1c_any_method
FROM {catalog}.{schema}.silver_observation o
JOIN {catalog}.{tschema}.loinc_parts p ON o.loinc_code = p.loinc_code
WHERE p.predicate = 'has_component' AND p.part = 'LP-HBA1C';

-- @id: lab_egfr_codes
-- class: 3_loinc_multiaxial  min_approach: rag  expect: 33914-3,98979-8
-- Which LOINC codes count as eGFR here (Component LP-EGFR). RAG can read these off the eGFR Page too.
SELECT concat_ws(',', sort_array(collect_set(loinc_code))) AS egfr_codes
FROM {catalog}.{tschema}.loinc_parts
WHERE predicate = 'has_component' AND part = 'LP-EGFR';

-- =========================================================================================
-- CLASS 4 -- RxNorm subsumption (codes are NOT lexical -> closure necessary; naive match = 0)
-- =========================================================================================

-- @id: med_on_statin
-- class: 4_rxnorm_subsumption  min_approach: closure_sql  expect: 1651
-- "How many DIABETIC patients are on any statin?" = diabetic-cohort patients with a prescription whose
-- rxnorm_code is subsumed by DRUGCLASS-STATIN via the RxNorm closure. All ages. (Across ALL patients the
-- count is 4741 -- a different, broader question; the diabetic cohort is the one the benchmark asks.)
SELECT COUNT(DISTINCT m.patient_id) AS diabetic_on_statin
FROM {catalog}.{schema}.bronze_order_med m
JOIN {catalog}.{tschema}.rxnorm_closure c ON m.rxnorm_code = c.descendant_code
JOIN {catalog}.{schema}.silver_diabetes_cohort d ON m.patient_id = d.patient_id
WHERE c.ancestor_code = 'DRUGCLASS-STATIN';

-- @id: med_is_statin
-- class: 4_rxnorm_subsumption  min_approach: closure_sql  expect: 1
-- Is 'Simvastatin 20 MG Oral Tablet' (312961) a statin? 1 = yes (subsumed by DRUGCLASS-STATIN).
SELECT COUNT(*) AS is_statin_312961
FROM {catalog}.{tschema}.rxnorm_closure
WHERE ancestor_code = 'DRUGCLASS-STATIN' AND descendant_code = '312961';

-- =========================================================================================
-- CLASS 5 -- value-set vintage (versioned value sets -> different population; RAG on current docs is stale)
-- =========================================================================================

-- @id: vintage_egfr_2026
-- class: 5_value_set_vintage  min_approach: metric_view  expect: 0
-- Under the MY2026 modernized KED eGFR set (CKD-EPI 98979-8 only), no patient qualifies: the synthetic data
-- records eGFR with MDRD 33914-3, dropped in 2026. (Contrast query vintage_egfr_2025 below returns 5697.)
SELECT COUNT(DISTINCT o.patient_id) AS egfr_2026_patients
FROM {catalog}.{schema}.silver_observation o
WHERE o.loinc_code IN (
  SELECT code FROM {catalog}.{tschema}.value_set_segment
  WHERE segment_id = 'KED_EGFR' AND measurement_year = '2026');

-- @id: vintage_egfr_2025
-- class: 5_value_set_vintage  min_approach: metric_view  expect: 5697
-- Contrast: the same measure under the MY2025 set (MDRD + CKD-EPI) qualifies 5697 -- the drift is real.
SELECT COUNT(DISTINCT o.patient_id) AS egfr_2025_patients
FROM {catalog}.{schema}.silver_observation o
WHERE o.loinc_code IN (
  SELECT code FROM {catalog}.{tschema}.value_set_segment
  WHERE segment_id = 'KED_EGFR' AND measurement_year = '2025');

-- =========================================================================================
-- CLASS 6 -- cross-domain protocol multi-hop (fixed-shape multi-joins over closure/edge tables)
-- =========================================================================================

-- @id: proto_statin_gap_safe
-- class: 6_protocol_multihop  min_approach: closure_sql  expect: 1667
-- Diabetics 40-75 with a statin care gap (SPD NOT_MET) AND no contraindication: not pregnant and no active
-- hepatic disease. Contraindication codes come from value_set_segment (CONTRA_PREGNANCY Z34/O26/O15/O00,
-- CONTRA_HEPATIC K70/K74); a patient is excluded if any dx falls under one of those ICD categories.
-- Base gap (no safety filter) = 1799; the contraindication filter removes 190.
SELECT COUNT(*) AS statin_gap_safe
FROM {catalog}.{schema}.gold_adherence_spd s
WHERE s.evidence_datetime IS NULL AND s.age BETWEEN 40 AND 75
  AND NOT EXISTS (
    SELECT 1 FROM {catalog}.{schema}.bronze_pat_enc_dx dx
    WHERE dx.patient_id = s.patient_id
      AND (dx.icd10_code LIKE 'Z34%' OR dx.icd10_code LIKE 'O26%'
        OR dx.icd10_code LIKE 'O15%' OR dx.icd10_code LIKE 'O00%'
        OR dx.icd10_code LIKE 'K70%' OR dx.icd10_code LIKE 'K74%'));

-- @id: proto_albuminuria_aceiarb
-- class: 6_protocol_multihop  min_approach: closure_sql  expect: 131
-- Patients with albuminuria (uACR >= 30; KED_UACR LOINC 9318-7/14959-1) NOT on an ACE inhibitor or ARB
-- (rxnorm_closure under DRUGCLASS-ACE / DRUGCLASS-ARB). protocol_edges recommends ACE/ARB for ALBUMINURIA.
-- Total with uACR >= 30 = 238; 131 of them are not on an ACE/ARB -> the protocol care gap.
SELECT COUNT(DISTINCT o.patient_id) AS albuminuria_no_aceiarb
FROM {catalog}.{schema}.silver_observation o
WHERE o.loinc_code IN ('9318-7', '14959-1') AND o.value_num >= 30
  AND NOT EXISTS (
    SELECT 1 FROM {catalog}.{schema}.bronze_order_med m
    JOIN {catalog}.{tschema}.rxnorm_closure c ON m.rxnorm_code = c.descendant_code
    WHERE m.patient_id = o.patient_id AND c.ancestor_code IN ('DRUGCLASS-ACE', 'DRUGCLASS-ARB'));

-- @id: proto_cardiorenal
-- class: 6_protocol_multihop  min_approach: closure_sql  expect: 10
-- Cardiorenal cohort = patients with diabetes (E10/E11/E13) AND CKD (N18) AND heart failure (I50) -- a
-- cross-branch intersection no single subtree expresses. Of the 10: on statin 10, on ACE/ARB 8, on SGLT2 0
-- (Synthea emits no SGLT2 fills) -- the SGLT2 guideline-care gap. (Coverage is reported by the arm, not scored here.)
WITH dm AS (SELECT DISTINCT patient_id FROM {catalog}.{schema}.bronze_pat_enc_dx
            WHERE icd10_code LIKE 'E11%' OR icd10_code LIKE 'E10%' OR icd10_code LIKE 'E13%'),
     ckd AS (SELECT DISTINCT patient_id FROM {catalog}.{schema}.bronze_pat_enc_dx WHERE icd10_code LIKE 'N18%'),
     hf AS (SELECT DISTINCT patient_id FROM {catalog}.{schema}.bronze_pat_enc_dx WHERE icd10_code LIKE 'I50%')
SELECT COUNT(*) AS cardiorenal_cohort
FROM dm JOIN ckd USING (patient_id) JOIN hf USING (patient_id);

-- @id: graph_contra_conflict
-- class: 8_graph_native  min_approach: graph  expect: 1
-- Patient fa93c75f-1541-10c2-ea84-f947c8561ce5: medications whose drug class the care protocol contraindicates
-- for one of the patient's OWN diagnoses. Path: prescribed rxnorm -> rxnorm_closure -> drug class ->
-- protocol_edges contraindicatedWith -> value_set_segment code -> ICD prefix of the patient's dx.
-- The single conflict: Simvastatin 10 MG (314231, DRUGCLASS-STATIN) x Z34.90 (pregnancy) via CONTRA_PREGNANCY, CP sec4.
SELECT COUNT(*) AS conflicts FROM (
  SELECT DISTINCT m.rxnorm_code, c.ancestor_code, e.object, dx.icd10_code
  FROM {catalog}.{schema}.bronze_order_med m
  JOIN {catalog}.{tschema}.rxnorm_closure c ON m.rxnorm_code = c.descendant_code
  JOIN {catalog}.{tschema}.protocol_edges e ON e.subject = c.ancestor_code AND e.predicate = 'contraindicatedWith'
  JOIN {catalog}.{tschema}.value_set_segment v ON v.segment_id = e.object
  JOIN {catalog}.{schema}.bronze_pat_enc_dx dx ON dx.patient_id = m.patient_id AND dx.icd10_code LIKE concat(v.code, '%')
  WHERE m.patient_id = 'fa93c75f-1541-10c2-ea84-f947c8561ce5');

-- @id: graph_patient_gaps
-- class: 8_graph_native  min_approach: graph  expect: EED,KED
-- Patient 00f63646-fc2f-16a9-53e5-951816dfefe3 (MY2026): eligible for all five measures; open care gaps by each
-- measure's live rule (the rules live in the metric views). Compliant on BPD, GSD, SPD.
SELECT array_join(array_sort(collect_list(m)), ',') AS open_gaps FROM (
  SELECT 'GSD' AS m FROM {catalog}.{schema}.gold_adherence_gsd WHERE patient_id = '00f63646-fc2f-16a9-53e5-951816dfefe3'
    AND measurement_year = 2026 AND eligible_flag AND evidence_datetime IS NULL
  UNION ALL SELECT 'KED' FROM {catalog}.{schema}.gold_adherence_ked WHERE patient_id = '00f63646-fc2f-16a9-53e5-951816dfefe3'
    AND measurement_year = 2026 AND eligible_flag AND (egfr_datetime IS NULL OR uacr_datetime IS NULL)
  UNION ALL SELECT 'BPD' FROM {catalog}.{schema}.gold_adherence_bpd WHERE patient_id = '00f63646-fc2f-16a9-53e5-951816dfefe3'
    AND measurement_year = 2026 AND eligible_flag AND NOT (systolic < 140 AND diastolic < 90)
  UNION ALL SELECT 'SPD' FROM {catalog}.{schema}.gold_adherence_spd WHERE patient_id = '00f63646-fc2f-16a9-53e5-951816dfefe3'
    AND measurement_year = 2026 AND eligible_flag AND evidence_datetime IS NULL
  UNION ALL SELECT 'EED' FROM {catalog}.{schema}.gold_adherence_eed WHERE patient_id = '00f63646-fc2f-16a9-53e5-951816dfefe3'
    AND measurement_year = 2026 AND eligible_flag AND evidence_datetime IS NULL);

-- @id: graph_statin_contra_cohort
-- class: 8_graph_native  min_approach: graph  expect: 198
-- Patients prescribed any statin who also have a diagnosis under a value set the protocol lists as a statin
-- contraindication (protocol_edges DRUGCLASS-STATIN contraindicatedWith -> value_set_segment codes, ICD prefix).
-- All 198 are via CONTRA_PREGNANCY (no CONTRA_HEPATIC dx in the data). The same traversal over the Ontobricks graph
-- (prescribed -> hasIngredient -> inDrugClass; hasDiagnosis -> subClassOf <- contains <- contraindicatedWith) = 198.
SELECT COUNT(DISTINCT m.patient_id) AS statin_with_contraindication
FROM {catalog}.{schema}.bronze_order_med m
JOIN {catalog}.{tschema}.rxnorm_closure c ON m.rxnorm_code = c.descendant_code AND c.ancestor_code = 'DRUGCLASS-STATIN'
JOIN {catalog}.{tschema}.protocol_edges e ON e.subject = 'DRUGCLASS-STATIN' AND e.predicate = 'contraindicatedWith'
JOIN {catalog}.{tschema}.value_set_segment v ON v.segment_id = e.object
JOIN {catalog}.{schema}.bronze_pat_enc_dx dx ON dx.patient_id = m.patient_id AND dx.icd10_code LIKE concat(v.code, '%');

-- @id: op_worst_clinic_annual
-- class: 9_operational_temporal  min_approach: metric_view  expect: CLINIC-04
-- Lowest protocol Step-3 adherence year-to-date, closed 90-day windows only (open windows aren't misses yet).
SELECT clinic_id, ROUND(AVG(CAST(followup_within_90d AS INT)), 3) AS step3_adherence_rate,
       COUNT(*) AS closed_obligations
FROM {catalog}.{schema}.gold_protocol_adherence
WHERE measurement_year = 2026 AND window_closed
GROUP BY clinic_id ORDER BY step3_adherence_rate, clinic_id;

-- @id: op_clinic_drift
-- class: 9_operational_temporal  min_approach: metric_view  expect: CLINIC-08
-- Each clinic's trailing-3-month adherence (ending the latest closed month) vs its OWN year-to-date baseline.
WITH c AS (
  SELECT clinic_id, date_trunc('MONTH', trigger_ts) AS m, CAST(followup_within_90d AS INT) AS f
  FROM {catalog}.{schema}.gold_protocol_adherence WHERE measurement_year = 2026 AND window_closed),
last AS (SELECT max(m) AS lm FROM c)
SELECT clinic_id,
       ROUND(AVG(CASE WHEN m > add_months(lm, -3) THEN f END), 3) AS trailing_3mo,
       ROUND(AVG(f), 3) AS own_baseline,
       ROUND(AVG(CASE WHEN m > add_months(lm, -3) THEN f END) - AVG(f), 3) AS drift
FROM c CROSS JOIN last GROUP BY clinic_id ORDER BY drift;

-- @id: op_drift_rootcause
-- class: 9_operational_temporal  min_approach: closure_sql  expect: 2026-05-15
-- The hop a KPI view can't make: join the drifting clinic to the PCP-transition dimension, before vs after.
SELECT CAST(t.transition_date AS STRING) AS transition_date, t.clinic_id, t.change_type, t.recovery_days,
       ROUND(AVG(CASE WHEN p.trigger_ts < t.transition_date THEN CAST(p.followup_within_90d AS INT) END), 3) AS adherence_before,
       ROUND(AVG(CASE WHEN p.trigger_ts >= t.transition_date THEN CAST(p.followup_within_90d AS INT) END), 3) AS adherence_after,
       t.narrative
FROM {catalog}.{schema}.panel_pcp_transition t
JOIN {catalog}.{schema}.gold_protocol_adherence p
  ON p.clinic_id = t.clinic_id AND p.window_closed AND p.measurement_year = 2026
GROUP BY ALL;
