"""Independent check of the eligibility engine: re-derive each criterion in plain SQL from the protocol text and the
vendored closures, and compare it with gold_eligibility_criterion participant by participant. Read-only.

Written from the protocols (CSL-A v1.0 section 5 + Amendment 1, CSL-B v1.0 section 5) and the class roots in the
rule registry, not from src/clinical_study/eligibility.py:
  * INC-AGE: AGE at screening in [18, 75] (CSL-A) or [18, 80] (CSL-B).
  * INC-T2D (CSL-B): a medical-history term at or below type 2 diabetes mellitus (MONDO:0005148).
  * INC-BMI: BMI from the screening weight (kg; if none is valid, the earliest valid pre-dose weight) and height; CSL-A >= 30, or >= 27 with a weight-related
    comorbidity (WRC-V1; WRC-V2 adds obstructive sleep apnea for participants screened on or after the Amendment 1
    date), a term at or below a class root and not at or below an excluded root; CSL-B >= 27.
  * EXC-MH: a history term at or below an EXCL-MH-V1 root; CSL-B does not exclude diabetic retinopathy.
  * EXC-CM: a medication that is a GLP-1 RA class member or has the physiologic effect appetite suppression,
    taken within 90 days before screening (started on or before screening and not ended more than 90 days before).
  * EXC-CI: a history term whose MONDO concept or any MONDO ancestor maps to a MeSH record (exactMatch / xref /
    curated) whose MeSH ancestors include a record that a GLP-1 RA class member is CI_with (Drug Hypersensitivity
    excluded).

    .venv/bin/python -I scripts/ls_audit_eligibility.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
C = "eli_test_classic_catalog.clinical_study"
S = "eli_test_classic_catalog.clinical_study_standards"
AMD1 = "2025-10-27"


def _q():
    spec = importlib.util.spec_from_file_location("q", ROOT / "scripts/q.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.run


def _under(class_id: str, kind: str = "root") -> str:
    """MONDO codes at or below a class's roots (closure includes depth 0)."""
    return (f"SELECT c.descendant_code AS code FROM {S}.mondo_closure c JOIN {S}.class_root r "
            f"ON r.concept_id = c.ancestor_code WHERE r.class_id = '{class_id}' AND r.kind = '{kind}'")


SQL = f"""
WITH dm AS (SELECT USUBJID, STUDYID, AGE, to_date(DMDTC) AS scr FROM {C}.silver_dm),
mh AS (SELECT USUBJID, CPL_MONDO_ID AS code FROM {C}.silver_mh WHERE CPL_MONDO_ID IS NOT NULL),
wrc1 AS (SELECT code FROM ({_under('WRC-V1')}) EXCEPT SELECT code FROM ({_under('WRC-V1', 'exclude_root')})),
wrc2 AS (SELECT code FROM wrc1 UNION SELECT code FROM ({_under('WRC-V2')})
         EXCEPT SELECT code FROM ({_under('WRC-V1', 'exclude_root')})),
t2d AS (SELECT descendant_code AS code FROM {S}.mondo_closure WHERE ancestor_code = 'MONDO:0005148'),
dr AS (SELECT descendant_code AS code FROM {S}.mondo_closure WHERE ancestor_code = 'MONDO:0005266'),
excl AS ({_under('EXCL-MH-V1')}),
scr_vs AS (  -- screening weight; if none is valid, the earliest valid pre-dose weight (protocol 5.1 criterion 2)
  SELECT v.USUBJID,
         coalesce(max(CASE WHEN v.VSTESTCD = 'WEIGHT' AND v.VISIT = 'SCREENING' THEN v.VSSTRESN END),
                  max_by(CASE WHEN v.VSTESTCD = 'WEIGHT' AND (d.RFXSTDTC IS NULL OR v.VSDTC < d.RFXSTDTC)
                              THEN v.VSSTRESN END,
                         CASE WHEN v.VSTESTCD = 'WEIGHT' AND v.VSSTRESN > 0
                                   AND (d.RFXSTDTC IS NULL OR v.VSDTC < d.RFXSTDTC) THEN -unix_timestamp(
                                     to_timestamp(v.VSDTC)) END)) AS kg,
         max(CASE WHEN v.VSTESTCD = 'HEIGHT' AND v.VISIT = 'SCREENING' THEN v.VSSTRESN END) AS cm
  FROM {C}.silver_vs v JOIN {C}.silver_dm d USING (USUBJID) WHERE v.VSSTRESN > 0 GROUP BY v.USUBJID),
prohib AS (
  SELECT DISTINCT e.subject AS rx FROM {S}.kb_edge e
  WHERE (e.predicate = 'medrt:memberOf' AND e.object IN (
            SELECT descendant_code FROM {S}.medrt_class_closure WHERE ancestor_code = 'MEDRT:N0000178480'))
     OR (e.predicate = 'medrt:has_PE' AND e.object = 'MEDRT:N0000175372')),
cm AS (SELECT c.USUBJID FROM {C}.silver_cm c JOIN dm USING (USUBJID) JOIN prohib p ON p.rx = c.CPL_RXNORM_ID
       WHERE to_date(left(c.CMSTDTC, 10)) <= dm.scr
         AND (c.CMENDTC IS NULL OR length(c.CMENDTC) < 10 OR to_date(left(c.CMENDTC, 10)) >= date_sub(dm.scr, 90))),
glp1 AS (SELECT e.subject AS rx FROM {S}.kb_edge e WHERE e.predicate = 'medrt:memberOf' AND e.object IN (
           SELECT descendant_code FROM {S}.medrt_class_closure WHERE ancestor_code = 'MEDRT:N0000178480')),
ci_mesh AS (  -- MeSH descriptors a GLP-1 RA member is CI_with (concept -> descriptor), minus Drug Hypersensitivity
  SELECT DISTINCT coalesce(cc.object, e.object) AS mesh FROM {S}.kb_edge e JOIN glp1 g ON g.rx = e.subject
  LEFT JOIN {S}.kb_edge cc ON cc.subject = e.object AND cc.predicate = 'mesh:conceptOf'
  WHERE e.predicate = 'medrt:CI_with' AND coalesce(cc.object, e.object) <> 'MESH:D004342'),
mondo_mesh AS (
  SELECT subject AS mondo, object AS mesh FROM {S}.kb_edge
  WHERE predicate IN ('skos:exactMatch', 'oboInOwl:hasDbXref', 'cpl:curatedEquivalent') AND object LIKE 'MESH:%'
  UNION SELECT m.subject, h.object FROM {S}.kb_edge m JOIN {S}.kb_edge h
    ON h.subject = m.object AND h.predicate = 'mesh:headingMappedTo'
  WHERE m.predicate IN ('skos:exactMatch', 'oboInOwl:hasDbXref', 'cpl:curatedEquivalent') AND m.object LIKE 'MESH:%'),
ci AS (SELECT DISTINCT mh.USUBJID FROM mh
       JOIN {S}.mondo_closure up ON up.descendant_code = mh.code
       JOIN mondo_mesh mm ON mm.mondo = up.ancestor_code
       JOIN (SELECT descendant_code AS mesh, ancestor_code AS up FROM {S}.mesh_closure
             UNION SELECT mesh, mesh FROM mondo_mesh) mup ON mup.mesh = mm.mesh  -- supplementary records: self only
       JOIN ci_mesh x ON x.mesh = mup.up),
mine AS (
  SELECT USUBJID, 'INC-AGE' AS criterion_id,
         AGE BETWEEN 18 AND CASE STUDYID WHEN 'CSL-A' THEN 75 ELSE 80 END AS hit FROM dm
  UNION ALL SELECT USUBJID, 'INC-T2D', exists(SELECT 1 FROM mh JOIN t2d USING (code) WHERE mh.USUBJID = dm.USUBJID)
    FROM dm WHERE STUDYID = 'CSL-B'
  UNION ALL SELECT dm.USUBJID, 'INC-BMI',
    CASE WHEN dm.STUDYID = 'CSL-B' THEN bmi >= 27
         ELSE bmi >= 30 OR (bmi >= 27 AND (
           (dm.scr < DATE'{AMD1}' AND exists(SELECT 1 FROM mh JOIN wrc1 USING (code) WHERE mh.USUBJID = dm.USUBJID))
        OR (dm.scr >= DATE'{AMD1}' AND exists(SELECT 1 FROM mh JOIN wrc2 USING (code) WHERE mh.USUBJID = dm.USUBJID))))
    END
    FROM dm LEFT JOIN (SELECT USUBJID, kg / power(cm / 100, 2) AS bmi FROM scr_vs) b USING (USUBJID)
  UNION ALL SELECT USUBJID, 'EXC-MH', exists(
      SELECT 1 FROM mh JOIN excl USING (code) WHERE mh.USUBJID = dm.USUBJID
        AND NOT (dm.STUDYID = 'CSL-B' AND mh.code IN (SELECT code FROM dr))) FROM dm
  UNION ALL SELECT USUBJID, 'EXC-CM', USUBJID IN (SELECT USUBJID FROM cm) FROM dm
  UNION ALL SELECT USUBJID, 'EXC-CI', USUBJID IN (SELECT USUBJID FROM ci) FROM dm),
eng AS (SELECT USUBJID, criterion_id, outcome IN ('MET', 'TRIGGERED') AS hit, outcome
        FROM {C}.gold_eligibility_criterion)
SELECT criterion_id, count(*) AS n,
       count_if(mine.hit AND eng.hit) AS both_hit,
       count_if(coalesce(mine.hit, false) AND NOT eng.hit) AS audit_only,
       count_if(NOT coalesce(mine.hit, false) AND eng.hit) AS engine_only,
       concat_ws(',', slice(collect_list(CASE WHEN coalesce(mine.hit, false) <> eng.hit
                 THEN concat(USUBJID, ':', eng.outcome) END), 1, 4)) AS examples
FROM eng LEFT JOIN mine USING (USUBJID, criterion_id) GROUP BY criterion_id ORDER BY criterion_id
"""


def main() -> None:
    rows = _q()(SQL)
    bad = 0
    for r in rows:
        ok = int(r["audit_only"]) == 0 and int(r["engine_only"]) == 0
        bad += not ok
        print(f"{'ok  ' if ok else 'DIFF'} {r}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
