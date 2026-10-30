-- Column-level UC comments for the care_protocol_terminology schema. Ontology fuel: Genie indexes these.
-- {catalog} substituted by apply_comments.py. One statement per line, ';'-terminated. Idempotent.

-- icd10_closure: transitive closure of the ICD-10-CM hierarchy (ancestor -> descendant, all depths).
COMMENT ON COLUMN {catalog}.care_protocol_terminology.icd10_closure.ancestor_code IS 'ICD-10-CM code of the ancestor (broader) concept, e.g. E11 (Type 2 diabetes mellitus).';
COMMENT ON COLUMN {catalog}.care_protocol_terminology.icd10_closure.ancestor_name IS 'Name of the ancestor concept.';
COMMENT ON COLUMN {catalog}.care_protocol_terminology.icd10_closure.descendant_code IS 'ICD-10-CM code of the descendant (narrower) concept, e.g. E11.21. A single equality join on this column subsumes the whole subtree.';
COMMENT ON COLUMN {catalog}.care_protocol_terminology.icd10_closure.descendant_name IS 'Name of the descendant concept.';
COMMENT ON COLUMN {catalog}.care_protocol_terminology.icd10_closure.depth IS 'Hierarchy distance from ancestor to descendant (0 = self). Enables subsumption queries without recursive CTEs.';

-- value_set_segment: hand-curated HEDIS value sets as code segments (supports cross-branch sets).
COMMENT ON COLUMN {catalog}.care_protocol_terminology.value_set_segment.segment_id IS 'Value-set segment identifier, e.g. GSD_A1C_TEST (A1c lab codes), KED_EGFR, SPD_STATIN.';
COMMENT ON COLUMN {catalog}.care_protocol_terminology.value_set_segment.segment_name IS 'Human-readable value-set name.';
COMMENT ON COLUMN {catalog}.care_protocol_terminology.value_set_segment.code IS 'A member code of the value set (LOINC, ICD-10-CM, or RxNorm depending on code_system).';
COMMENT ON COLUMN {catalog}.care_protocol_terminology.value_set_segment.code_system IS 'Terminology the code belongs to: LOINC, ICD10CM, or RXNORM.';
COMMENT ON COLUMN {catalog}.care_protocol_terminology.value_set_segment.measurement_year IS 'HEDIS measurement year the value-set version applies to (drift demo: value sets change across years).';
COMMENT ON COLUMN {catalog}.care_protocol_terminology.value_set_segment.owner IS 'Steward/owner of the value-set segment.';

-- loinc: curated LOINC lab terminology subset.
COMMENT ON COLUMN {catalog}.care_protocol_terminology.loinc.loinc_code IS 'LOINC code (e.g. 4548-4 = Hemoglobin A1c / HbA1c in blood).';
COMMENT ON COLUMN {catalog}.care_protocol_terminology.loinc.long_common_name IS 'LOINC long common name for the lab test.';
COMMENT ON COLUMN {catalog}.care_protocol_terminology.loinc.concept IS 'Short semantic concept label grouping related LOINC codes (e.g. A1C, EGFR, UACR, BP).';
