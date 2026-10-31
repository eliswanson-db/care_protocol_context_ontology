-- Unity Catalog metric view: EED (Eye Exam for Patients With Diabetes).
-- Governed KPI layer over gold_adherence_eed. {catalog}/{schema}/{semantic_schema} substituted by apply_metric_views.py.
-- Rich comment/synonyms/display_name are intentional ontology fuel for Genie. HEDIS-aligned demo, not NCQA-certified.
CREATE OR REPLACE VIEW {catalog}.{semantic_schema}.eed_compliance_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
source: {catalog}.{schema}.gold_adherence_eed
comment: "HEDIS EED (Eye Exam) compliance for the diabetes population aged 18-75. Denominator = eligible diabetes patients; numerator = a retinal/diabetic eye exam (SNOMED procedure value set) in the measurement year. HEDIS-aligned demo, not NCQA-certified."
dimensions:
  - name: Measurement Year
    expr: measurement_year
    comment: "HEDIS measurement year the metrics are computed for (e.g. 2025)."
    synonyms: [year, reporting year, MY]
    display_name: Measurement Year
  - name: Compliance Status
    expr: status
    comment: "MET = a diabetic eye exam was found in the measurement year; NOT_MET = no exam (care gap)."
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
    expr: COALESCE(gap_reason, 'Met')
    comment: "Why the patient is a care gap (NOT_MET); 'Met' when compliant. Group care gaps by reason."
    synonyms: [gap reason, reason, care gap reason, why gap]
    display_name: Gap Reason
  - name: Age Band
    expr: CASE
      WHEN age < 45 THEN '18-44'
      WHEN age < 65 THEN '45-64'
      ELSE '65-75'
      END
    comment: "Age band at the end of the measurement year (EED eligible population is 18-75)."
    synonyms: [age group, age bracket, age range]
    display_name: Age Band
  - name: Measure
    expr: measure_id
    comment: "HEDIS measure code; this view reports EED (Eye Exam)."
    synonyms: [measure id, hedis measure, quality measure]
    display_name: HEDIS Measure
measures:
  - name: Eligible Patients
    expr: COUNT(1)
    comment: "Diabetes patients aged 18-75 eligible for EED (the measure denominator). One row per patient."
    synonyms: [denominator, eligible population, eligible count, patients eligible]
    display_name: Eligible Patients
    format:
      type: number
      decimal_places: {type: exact, places: 0}
  - name: Eye Exam Patients
    expr: COUNT(1) FILTER (WHERE numerator_flag)
    comment: "Eligible patients with a retinal/diabetic eye exam in the measurement year (the numerator)."
    synonyms: [numerator, exam done, patients met, retinal exam, eye exam count]
    display_name: Eye Exam Patients
    format:
      type: number
      decimal_places: {type: exact, places: 0}
  - name: EED Compliance Rate
    expr: "MEASURE(`Eye Exam Patients`) / MEASURE(`Eligible Patients`)"
    comment: "Share of eligible diabetes patients with a diabetic eye exam in the measurement year. Numerator / denominator; re-aggregates at any grain."
    synonyms: [compliance rate, adherence rate, eed rate, eye exam rate, retinal exam rate, met rate]
    display_name: EED Compliance Rate
    format:
      type: percentage
      decimal_places: {type: max, places: 1}
$$
