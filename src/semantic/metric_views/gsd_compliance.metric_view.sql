-- Unity Catalog metric view: GSD (Glycemic Status Assessment for Patients With Diabetes).
-- The GOVERNED SEMANTIC LAYER for the measure: the compliance RULE lives HERE, computed live, NOT baked in gold.
-- gold_adherence_gsd is now an EVIDENCE base (one row per eligible patient + latest A1c); this view derives the
-- numerator (>=1 A1c test = evidence_datetime IS NOT NULL), MET/UNMET status, care-gap reason, and the control
-- bands (<8 / >9 on evidence_value) as live expressions that re-aggregate at any grain. Consumed by dashboards,
-- Genie, and SQL. {catalog}/{schema}/{semantic_schema} substituted by apply_metric_views.py. HEDIS-aligned demo.
-- Rich comment/synonyms/display_name are intentional: they are the human-modeled fuel the Genie Ontology indexes.
CREATE OR REPLACE VIEW {catalog}.{semantic_schema}.gsd_compliance_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
source: {catalog}.{schema}.gold_adherence_gsd
comment: "HEDIS GSD (Glycemic Status Assessment) compliance for the diabetes population aged 18-75. The measure is DEFINED here, computed live over the gold evidence base: denominator = eligible diabetes patients; numerator = patients with an A1c test (LOINC) in the measurement year (evidence present). Also exposes glycemic-control bands (good <8%, poor >9%). HEDIS-aligned demo, not NCQA-certified."
dimensions:
  - name: Measurement Year
    expr: measurement_year
    comment: "HEDIS measurement year the metrics are computed for (e.g. 2026)."
    synonyms: [year, reporting year, MY]
    display_name: Measurement Year
  - name: Compliance Status
    expr: "CASE WHEN evidence_datetime IS NOT NULL THEN 'MET' ELSE 'NOT_MET' END"
    comment: "Computed live: MET = an A1c test exists in the measurement year; NOT_MET = no A1c test. The rule lives in this metric view, not in gold."
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
    expr: "CASE WHEN evidence_datetime IS NOT NULL THEN 'Met' ELSE 'No A1c test in measurement year' END"
    comment: "Computed live: why the patient is a care gap (NOT_MET); 'Met' when compliant. Group care gaps by reason."
    synonyms: [gap reason, reason, care gap reason, why gap]
    display_name: Gap Reason
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
    comment: "HEDIS measure code; this view reports GSD (Glycemic Status Assessment)."
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
    expr: "COUNT(1) FILTER (WHERE evidence_datetime IS NOT NULL)"
    comment: "Eligible patients with at least one A1c test in the measurement year (the measure numerator) — computed live from the evidence."
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
    expr: "COUNT(1) FILTER (WHERE evidence_value < 8.0)"
    comment: "Patients whose latest measurement-year A1c is < 8.0% (good glycemic control) — band computed live from evidence_value."
    synonyms: [good control, well controlled, a1c under 8]
    display_name: Good Control (<8%) Patients
    format:
      type: number
      decimal_places: {type: exact, places: 0}
  - name: Poor Control Patients
    expr: "COUNT(1) FILTER (WHERE evidence_value > 9.0)"
    comment: "Patients whose latest measurement-year A1c is > 9.0% (poor glycemic control) — band computed live from evidence_value."
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
