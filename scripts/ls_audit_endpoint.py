"""Independent check of the Week 24 endpoint engine: re-derive every result in plain SQL from the SAP text alone
and compare it, participant by participant, with gold_endpoint_result. Read-only.

The HEDIS counterpart is gold_queries.sql (fixed-shape SQL as the answer key for the pipeline). This SQL was written
from the SAP sections, not from src/clinical_study/engine.py, so the two derivations can disagree:
  * CSL-A SAP 9.4.1 (v1.0: +/-7 days; v2.0: +/-14 days) and CSL-B SAP 8.3 (+/-10 days).
  * Reference date: first dose (earliest EX record; placebo is EXDOSE 0). Study day: no day 0.
  * Valid weight: WEIGHT, not NOT DONE, numeric > 0, unit kg / LB / g; a repeat with the same date-time, value and
    unit counted once.
  * Baseline: CSL-A the last valid weight on study days -28..-1, or on day 1 if timed before the first dose;
    CSL-B the mean of valid weights on days -14..-1.
  * Follow-up: closest valid weight to the target date (A: ref + 168, B: ref + 167) within the window; ties: A the
    later date, B the earlier date, then the lower VSSEQ.
  * Population: the full analysis set.

    .venv/bin/python -I scripts/ls_audit_endpoint.py          # prints the comparison; exits 1 on any mismatch
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
C = "eli_test_classic_catalog.clinical_study"
VERSIONS = {  # endpoint_version: (study, target offset, half width, baseline days, baseline method, tie order)
    "EP-A-WT24.R1": ("CSL-A", 168, 7, (-28, -1), "last", "DESC"),
    "EP-A-WT24.R2": ("CSL-A", 168, 14, (-28, -1), "last", "DESC"),
    "EP-B-WT24.R1": ("CSL-B", 167, 10, (-14, -1), "mean", "ASC"),
}


def _q():
    spec = importlib.util.spec_from_file_location("q", ROOT / "scripts/q.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.run


def derive_sql(ev: str) -> str:
    study, off, hw, (b0, b1), method, tie = VERSIONS[ev]
    if method == "last":
        base = f"""base AS (SELECT USUBJID, CPL_OBS_ID AS base_obs, kg AS BASE FROM (
                     SELECT w.*, row_number() OVER (PARTITION BY w.USUBJID ORDER BY w.ts DESC, w.VSSEQ) AS rn
                     FROM w JOIN ref USING (USUBJID)
                     WHERE w.sd BETWEEN {b0} AND {b1}
                        OR (w.sd = 1 AND w.has_time AND w.ts < ref.first_dose_ts)) WHERE rn = 1)"""
    else:
        base = f"""base AS (SELECT USUBJID, CAST(NULL AS STRING) AS base_obs, avg(kg) AS BASE FROM w
                     WHERE sd BETWEEN {b0} AND {b1} GROUP BY USUBJID)"""
    return f"""
    WITH ref AS (
      SELECT USUBJID, min(to_timestamp(EXSTDTC)) AS first_dose_ts, to_date(min(EXSTDTC)) AS ref_date
      FROM {C}.silver_ex WHERE STUDYID = '{study}' AND EXDOSE >= 0 AND length(EXSTDTC) >= 10 GROUP BY USUBJID),
    raw AS (
      SELECT v.USUBJID, v.VSSEQ, v.CPL_OBS_ID, v.VSDTC, v.VSORRES, v.VSORRESU,
             to_timestamp(v.VSDTC) AS ts, v.VSDTC LIKE '%T%' AS has_time, to_date(v.VSDTC) AS d,
             try_cast(v.VSORRES AS DOUBLE) * CASE v.VSORRESU WHEN 'kg' THEN 1.0 WHEN 'LB' THEN 0.45359237
                                                 WHEN 'g' THEN 0.001 END AS kg
      FROM {C}.silver_vs v
      WHERE v.STUDYID = '{study}' AND v.VSTESTCD = 'WEIGHT' AND coalesce(v.VSSTAT, '') <> 'NOT DONE'
        AND length(v.VSDTC) >= 10),
    w AS (
      SELECT r.*, CASE WHEN r.d >= ref.ref_date THEN datediff(r.d, ref.ref_date) + 1
                       ELSE datediff(r.d, ref.ref_date) END AS sd
      FROM (SELECT *, row_number() OVER (PARTITION BY USUBJID, VSDTC, VSORRES, VSORRESU ORDER BY VSSEQ) AS dup
            FROM raw WHERE kg > 0) r JOIN ref USING (USUBJID) WHERE r.dup = 1),
    {base},
    fu AS (SELECT USUBJID, CPL_OBS_ID AS fu_obs, kg AS AVAL_FU FROM (
             SELECT w.*, row_number() OVER (PARTITION BY w.USUBJID
                      ORDER BY abs(datediff(w.d, date_add(ref.ref_date, {off}))), w.d {tie}, w.VSSEQ) AS rn
             FROM w JOIN ref USING (USUBJID)
             WHERE abs(datediff(w.d, date_add(ref.ref_date, {off}))) <= {hw}) WHERE rn = 1),
    fas AS (SELECT USUBJID FROM {C}.gold_participant_population WHERE STUDYID = '{study}' AND FASFL = 'Y'),
    mine AS (
      SELECT fas.USUBJID, base.base_obs, fu.fu_obs, base.BASE, fu.AVAL_FU,
             100 * (fu.AVAL_FU - base.BASE) / base.BASE AS PCHG
      FROM fas LEFT JOIN base USING (USUBJID) LEFT JOIN fu USING (USUBJID)
      WHERE base.BASE IS NOT NULL AND fu.AVAL_FU IS NOT NULL),
    eng AS (SELECT USUBJID, baseline_observation_id, followup_observation_id, BASE, AVAL_FU, PCHG
            FROM {C}.gold_endpoint_result WHERE endpoint_version = '{ev}' AND result_status = 'DERIVED')
    SELECT
      count_if(mine.USUBJID IS NOT NULL) AS audit_derived,
      count_if(eng.USUBJID IS NOT NULL) AS engine_derived,
      count_if(mine.USUBJID IS NULL) AS engine_only,
      count_if(eng.USUBJID IS NULL) AS audit_only,
      count_if(mine.USUBJID IS NOT NULL AND eng.USUBJID IS NOT NULL
               AND (mine.fu_obs <> eng.followup_observation_id
                    OR (mine.base_obs IS NOT NULL AND mine.base_obs <> eng.baseline_observation_id))) AS obs_diff,
      count_if(abs(mine.PCHG - eng.PCHG) > 1e-6 OR abs(mine.BASE - eng.BASE) > 1e-6) AS value_diff,
      round(avg(mine.PCHG), 4) AS audit_mean_pchg,
      concat_ws(',', slice(collect_list(CASE WHEN mine.USUBJID IS NULL OR eng.USUBJID IS NULL
                OR mine.fu_obs <> eng.followup_observation_id OR abs(mine.PCHG - eng.PCHG) > 1e-6
                OR (mine.base_obs IS NOT NULL AND mine.base_obs <> eng.baseline_observation_id)
                THEN coalesce(mine.USUBJID, eng.USUBJID) END), 1, 5)) AS examples
    FROM mine FULL OUTER JOIN eng USING (USUBJID)"""


def main() -> None:
    run = _q()
    bad = 0
    for ev in VERSIONS:
        r = run(derive_sql(ev))[0]
        ok = all(int(r[k]) == 0 for k in ("engine_only", "audit_only", "obs_diff", "value_diff"))
        bad += not ok
        print(f"{'ok  ' if ok else 'DIFF'} {ev}: {r}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
