-- =====================================================================
-- Hierarchy encodings: closure table + segment table  (ICD-10-CM / HEDIS)
-- A third, relational differentiator alongside Genie Ontology & Ontobricks.
-- See hierarchy_encodings.md. Terminology is free-only (ADR-0002).
-- Replace ${catalog}.${schema} at deploy (DAB vars: catalog / schema).
-- =====================================================================
USE CATALOG ${catalog};
USE SCHEMA  ${schema};

-- ---------------------------------------------------------------------
-- 1) Adjacency source — the tree. ICD-10-CM parent/child (from the CMS
--    order file, or derived from code structure). A few diabetes rows shown.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS icd10_hier (
  code        STRING COMMENT 'ICD-10-CM code, e.g. E11.21',
  parent_code STRING COMMENT 'Immediate parent code, e.g. E11.2 (NULL at a root)',
  name        STRING,
  code_system STRING DEFAULT 'ICD10CM'
) COMMENT 'ICD-10-CM adjacency list (parent_id encoding). Build the closure from this.';

-- illustrative diabetes subtree (real load comes from the CMS order file)
-- INSERT: ('E11','E10-E13…','Type 2 diabetes mellitus'), ('E11.2','E11','… with kidney complications'),
--         ('E11.21','E11.2','… with diabetic nephropathy'), ('E11.22','E11.2','… with CKD'), …

-- ---------------------------------------------------------------------
-- 2) Closure table — ONE row per ancestor→descendant pair, incl. depth-0
--    self rows. The recursive walk is paid ONCE, here, at build time.
--    Rebuild on code-set / measurement-year change (ties to the drift demo).
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE icd10_closure
COMMENT 'Transitive closure of icd10_hier. Select a whole subtree with one equality: WHERE ancestor_code = X.'
AS
WITH RECURSIVE walk AS (
  SELECT code AS ancestor_code, code AS descendant_code, 0 AS depth
  FROM icd10_hier                                  -- depth-0 self rows
  UNION ALL
  SELECT w.ancestor_code, h.code, w.depth + 1
  FROM walk w
  JOIN icd10_hier h ON h.parent_code = w.descendant_code
)
SELECT w.ancestor_code, a.name AS ancestor_name,
       w.descendant_code, d.name AS descendant_name, w.depth
FROM walk w
JOIN icd10_hier a ON a.code = w.ancestor_code
JOIN icd10_hier d ON d.code = w.descendant_code;

-- (Optional) same pattern over the LOINC Part hierarchy for the lab-concept side:
--   CREATE OR REPLACE TABLE loinc_part_closure AS WITH RECURSIVE … ;

-- ---------------------------------------------------------------------
-- 3) Segment table — named sets that cut ACROSS the tree (value sets /
--    cohorts). The "rules that ignore the hierarchy." Each has an owner.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS value_set_segment (
  segment_id       STRING  COMMENT 'e.g. HEDIS_DIABETES_DENOM',
  segment_name     STRING,
  code             STRING,
  code_system      STRING  COMMENT 'ICD10CM | LOINC | RXNORM',
  measurement_year INT,
  owner            STRING  COMMENT 'named owner — every segment definition needs one',
  effective_from   DATE,
  effective_to     DATE
) COMMENT 'Cross-branch named sets (HEDIS demo value sets / cohorts). Not NCQA/VSAC — demo only.';

-- =====================================================================
-- DEMO: the same question, written three ways
-- =====================================================================

-- QUESTION A — "diabetes denominator": patients with any code under E10/E11/E13.

-- A1) Adjacency / recursive CTE — unbounded depth needs a walk; shape changes
--     per question and is easy to get wrong (benchmark room wrote 0 correct CTEs).
WITH RECURSIVE dm AS (
  SELECT code FROM icd10_hier WHERE code IN ('E10','E11','E13')
  UNION ALL
  SELECT h.code FROM icd10_hier h JOIN dm ON h.parent_code = dm.code
)
SELECT count(DISTINCT dx.patient_id) AS dm_patients
FROM dx JOIN dm ON dx.icd10_code = dm.code;

-- A2) Closure / one equality at every depth — automatically includes E11.21
--     (the T3 subsumption tracer). Only the literal list changes between questions.
SELECT count(DISTINCT dx.patient_id) AS dm_patients
FROM dx
JOIN icd10_closure c ON c.descendant_code = dx.icd10_code
WHERE c.ancestor_code IN ('E10','E11','E13');

-- QUESTION B — cross-branch cohort (the "Strategic Assortment" analog): a curated
-- diabetes value set spanning branches with specific includes/excludes. NO subtree
-- equals it — only the segment table answers it.
SELECT count(DISTINCT dx.patient_id) AS dm_denominator
FROM dx
JOIN value_set_segment s
  ON s.code = dx.icd10_code AND s.code_system = 'ICD10CM'
WHERE s.segment_id = 'HEDIS_DIABETES_DENOM'
  AND s.measurement_year = 2025;

-- Inspect the subtree the closure returns (teaching view):
--   SELECT descendant_code, descendant_name, depth
--   FROM icd10_closure WHERE ancestor_code = 'E11' ORDER BY depth, descendant_code;
