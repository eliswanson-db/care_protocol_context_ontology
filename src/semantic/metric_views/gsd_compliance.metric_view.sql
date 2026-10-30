-- Unity Catalog metric view: GSD (Glycemic Status Assessment for Patients With Diabetes).
-- Governed, reusable KPI layer over gold_adherence_gsd. Consumed by dashboards, Genie, and SQL.
-- {catalog}/{schema} are substituted by apply_metric_views.py (serverless task). HEDIS-aligned demo, not NCQA-certified.
-- Rich comment/synonyms/display_name are intentional: they are the human-modeled fuel the Genie Ontology indexes.
CREATE OR REPLACE VIEW {catalog}.{schema}.gsd_compliance_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
source: {catalog}.{schema}.gold_adherence_gsd
comment: "HEDIS GSD (Glycemic Status Assessment) compliance for the diabetes population aged 18-75. Denominator = eligible diabetes patients; numerator = patients with an A1c test (LOINC) in the measurement year. Also exposes glycemic-control bands (good <8%, poor >9%). HEDIS-aligned demo, not NCQA-certified."
dimensions:
  - name: Measurement Year
    expr: measurement_year
    synonyms: [year, reporting year, MY]
    display_name: Measurement Year
  - name: Compliance Status
    expr: status
    comment: "MET = A1c test found in the measurement year; NOT_MET = no A1c test."
    synonyms: [status, met status, adherence status, gap status]
    display_name: Compliance Status
  - name: Age Band
    expr: CASE
      WHEN age < 45 THEN '18-44'
      WHEN age < 65 THEN '45-64'
      ELSE '65-75'
      END
    comment: "Age band at the end of the measurement year (eligible population is 18-75)."
    synonyms: [age group, age bracket, age range]
    display_name: Age Band
  - name: Measure
    expr: measure_id
    synonyms: [measure id, hedis measure, quality measure]
    display_name: HEDIS Measure
measures:
  - name: Eligible Patients
    expr: COUNT(1)
    comment: "Diabetes patients aged 18-75 eligible for GSD (the measure denominator). One row per patient."
    synonyms: [denominator, eligible population, eligible count, patients eligible]
    display_name: Eligible Patients
    format:
      type: number
      decimal_places: {type: exact, places: 0}
  - name: Compliant Patients
    expr: COUNT(1) FILTER (WHERE numerator_flag)
    comment: "Eligible patients with at least one A1c test in the measurement year (the measure numerator)."
    synonyms: [numerator, compliant count, patients met, tested patients, a1c tested]
    display_name: Compliant Patients
    format:
      type: number
      decimal_places: {type: exact, places: 0}
  - name: GSD Compliance Rate
    expr: "MEASURE(`Compliant Patients`) / MEASURE(`Eligible Patients`)"
    comment: "Share of eligible diabetes patients with an A1c test in the measurement year. Numerator / denominator; re-aggregates at any grain."
    synonyms: [compliance rate, adherence rate, gsd rate, a1c testing rate, met rate, screening rate]
    display_name: GSD Compliance Rate
    format:
      type: percentage
      decimal_places: {type: max, places: 1}
  - name: Good Control Patients
    expr: COUNT(1) FILTER (WHERE a1c_lt8)
    comment: "Patients whose latest measurement-year A1c is < 8.0% (good glycemic control)."
    synonyms: [good control, well controlled, a1c under 8]
    display_name: Good Control (<8%) Patients
    format:
      type: number
      decimal_places: {type: exact, places: 0}
  - name: Poor Control Patients
    expr: COUNT(1) FILTER (WHERE a1c_gt9)
    comment: "Patients whose latest measurement-year A1c is > 9.0% (poor glycemic control)."
    synonyms: [poor control, poorly controlled, uncontrolled, a1c over 9]
    display_name: Poor Control (>9%) Patients
    format:
      type: number
      decimal_places: {type: exact, places: 0}
  - name: Poor Control Rate
    expr: "MEASURE(`Poor Control Patients`) / MEASURE(`Compliant Patients`)"
    comment: "Share of A1c-tested patients whose latest A1c is > 9.0%."
    synonyms: [poor control rate, uncontrolled rate]
    display_name: Poor Control Rate
    format:
      type: percentage
      decimal_places: {type: max, places: 1}
$$
