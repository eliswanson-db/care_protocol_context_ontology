-- Unity Catalog metric view: MAD (Medication Adherence for Diabetes Medications) -- a story 3x Star measure.
-- PDC-based (proportion of days covered). {catalog}/{schema} substituted by apply_metric_views.py.
CREATE OR REPLACE VIEW {catalog}.{schema}.mad_compliance_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
source: {catalog}.{schema}.gold_adherence_mad
comment: "HEDIS MAD (Medication Adherence for Diabetes Medications). Denominator: diabetes patients 18+ with >=2 diabetes-med fills in the year; numerator: PDC >= 80%. The refill-gap / adherence measure from the story. HEDIS-aligned demo, not NCQA-certified."
dimensions:
  - name: Measurement Year
    expr: measurement_year
    synonyms: [year, reporting year, MY]
    display_name: Measurement Year
  - name: Adherence Status
    expr: status
    comment: "MET = PDC >= 80%; NOT_MET = PDC < 80% (a refill-gap / adherence gap)."
    synonyms: [status, adherence status, pdc status]
    display_name: Adherence Status
  - name: Age Band
    expr: CASE WHEN age < 45 THEN '18-44' WHEN age < 65 THEN '45-64' ELSE '65+' END
    synonyms: [age group, age bracket]
    display_name: Age Band
measures:
  - name: Eligible Patients
    expr: COUNT(1)
    comment: "Diabetes patients 18+ with >=2 diabetes-med fills in the year (the denominator)."
    synonyms: [denominator, eligible population, patients on diabetes meds]
    display_name: Eligible Patients
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: Adherent Patients
    expr: COUNT(1) FILTER (WHERE numerator_flag)
    comment: "Patients with PDC >= 80% (the numerator)."
    synonyms: [numerator, adherent, patients adherent, met]
    display_name: Adherent Patients
    format: {type: number, decimal_places: {type: exact, places: 0}}
  - name: MAD Adherence Rate
    expr: "MEASURE(`Adherent Patients`) / MEASURE(`Eligible Patients`)"
    comment: "Share of eligible patients adherent to diabetes meds (PDC >= 80%). Refill gaps pull this down."
    synonyms: [adherence rate, mad rate, medication adherence rate, pdc rate, met rate]
    display_name: MAD Adherence Rate
    format: {type: percentage, decimal_places: {type: max, places: 1}}
  - name: Avg PDC
    expr: AVG(pdc)
    comment: "Average proportion of days covered across eligible patients."
    synonyms: [average pdc, mean adherence, proportion days covered]
    display_name: Avg PDC
    format: {type: percentage, decimal_places: {type: max, places: 1}}
$$
