-- Unity Catalog metric view: SSD (Diabetes Screening for People With Schizophrenia/Bipolar on Antipsychotics).
-- ACTIVE (ADR-0017): backed by gold_adherence_ssd, synthesized by src/data_generation/ssd_cohort.py and built
-- in src/pipelines/measures.py. Cross-domain cohort (SMI dx + antipsychotic dispensing + glucose/HbA1c screen).
-- {catalog}/{schema}/{semantic_schema} substituted by apply_metric_views.py. HEDIS-aligned demo, not NCQA-certified.
CREATE OR REPLACE VIEW {catalog}.{semantic_schema}.ssd_compliance_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 0.1
source: {catalog}.{schema}.gold_adherence_ssd
comment: "HEDIS SSD (Diabetes Screening for People With Schizophrenia or Bipolar Disorder Who Are Using Antipsychotic Medications). Cross-domain: SMI diagnosis + antipsychotic dispensing + glucose/HbA1c screen, ages 18-64. Denominator = eligible SMI-on-antipsychotic patients; numerator = patients with a glucose or HbA1c test in the measurement year. HEDIS-aligned demo, not NCQA-certified."
dimensions:
  - name: Measurement Year
    expr: measurement_year
    comment: "HEDIS measurement year."
    synonyms: [year, reporting year, MY]
    display_name: Measurement Year
  - name: Compliance Status
    expr: status
    comment: "MET = glucose or HbA1c screen found in the measurement year; NOT_MET = no screen."
    synonyms: [status, screening status, gap status]
    display_name: Compliance Status
  - name: Clinic
    expr: clinic_id
    comment: "Clinic (site) the SSD patient is seen at."
    synonyms: [clinic, site, location, facility]
    display_name: Clinic
  - name: Panel
    expr: panel_id
    comment: "Care panel the SSD patient belongs to."
    synonyms: [panel, pcp panel, provider panel, care team]
    display_name: Panel
  - name: Age Band
    expr: CASE WHEN age < 35 THEN '18-34' WHEN age < 50 THEN '35-49' ELSE '50-64' END
    comment: "Age band at the end of the measurement year (eligible population is 18-64)."
    synonyms: [age group, age bracket]
    display_name: Age Band
  - name: Measure
    expr: measure_id
    comment: "HEDIS measure code; this view reports SSD."
    synonyms: [measure id, hedis measure, quality measure]
    display_name: HEDIS Measure
measures:
  - name: Eligible Patients
    expr: COUNT(1)
    comment: "SMI patients on antipsychotics aged 18-64 eligible for SSD (the denominator)."
    synonyms: [denominator, eligible population, eligible count]
    display_name: Eligible Patients
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Screened Patients
    expr: COUNT(1) FILTER (WHERE numerator_flag)
    comment: "Eligible patients with a glucose or HbA1c screen in the measurement year (the numerator)."
    synonyms: [numerator, screened count, patients screened]
    display_name: Screened Patients
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: SSD Compliance Rate
    expr: "MEASURE(`Screened Patients`) / MEASURE(`Eligible Patients`)"
    comment: "Share of eligible SMI-on-antipsychotic patients screened for diabetes. Numerator / denominator; re-aggregates at any grain."
    synonyms: [compliance rate, screening rate, ssd rate, met rate]
    display_name: SSD Compliance Rate
    format: {type: percentage, decimal_places: {type: max, places: 1}}
$$
