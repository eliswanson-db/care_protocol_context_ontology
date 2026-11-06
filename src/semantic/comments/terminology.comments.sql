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

-- icd10_hier: raw parent/child edges of the ICD-10-CM hierarchy. icd10_closure is the transitive expansion of this.
COMMENT ON COLUMN {catalog}.care_protocol_terminology.icd10_hier.code IS 'ICD-10-CM code of this concept (the child node of a direct parent/child edge).';
COMMENT ON COLUMN {catalog}.care_protocol_terminology.icd10_hier.parent_code IS 'ICD-10-CM code of the immediate parent concept. Direct edges only; transitively expanded (all depths) into icd10_closure.';
COMMENT ON COLUMN {catalog}.care_protocol_terminology.icd10_hier.name IS 'Human-readable name of the ICD-10-CM concept.';

-- rxnorm_hier: raw parent/child edges of RxNorm (ingredient -> clinical drug). rxnorm_closure is its transitive expansion.
COMMENT ON COLUMN {catalog}.care_protocol_terminology.rxnorm_hier.code IS 'RxNorm rxcui of this concept (child node of the edge), typically a clinical drug.';
COMMENT ON COLUMN {catalog}.care_protocol_terminology.rxnorm_hier.parent_code IS 'RxNorm rxcui of the immediate parent concept (e.g. the ingredient). Transitively expanded into rxnorm_closure.';
COMMENT ON COLUMN {catalog}.care_protocol_terminology.rxnorm_hier.name IS 'Human-readable RxNorm concept name.';
COMMENT ON COLUMN {catalog}.care_protocol_terminology.rxnorm_hier.relationship IS 'Edge type: class_member (drug class -> ingredient) or ingredient_of (ingredient -> clinical drug). Each relationship has its own closure (drug_class_closure, rxnorm_ingredient_closure); rxnorm_closure is their composition.';

-- rxnorm_statin: the statin ingredient value set (seed codes for SPD subsumption).
COMMENT ON COLUMN {catalog}.care_protocol_terminology.rxnorm_statin.rxcui IS 'RxNorm ingredient rxcui for a statin (e.g. 36567 simvastatin). Joined to rxnorm_closure to subsume every statin clinical drug for the SPD numerator.';
COMMENT ON COLUMN {catalog}.care_protocol_terminology.rxnorm_statin.ingredient IS 'Statin ingredient name (e.g. simvastatin, atorvastatin).';

-- loinc_parts: LOINC multiaxial Parts -- each LOINC code decomposed into its semantic axes (component/system/method).
COMMENT ON COLUMN {catalog}.care_protocol_terminology.loinc_parts.loinc_code IS 'LOINC code being decomposed into its semantic Parts (e.g. 4548-4 Hemoglobin A1c).';
COMMENT ON COLUMN {catalog}.care_protocol_terminology.loinc_parts.loinc_name IS 'LOINC long common name of the code.';
COMMENT ON COLUMN {catalog}.care_protocol_terminology.loinc_parts.predicate IS 'LOINC Part axis / relationship: has_component, has_system, has_method, etc.';
COMMENT ON COLUMN {catalog}.care_protocol_terminology.loinc_parts.part IS 'LOINC Part code on the object side of the predicate (e.g. LP-HBA1C, LP-SYS-BLD).';
COMMENT ON COLUMN {catalog}.care_protocol_terminology.loinc_parts.part_name IS 'Human-readable Part name. Enables semantic grouping of labs across code vintages/methods (e.g. all HbA1c components regardless of method).';

-- protocol_edges: the care-protocol knowledge graph as subject-predicate-object triples (drug-class recommendations).
COMMENT ON COLUMN {catalog}.care_protocol_terminology.protocol_edges.subject IS 'Subject of a care-protocol edge, typically a drug class (e.g. DRUGCLASS-STATIN, DRUGCLASS-SGLT2, DRUGCLASS-ACE).';
COMMENT ON COLUMN {catalog}.care_protocol_terminology.protocol_edges.predicate IS 'Edge relationship: recommendedFor, firstLineFor, contraindicatedWith, or contraindicatedWhen.';
COMMENT ON COLUMN {catalog}.care_protocol_terminology.protocol_edges.object IS 'Object of the edge: a measure, condition, comorbidity, or contraindication (e.g. SPD, ALBUMINURIA, COMORBID_CKD, CONTRA_PREGNANCY, eGFR_LT_30).';
COMMENT ON COLUMN {catalog}.care_protocol_terminology.protocol_edges.value IS 'Optional numeric threshold attached to the edge (e.g. 30 for eGFR_LT_30); null when not applicable.';
COMMENT ON COLUMN {catalog}.care_protocol_terminology.protocol_edges.source IS 'Citation into the care-protocol document (section/version, e.g. CP-DM-2025.1 sec2). Record-level provenance for the recommendation.';
