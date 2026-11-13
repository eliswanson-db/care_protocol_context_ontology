-- Semantic validation for the Clinical Study lab (applied by scripts/ls_apply_sql.py; ${catalog} substituted).
-- One row per violation in dq_semantic_validation; dq_semantic_validation_summary gives counts per check, INCLUDING
-- checks with zero violations, so "nothing found" is visible as 0 rather than as a missing row.
-- Severity ERROR = the model is inconsistent; WARNING = expected data-quality finding (e.g. a planted bad unit).
-- These run in UC rather than as SHACL because whether Ontobricks executes SHACL is unverified.

CREATE OR REPLACE VIEW ${catalog}.clinical_study.dq_semantic_validation
COMMENT 'Semantic validation findings (one row per violation). SYNTHETIC demo.' AS
-- 1. Derived results must carry provenance that resolves to real observations
SELECT 'RESULT_WITHOUT_PROVENANCE' AS check_id, 'ERROR' AS severity,
       concat(r.USUBJID, '.', r.endpoint_version) AS subject_id,
       concat('baseline=', coalesce(r.baseline_observation_id, 'NULL'), ' followup=',
              coalesce(r.followup_observation_id, 'NULL')) AS detail
FROM ${catalog}.clinical_study.gold_endpoint_result r
LEFT JOIN ${catalog}.clinical_study.silver_vs f ON f.CPL_OBS_ID = r.followup_observation_id
WHERE r.result_status = 'DERIVED'
  AND (r.baseline_observation_id IS NULL OR f.CPL_OBS_ID IS NULL OR r.PCHG IS NULL
       OR concat(r.USUBJID, '.', r.endpoint_version) IN (
          SELECT x.k FROM (SELECT concat(USUBJID, '.', endpoint_version) AS k,
                                  explode(split(baseline_observation_id, ',')) AS b
                           FROM ${catalog}.clinical_study.gold_endpoint_result
                           WHERE baseline_observation_id IS NOT NULL) x
          LEFT ANTI JOIN ${catalog}.clinical_study.silver_vs s ON s.CPL_OBS_ID = x.b))
UNION ALL
-- 2. Every result must come from an approved, fully versioned rule
SELECT 'UNVERSIONED_OR_UNAPPROVED_RULE', 'ERROR', concat(r.USUBJID, '.', r.endpoint_version),
       concat('rule ', r.endpoint_version, ' state=', coalesce(v.review_state, 'MISSING'))
FROM ${catalog}.clinical_study.gold_endpoint_result r
LEFT JOIN ${catalog}.clinical_study_standards.rule_version v ON v.endpoint_version = r.endpoint_version
WHERE v.endpoint_version IS NULL OR v.review_state <> 'approved' OR v.protocol_version IS NULL
   OR v.sap_version IS NULL OR r.execution_run_id IS NULL
UNION ALL
-- 3. Concept references must resolve in the KB
SELECT 'MISSING_CONCEPT_REFERENCE', 'ERROR', m.CPL_SOURCE_RECORD_ID, concat('MH code ', m.CPL_MONDO_ID)
FROM ${catalog}.clinical_study.silver_mh m
LEFT JOIN ${catalog}.clinical_study_standards.kb_concept k ON k.concept_id = m.CPL_MONDO_ID
WHERE k.concept_id IS NULL
UNION ALL
SELECT 'MISSING_CONCEPT_REFERENCE', 'ERROR', c.CPL_SOURCE_RECORD_ID, concat('CM code ', c.CPL_RXNORM_ID)
FROM ${catalog}.clinical_study.silver_cm c
LEFT JOIN ${catalog}.clinical_study_standards.kb_concept k ON k.concept_id = c.CPL_RXNORM_ID
WHERE k.concept_id IS NULL
UNION ALL
SELECT 'MISSING_CONCEPT_REFERENCE', 'ERROR', concat(r.class_id, ':', r.kind), concat('class root ', r.concept_id)
FROM ${catalog}.clinical_study_standards.class_root r
LEFT JOIN ${catalog}.clinical_study_standards.kb_concept k ON k.concept_id = r.concept_id
WHERE k.concept_id IS NULL
UNION ALL
SELECT 'MISSING_CONCEPT_REFERENCE', 'ERROR', t.endpoint_version, concat('endpoint concept ', t.ref)
FROM (SELECT endpoint_version, explode(array(biomedical_concept, dataset_specialization)) AS ref
      FROM ${catalog}.clinical_study_standards.rule_version) t
LEFT JOIN ${catalog}.clinical_study_standards.kb_concept k ON k.concept_id = t.ref
WHERE k.concept_id IS NULL
UNION ALL
-- 4. Variables a used dataset specialization constrains must exist in the physical SDTM-shaped table
SELECT 'INVALID_DATASET_VARIABLE', 'ERROR', b.subject, concat('DSS WEIGHT constrains ', b.object,
       ' which is not a column of silver_vs')
FROM ${catalog}.clinical_study_standards.kb_edge b
JOIN ${catalog}.clinical_study_standards.kb_edge h
  ON h.object = b.subject AND h.predicate = 'cosmos:hasVariableBinding' AND h.subject = 'COSMOS_DSS:WEIGHT'
WHERE b.predicate = 'cosmos:constrains'
  AND upper(element_at(split(b.object, '[.]'), 2)) NOT IN (
      SELECT upper(column_name) FROM ${catalog}.information_schema.columns
      WHERE table_schema = 'clinical_study' AND table_name = 'silver_vs')
UNION ALL
-- 5. Values must be allowed by the codelist / specialization
SELECT 'UNSUPPORTED_CODELIST_VALUE', 'WARNING', v.CPL_OBS_ID,
       concat('VSORRESU=', v.VSORRESU, ' not allowed by DSS WEIGHT (raw ', coalesce(v.CPL_RAW_UNIT, ''), ')')
FROM ${catalog}.clinical_study.silver_vs v
WHERE v.VSTESTCD = 'WEIGHT' AND v.VSORRESU IS NOT NULL
  AND v.VSORRESU NOT IN (
      SELECT k.notation FROM ${catalog}.clinical_study_standards.kb_edge e
      JOIN ${catalog}.clinical_study_standards.kb_concept k ON k.concept_id = e.object
      WHERE e.subject = 'COSMOS_DSSVAR:WEIGHT.VSORRESU' AND e.predicate = 'cosmos:allowedValue')
UNION ALL
SELECT 'UNSUPPORTED_CODELIST_VALUE', 'ERROR', concat('VSTESTCD=', t.VSTESTCD), 'test code not in CDISC CT C66741'
FROM (SELECT DISTINCT VSTESTCD FROM ${catalog}.clinical_study.silver_vs) t
WHERE t.VSTESTCD NOT IN (
    SELECT k.notation FROM ${catalog}.clinical_study_standards.kb_edge e
    JOIN ${catalog}.clinical_study_standards.kb_concept k ON k.concept_id = e.subject
    WHERE e.predicate = 'cdisc:inCodelist' AND e.object = 'CDISC_CT:C66741')
UNION ALL
-- 6. Every rule must cite a section that exists
SELECT 'RULE_WITHOUT_DOCUMENT_SECTION', 'ERROR', s.rule_id, concat(s.document_id, ' §', s.section)
FROM ${catalog}.clinical_study_standards.rule_document_support s
LEFT JOIN ${catalog}.clinical_study.doc_section d ON d.document_id = s.document_id AND d.section_number = s.section
WHERE d.section_id IS NULL
UNION ALL
-- 7. Approved assertions must agree with the rule they cite (document vs executable rule drift)
SELECT 'DOCUMENT_RULE_DISAGREEMENT', 'ERROR', a.assertion_id,
       concat(a.assertion_type, ' document=', a.value, ' rule=', a.rule_ref)
FROM ${catalog}.clinical_study.rule_assertion a
JOIN ${catalog}.clinical_study_standards.rule_version v ON v.endpoint_version = a.rule_ref
WHERE a.review_state = 'approved' AND NOT (
     (a.assertion_type = 'FOLLOWUP_WINDOW_HALF_WIDTH' AND a.value = cast(v.window_half_width_days AS string))
  OR (a.assertion_type = 'TARGET_OFFSET_DAYS' AND a.value = cast(v.target_offset_days AS string))
  OR (a.assertion_type = 'BASELINE_WINDOW'
      AND a.value = concat(v.baseline_window_start, ',', v.baseline_window_end))
  OR (a.assertion_type = 'BASELINE_METHOD' AND a.value = v.baseline_method)
  OR (a.assertion_type = 'TIE_BREAKER' AND a.value = element_at(split(element_at(split(v.tie_breaker, ','), 1), '_'), 1)));

CREATE OR REPLACE VIEW ${catalog}.clinical_study.dq_semantic_validation_summary
COMMENT 'Semantic validation counts per check (0 = checked and clean).' AS
SELECT c.check_id, c.severity, c.description, coalesce(n.n, 0) AS n_violations
FROM (SELECT * FROM VALUES
  ('RESULT_WITHOUT_PROVENANCE', 'ERROR', 'Derived result lacks resolvable baseline/follow-up observations'),
  ('UNVERSIONED_OR_UNAPPROVED_RULE', 'ERROR', 'Result from a rule that is missing, unapproved or unversioned'),
  ('MISSING_CONCEPT_REFERENCE', 'ERROR', 'MH/CM code, class root or endpoint concept not in the KB'),
  ('INVALID_DATASET_VARIABLE', 'ERROR', 'Specialization constrains a variable the physical table lacks'),
  ('UNSUPPORTED_CODELIST_VALUE', 'WARNING', 'Value not allowed by the codelist / dataset specialization'),
  ('RULE_WITHOUT_DOCUMENT_SECTION', 'ERROR', 'Rule cites a document section that does not exist'),
  ('DOCUMENT_RULE_DISAGREEMENT', 'ERROR', 'Approved document assertion disagrees with the executable rule')
  AS c(check_id, severity, description)) c
LEFT JOIN (SELECT check_id, count(*) AS n FROM ${catalog}.clinical_study.dq_semantic_validation GROUP BY check_id) n
  ON n.check_id = c.check_id;
