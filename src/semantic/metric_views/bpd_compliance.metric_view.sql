-- Unity Catalog metric view: BPD (Blood Pressure control for Patients With Diabetes).
-- Governed KPI layer over gold_adherence_bpd. {catalog}/{schema} substituted by apply_metric_views.py.
-- Rich comment/synonyms/display_name are intentional ontology fuel for Genie. HEDIS-aligned demo, not NCQA-certified.
CREATE OR REPLACE VIEW {catalog}.{schema}.bpd_compliance_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
source: {catalog}.{schema}.gold_adherence_bpd
comment: "HEDIS BPD (Blood Pressure control) compliance for the diabetes population aged 18-75. Denominator = eligible diabetes patients; numerator = most recent blood-pressure reading in the measurement year is controlled (<140/90). HEDIS-aligned demo, not NCQA-certified."
dimensions:
  - name: Measurement Year
    expr: measurement_year
    synonyms: [year, reporting year, MY]
    display_name: Measurement Year
  - name: Compliance Status
    expr: status
    comment: "MET = latest measurement-year BP is controlled (<140/90); NOT_MET = uncontrolled or no reading."
    synonyms: [status, met status, adherence status, gap status, bp control status]
    display_name: Compliance Status
  - name: Age Band
    expr: CASE
      WHEN age < 45 THEN '18-44'
      WHEN age < 65 THEN '45-64'
      ELSE '65-75'
      END
    comment: "Age band at the end of the measurement year (BPD eligible population is 18-75)."
    synonyms: [age group, age bracket, age range]
    display_name: Age Band
  - name: Measure
    expr: measure_id
    synonyms: [measure id, hedis measure, quality measure]
    display_name: HEDIS Measure
measures:
  - name: Eligible Patients
    expr: COUNT(1)
    comment: "Diabetes patients aged 18-75 eligible for BPD (the measure denominator). One row per patient."
    synonyms: [denominator, eligible population, eligible count, patients eligible]
    display_name: Eligible Patients
    format:
      type: number
      decimal_places: {type: exact, places: 0}
  - name: Controlled Patients
    expr: COUNT(1) FILTER (WHERE numerator_flag)
    comment: "Eligible patients whose most recent measurement-year BP reading is controlled (<140/90) -- the numerator."
    synonyms: [numerator, controlled count, patients met, bp controlled]
    display_name: Controlled Patients
    format:
      type: number
      decimal_places: {type: exact, places: 0}
  - name: BPD Compliance Rate
    expr: "MEASURE(`Controlled Patients`) / MEASURE(`Eligible Patients`)"
    comment: "Share of eligible diabetes patients with a controlled most-recent BP (<140/90) in the measurement year. Numerator / denominator; re-aggregates at any grain."
    synonyms: [compliance rate, adherence rate, bpd rate, bp control rate, blood pressure control rate, met rate]
    display_name: BPD Compliance Rate
    format:
      type: percentage
      decimal_places: {type: max, places: 1}
  - name: Avg Systolic
    expr: AVG(systolic)
    comment: "Average systolic blood pressure of the latest measurement-year readings."
    synonyms: [average systolic, mean systolic, systolic bp]
    display_name: Avg Systolic
    format:
      type: number
      decimal_places: {type: max, places: 0}
  - name: Avg Diastolic
    expr: AVG(diastolic)
    comment: "Average diastolic blood pressure of the latest measurement-year readings."
    synonyms: [average diastolic, mean diastolic, diastolic bp]
    display_name: Avg Diastolic
    format:
      type: number
      decimal_places: {type: max, places: 0}
$$
