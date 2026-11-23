-- Life-sciences benchmark gold (docs/benchmark/ls_questions.yaml): the answer key for the locked LS questions.
-- Same format and gate as gold_queries.sql (HEDIS):
--   DATABRICKS_CONFIG_PROFILE=ECT python src/benchmark/verify_gold.py --warehouse_id <WH> --gold src/benchmark/ls_gold_queries.sql
-- `-- holdout:` = an answer key no approach may hold in its context (never in a Genie space, Page, saved query or
-- the corpus). The data cutoff is 2026-10-31; every query filters on it explicitly. Each query is written from the
-- protocol / SAP / registry text over the standardized (silver) data and the vendored closures; where the question
-- is about the governed result itself (lq1, lq2), it reads gold_endpoint_result, which ls_audit_endpoint.py checks
-- independently against the SAP.

-- @id: lq1_wt24_by_arm
-- class: ls_bench  min_approach: metric_view  expect: CSL101:-12.66,PBO:-2.31
-- holdout: LS benchmark question 1
-- Mean percent change in body weight, baseline to Week 24, CSL-A full analysis set, rule EP-A-WT24.R2 (SAP v2.0),
-- by arm, Week 24 weights dated on or before 2026-10-31.
SELECT array_join(array_sort(collect_list(concat(ARMCD, ':', format_number(m, 2)))), ',') AS mean_pchg_by_arm
FROM (SELECT p.ARMCD, avg(r.PCHG) AS m
      FROM {catalog}.clinical_study.gold_endpoint_result r
      JOIN {catalog}.clinical_study.gold_participant_population p USING (USUBJID)
      JOIN {catalog}.clinical_study.silver_vs v ON v.CPL_OBS_ID = r.followup_observation_id
      WHERE r.endpoint_version = 'EP-A-WT24.R2' AND r.result_status = 'DERIVED' AND p.FASFL = 'Y'
        AND to_date(v.VSDTC) <= DATE'2026-10-31'
      GROUP BY p.ARMCD);

-- @id: lq2_wt24_bmi35_by_arm
-- class: ls_bench  min_approach: closure_sql  expect: CSL101:-12.66,PBO:-2.31
-- holdout: LS benchmark question 2
-- Same endpoint (EP-A-WT24.R2, CSL-A FAS) for participants whose baseline BMI is 35 or more: the endpoint's baseline
-- weight (kg) over the screening height (m) squared. BMI is not a column anywhere; it has to be computed.
SELECT array_join(array_sort(collect_list(concat(ARMCD, ':', format_number(m, 2)))), ',') AS mean_pchg_by_arm
FROM (SELECT p.ARMCD, avg(r.PCHG) AS m
      FROM {catalog}.clinical_study.gold_endpoint_result r
      JOIN {catalog}.clinical_study.gold_participant_population p USING (USUBJID)
      JOIN {catalog}.clinical_study.silver_vs v ON v.CPL_OBS_ID = r.followup_observation_id
      JOIN (SELECT USUBJID, max(VSSTRESN) / 100 AS m_height FROM {catalog}.clinical_study.silver_vs
            WHERE VSTESTCD = 'HEIGHT' AND VISIT = 'SCREENING' AND VSSTRESN > 0 GROUP BY USUBJID) h USING (USUBJID)
      WHERE r.endpoint_version = 'EP-A-WT24.R2' AND r.result_status = 'DERIVED' AND p.FASFL = 'Y'
        AND to_date(v.VSDTC) <= DATE'2026-10-31' AND r.BASE / power(h.m_height, 2) >= 35
      GROUP BY p.ARMCD);

-- @id: lq3_wrc_v1_randomized
-- class: ls_bench  min_approach: closure_sql  expect: 0
-- holdout: LS benchmark question 3
-- Randomized CSL-A participants with at least one weight-related comorbidity as protocol 1.0 section 5.1 defines it
-- (any MH term at or below a WRC-V1 root and not at or below a carve-out root; MONDO closure includes the root).
WITH roots AS (SELECT concept_id, kind FROM {catalog}.clinical_study_standards.class_root WHERE class_id = 'WRC-V1'),
wrc AS (SELECT c.descendant_code AS code FROM {catalog}.clinical_study_standards.mondo_closure c
        JOIN roots r ON r.concept_id = c.ancestor_code AND r.kind = 'root'
        EXCEPT
        SELECT c.descendant_code FROM {catalog}.clinical_study_standards.mondo_closure c
        JOIN roots r ON r.concept_id = c.ancestor_code AND r.kind = 'exclude_root')
SELECT count(DISTINCT dm.USUBJID) AS n
FROM {catalog}.clinical_study.silver_dm dm
JOIN {catalog}.clinical_study.silver_mh mh USING (USUBJID)
JOIN wrc ON wrc.code = mh.CPL_MONDO_ID
WHERE dm.STUDYID = 'CSL-A' AND dm.CPL_RANDDT IS NOT NULL AND to_date(dm.CPL_RANDDT) <= DATE'2026-10-31';

-- @id: lq6_prohibited_on_treatment_by_arm
-- class: ls_bench  min_approach: closure_sql  expect: CSL101:0,PBO:0
-- holdout: LS benchmark question 6
-- CSL-A dosed participants who started a prohibited medication on treatment (protocol section 6: a GLP-1 receptor
-- agonist class member, or a drug whose MED-RT physiologic effect is Appetite Suppression), started on or after the
-- first dose and on or before 2026-10-31, by arm.
WITH glp1 AS (SELECT descendant_code AS cls FROM {catalog}.clinical_study_standards.medrt_class_closure
              WHERE ancestor_code = 'MEDRT:N0000178480'),
prohib AS (SELECT DISTINCT subject AS rx FROM {catalog}.clinical_study_standards.kb_edge
           WHERE (predicate = 'medrt:memberOf' AND object IN (SELECT cls FROM glp1))
              OR (predicate = 'medrt:has_PE' AND object = 'MEDRT:N0000175372')),
first_dose AS (SELECT USUBJID, to_date(min(EXSTDTC)) AS d FROM {catalog}.clinical_study.silver_ex
               WHERE STUDYID = 'CSL-A' AND EXDOSE >= 0 GROUP BY USUBJID),
hit AS (SELECT DISTINCT cm.USUBJID FROM {catalog}.clinical_study.silver_cm cm
        JOIN prohib ON prohib.rx = cm.CPL_RXNORM_ID JOIN first_dose f USING (USUBJID)
        WHERE length(cm.CMSTDTC) >= 10 AND to_date(left(cm.CMSTDTC, 10)) >= f.d
          AND to_date(left(cm.CMSTDTC, 10)) <= DATE'2026-10-31')
SELECT array_join(array_sort(collect_list(concat(ARMCD, ':', n))), ',') AS participants_by_arm
FROM (SELECT dm.ARMCD, count(DISTINCT hit.USUBJID) AS n FROM {catalog}.clinical_study.silver_dm dm
      JOIN first_dose USING (USUBJID) LEFT JOIN hit USING (USUBJID) WHERE dm.STUDYID = 'CSL-A' GROUP BY dm.ARMCD);

-- @id: lq8_osa_only_qualified
-- class: ls_bench  min_approach: closure_sql  expect: 0
-- holdout: LS benchmark question 8
-- CSL-A participants screened from 2025-10-27 (Amendment 1) who met the BMI inclusion criterion only because
-- obstructive sleep apnea was added: BMI 27 to < 30 at screening, an MH term at or below OSA (MONDO:0007147), and no term in
-- WRC-V1 (protocol 1.0 list minus carve-outs). Screening weight (kg) over screening height (m) squared; if no valid
-- screening weight, the earliest valid pre-dose weight (protocol 5.1 criterion 2).
WITH roots AS (SELECT concept_id, kind FROM {catalog}.clinical_study_standards.class_root WHERE class_id = 'WRC-V1'),
wrc1 AS (SELECT c.descendant_code AS code FROM {catalog}.clinical_study_standards.mondo_closure c
         JOIN roots r ON r.concept_id = c.ancestor_code AND r.kind = 'root'
         EXCEPT
         SELECT c.descendant_code FROM {catalog}.clinical_study_standards.mondo_closure c
         JOIN roots r ON r.concept_id = c.ancestor_code AND r.kind = 'exclude_root'),
osa AS (SELECT descendant_code AS code FROM {catalog}.clinical_study_standards.mondo_closure
        WHERE ancestor_code = 'MONDO:0007147'),
w AS (SELECT v.USUBJID, v.VISIT, v.VSTESTCD, v.VSSTRESN, to_timestamp(v.VSDTC) AS ts, d.RFXSTDTC
      FROM {catalog}.clinical_study.silver_vs v JOIN {catalog}.clinical_study.silver_dm d USING (USUBJID)
      WHERE d.STUDYID = 'CSL-A' AND v.VSSTRESN > 0 AND v.VSTESTCD IN ('WEIGHT', 'HEIGHT')),
bmi AS (SELECT USUBJID,
               coalesce(max(CASE WHEN VSTESTCD = 'WEIGHT' AND VISIT = 'SCREENING' THEN VSSTRESN END),
                        min_by(CASE WHEN VSTESTCD = 'WEIGHT' THEN VSSTRESN END,
                               CASE WHEN VSTESTCD = 'WEIGHT' AND (RFXSTDTC IS NULL OR ts < to_timestamp(RFXSTDTC))
                                    THEN ts END))
               / power(max(CASE WHEN VSTESTCD = 'HEIGHT' AND VISIT = 'SCREENING' THEN VSSTRESN END) / 100, 2) AS bmi
        FROM w GROUP BY USUBJID)
SELECT count(*) AS n FROM {catalog}.clinical_study.silver_dm dm JOIN bmi USING (USUBJID)
WHERE dm.STUDYID = 'CSL-A' AND to_date(dm.DMDTC) >= DATE'2025-10-27' AND to_date(dm.DMDTC) <= DATE'2026-10-31'
  AND bmi.bmi >= 27 AND bmi.bmi < 30
  AND EXISTS (SELECT 1 FROM {catalog}.clinical_study.silver_mh mh JOIN osa ON osa.code = mh.CPL_MONDO_ID
              WHERE mh.USUBJID = dm.USUBJID)
  AND NOT EXISTS (SELECT 1 FROM {catalog}.clinical_study.silver_mh mh JOIN wrc1 ON wrc1.code = mh.CPL_MONDO_ID
                  WHERE mh.USUBJID = dm.USUBJID);
