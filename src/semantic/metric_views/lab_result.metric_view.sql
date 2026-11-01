-- Unity Catalog metric view: LOINC Lab Measures (MV-2). Governed KPI layer over gold_lab_result -- lab
-- observations enriched with LOINC multiaxial Parts so results aggregate by SEMANTIC concept (Component)
-- across code vintages and assay methods. This is the "graph > closure WITHIN a vocabulary" exemplar from the
-- benchmark charter: "all A1c regardless of method" = one Component (LP-HBA1C), spanning three LOINC codes.
-- Backs the LOINC Lab Measures Genie agent (AG-2). {catalog}/{schema}/{semantic_schema} substituted by
-- apply_metric_views.py. Rich comment/synonyms/display_name are intentional ontology fuel for Genie.
-- Synthetic; LOINC (c) Regenstrief, used under the LOINC License. HEDIS-aligned demo, not NCQA-certified.
CREATE OR REPLACE VIEW {catalog}.{semantic_schema}.lab_result_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
source: {catalog}.{schema}.gold_lab_result
comment: "LOINC lab-result measures over the synthetic observation stream, enriched with LOINC multiaxial Parts. Group by Lab Concept (Component) to count labs by WHAT was measured regardless of code vintage or method -- the multiaxial-identity capability a flat code list or a single is-a closure cannot express. Averages are only meaningful within a single Concept/Code (units differ across analytes). Synthetic; LOINC (c) Regenstrief under the LOINC License."
dimensions:
  - name: Measurement Year
    expr: measurement_year
    comment: "Calendar year of the lab result (YEAR(result_ts))."
    synonyms: [year, result year, reporting year]
    display_name: Measurement Year
  - name: Lab Concept
    expr: COALESCE(component, 'Uncoded (no LOINC Part)')
    comment: "LOINC Component Part -- WHAT the test measures (e.g. 'Hemoglobin A1c/Hemoglobin.total', 'Glomerular filtration rate.predicted', 'Albumin/Creatinine'). The multiaxial grouping key: one Concept spans every code/method that measures it. 'Uncoded' when the LOINC code has no Part in the demo subset."
    synonyms: [concept, component, analyte, what was measured, lab type, loinc component]
    display_name: Lab Concept (LOINC Component)
  - name: LOINC Code
    expr: loinc_code
    comment: "The specific LOINC code of the result (e.g. 4548-4, 17856-6, 98979-8). Several codes can share one Lab Concept."
    synonyms: [loinc, code, test code, lab code]
    display_name: LOINC Code
  - name: Lab Test
    expr: description
    comment: "Human-readable lab/test name as recorded on the observation."
    synonyms: [test name, lab name, test]
    display_name: Lab Test
  - name: Specimen System
    expr: COALESCE(specimen_system, 'Unspecified')
    comment: "LOINC System Part -- the specimen/site (e.g. Blood, Serum or Plasma, Urine, Arterial system)."
    synonyms: [system, specimen, sample, source, matrix]
    display_name: Specimen System
  - name: Method
    expr: COALESCE(method, 'Unspecified')
    comment: "LOINC Method Part -- the assay/technique (e.g. HPLC, IFCC, MDRD, CKD-EPI). Distinguishing Concept from Method is the point: HbA1c by HPLC and by IFCC are the SAME Concept, different Method."
    synonyms: [assay, technique, measurement method, how measured]
    display_name: Method
  - name: Units
    expr: COALESCE(units, 'Unspecified')
    comment: "Result units of measure as recorded."
    synonyms: [unit, uom, units of measure]
    display_name: Units
measures:
  - name: Observations
    expr: COUNT(1)
    comment: "Number of lab result rows (one per recorded numeric observation)."
    synonyms: [results, result count, tests performed, number of labs, observation count]
    display_name: Observations
    format:
      type: number
      decimal_places: {type: exact, places: 0}
  - name: Patients Tested
    expr: COUNT(DISTINCT patient_id)
    comment: "Distinct patients with at least one result in the grouping. Use this (not Observations) for 'how many patients were tested'."
    synonyms: [patients, distinct patients, patients with a result, tested patients, people tested]
    display_name: Patients Tested
    format:
      type: number
      decimal_places: {type: exact, places: 0}
  - name: Average Result
    expr: AVG(value_num)
    comment: "Mean numeric result value. Only meaningful grouped by a single Lab Concept or LOINC Code -- units differ across analytes (A1c % vs eGFR mL/min vs mmHg)."
    synonyms: [avg value, mean result, average value, mean]
    display_name: Average Result
    format:
      type: number
      decimal_places: {type: max, places: 2}
  - name: Min Result
    expr: MIN(value_num)
    comment: "Minimum numeric result value in the grouping (interpret within one Concept/Code)."
    synonyms: [minimum, lowest, min value]
    display_name: Min Result
    format:
      type: number
      decimal_places: {type: max, places: 2}
  - name: Max Result
    expr: MAX(value_num)
    comment: "Maximum numeric result value in the grouping (interpret within one Concept/Code)."
    synonyms: [maximum, highest, max value]
    display_name: Max Result
    format:
      type: number
      decimal_places: {type: max, places: 2}
$$
