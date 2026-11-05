-- Unity Catalog metric view: KED (Kidney Health Evaluation for Patients With Diabetes).
-- Governed KPI layer over gold_adherence_ked. The numerator is COMPOUND (eGFR AND uACR), so this view
-- exposes each component rate plus the combined rate. {catalog}/{schema}/{semantic_schema} substituted by apply_metric_views.py.
-- Rich comment/synonyms/display_name are intentional ontology fuel for Genie. HEDIS-aligned demo, not NCQA-certified.
CREATE OR REPLACE VIEW {catalog}.{semantic_schema}.ked_compliance_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
source: {catalog}.{schema}.gold_adherence_ked
comment: "HEDIS KED (Kidney Health Evaluation) compliance for the diabetes population aged 18-85. Denominator = eligible diabetes patients; numerator requires BOTH an eGFR test and a uACR test in the measurement year. Exposes the combined rate and each component (eGFR, uACR) separately. HEDIS-aligned demo, not NCQA-certified."
dimensions:
  - name: Measurement Year
    expr: measurement_year
    comment: "HEDIS measurement year the metrics are computed for (e.g. 2026)."
    synonyms: [year, reporting year, MY]
    display_name: Measurement Year
  - name: Compliance Status
    expr: "CASE WHEN egfr_datetime IS NOT NULL AND uacr_datetime IS NOT NULL THEN 'MET' ELSE 'NOT_MET' END"
    comment: "Computed live: MET = both an eGFR and a uACR test were found in the measurement year; NOT_MET = at least one is missing."
    synonyms: [status, met status, adherence status, gap status]
    display_name: Compliance Status
  - name: Clinic
    expr: clinic_id
    comment: "Clinic (site) the patient's panel belongs to. Enables care-gap and compliance rates by site."
    synonyms: [clinic, site, location, facility]
    display_name: Clinic
  - name: Panel
    expr: panel_id
    comment: "PCP panel the patient belongs to."
    synonyms: [panel, pcp panel, provider panel, care team]
    display_name: Panel
  - name: Gap Reason
    expr: "CASE WHEN egfr_datetime IS NOT NULL AND uacr_datetime IS NOT NULL THEN 'Met' WHEN egfr_datetime IS NULL AND uacr_datetime IS NULL THEN 'No eGFR or uACR test' WHEN egfr_datetime IS NULL THEN 'No eGFR test' ELSE 'No uACR test' END"
    comment: "Computed live: why the patient is a care gap (NOT_MET); 'Met' when compliant. Group care gaps by reason."
    synonyms: [gap reason, reason, care gap reason, why gap]
    display_name: Gap Reason
  - name: Age Band
    expr: CASE
      WHEN age < 45 THEN '18-44'
      WHEN age < 65 THEN '45-64'
      ELSE '65-85'
      END
    comment: "Age band at the end of the measurement year (KED eligible population is 18-85)."
    synonyms: [age group, age bracket, age range]
    display_name: Age Band
  - name: Measure
    expr: measure_id
    comment: "HEDIS measure code; this view reports KED (Kidney Health Evaluation)."
    synonyms: [measure id, hedis measure, quality measure]
    display_name: HEDIS Measure
measures:
  - name: Eligible Patients
    expr: COUNT(1)
    comment: "Diabetes patients aged 18-85 eligible for KED (the measure denominator). One row per patient."
    synonyms: [denominator, eligible population, eligible count, patients eligible]
    display_name: Eligible Patients
    format:
      type: number
      decimal_places: {type: exact, places: 0}
  - name: eGFR Tested Patients
    expr: "COUNT(1) FILTER (WHERE egfr_datetime IS NOT NULL)"
    comment: "Eligible patients with at least one eGFR (estimated glomerular filtration rate) test in the measurement year."
    synonyms: [egfr tested, gfr tested, kidney function tested, egfr count]
    display_name: eGFR Tested Patients
    format:
      type: number
      decimal_places: {type: exact, places: 0}
  - name: uACR Tested Patients
    expr: "COUNT(1) FILTER (WHERE uacr_datetime IS NOT NULL)"
    comment: "Eligible patients with at least one uACR (urine albumin-creatinine ratio) test in the measurement year."
    synonyms: [uacr tested, urine albumin tested, microalbumin tested, uacr count]
    display_name: uACR Tested Patients
    format:
      type: number
      decimal_places: {type: exact, places: 0}
  - name: Compliant Patients
    expr: "COUNT(1) FILTER (WHERE egfr_datetime IS NOT NULL AND uacr_datetime IS NOT NULL)"
    comment: "Eligible patients meeting the full KED numerator: BOTH an eGFR and a uACR test in the measurement year — computed live."
    synonyms: [numerator, compliant count, patients met, both tests, complete kidney eval]
    display_name: Compliant Patients
    format:
      type: number
      decimal_places: {type: exact, places: 0}
  - name: KED Compliance Rate
    expr: "MEASURE(`Compliant Patients`) / MEASURE(`Eligible Patients`)"
    comment: "Share of eligible diabetes patients with BOTH an eGFR and a uACR test in the measurement year. Numerator / denominator; re-aggregates at any grain."
    synonyms: [compliance rate, adherence rate, ked rate, kidney eval rate, met rate]
    display_name: KED Compliance Rate
    format:
      type: percentage
      decimal_places: {type: max, places: 1}
  - name: eGFR Test Rate
    expr: "MEASURE(`eGFR Tested Patients`) / MEASURE(`Eligible Patients`)"
    comment: "Share of eligible patients with an eGFR test. Component of the KED numerator."
    synonyms: [egfr rate, gfr test rate]
    display_name: eGFR Test Rate
    format:
      type: percentage
      decimal_places: {type: max, places: 1}
  - name: uACR Test Rate
    expr: "MEASURE(`uACR Tested Patients`) / MEASURE(`Eligible Patients`)"
    comment: "Share of eligible patients with a uACR test. Component of the KED numerator; typically the limiting component."
    synonyms: [uacr rate, urine albumin rate]
    display_name: uACR Test Rate
    format:
      type: percentage
      decimal_places: {type: max, places: 1}
$$
