-- Unity Catalog metric view: SPD (Statin Therapy for Patients With Diabetes).
-- Governed KPI layer over gold_adherence_spd. {catalog}/{schema} substituted by apply_metric_views.py.
-- Statins are resolved by subsumption over rxnorm_closure (ingredient -> clinical drug). HEDIS-aligned demo, not NCQA-certified.
CREATE OR REPLACE VIEW {catalog}.{schema}.spd_compliance_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
source: {catalog}.{schema}.gold_adherence_spd
comment: "HEDIS SPD (Statin Therapy) compliance for the diabetes population aged 40-75. Denominator = eligible diabetes patients; numerator = dispensed a statin in the measurement year (statins resolved from RxNorm ingredients to clinical drugs via subsumption). HEDIS-aligned demo, not NCQA-certified."
dimensions:
  - name: Measurement Year
    expr: measurement_year
    synonyms: [year, reporting year, MY]
    display_name: Measurement Year
  - name: Compliance Status
    expr: status
    comment: "MET = a statin was dispensed in the measurement year; NOT_MET = no statin (care gap)."
    synonyms: [status, met status, adherence status, gap status]
    display_name: Compliance Status
  - name: Age Band
    expr: CASE
      WHEN age < 55 THEN '40-54'
      WHEN age < 65 THEN '55-64'
      ELSE '65-75'
      END
    comment: "Age band at the end of the measurement year (SPD eligible population is 40-75)."
    synonyms: [age group, age bracket, age range]
    display_name: Age Band
  - name: Measure
    expr: measure_id
    synonyms: [measure id, hedis measure, quality measure]
    display_name: HEDIS Measure
measures:
  - name: Eligible Patients
    expr: COUNT(1)
    comment: "Diabetes patients aged 40-75 eligible for SPD (the measure denominator). One row per patient."
    synonyms: [denominator, eligible population, eligible count, patients eligible]
    display_name: Eligible Patients
    format:
      type: number
      decimal_places: {type: exact, places: 0}
  - name: On Statin Patients
    expr: COUNT(1) FILTER (WHERE numerator_flag)
    comment: "Eligible patients dispensed a statin in the measurement year (the numerator)."
    synonyms: [numerator, on statin, statin count, patients on statin, patients met]
    display_name: On Statin Patients
    format:
      type: number
      decimal_places: {type: exact, places: 0}
  - name: SPD Compliance Rate
    expr: "MEASURE(`On Statin Patients`) / MEASURE(`Eligible Patients`)"
    comment: "Share of eligible diabetes patients dispensed a statin in the measurement year. Numerator / denominator; re-aggregates at any grain."
    synonyms: [compliance rate, adherence rate, spd rate, statin therapy rate, statin rate, met rate]
    display_name: SPD Compliance Rate
    format:
      type: percentage
      decimal_places: {type: max, places: 1}
$$
