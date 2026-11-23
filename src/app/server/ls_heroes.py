"""Life-sciences hero participants, picked from the generated data by stated rules (the HEDIS pattern,
server/traces.py). Each rule takes the lowest USUBJID that qualifies, so a regeneration keeps the pick meaningful
and nobody chooses a participant by hand. The hand-authored test participants (FX-*) are never in the demo data.
"""

from __future__ import annotations

from .config import CATALOG

CS = f"{CATALOG}.clinical_study"

HEROES: list[dict] = [
    {"id": "amd1_recovered", "title": "Recovered by Amendment 1",
     "rule": "lowest USUBJID at SITE-118 with no Week 24 result under EP-A-WT24.R1 and a derived one under R2",
     "sql": f"""SELECT min(p.USUBJID) AS u FROM {CS}.gold_participant_population p
                JOIN {CS}.gold_endpoint_result r1 ON r1.USUBJID = p.USUBJID AND r1.endpoint_version = 'EP-A-WT24.R1'
                JOIN {CS}.gold_endpoint_result r2 ON r2.USUBJID = p.USUBJID AND r2.endpoint_version = 'EP-A-WT24.R2'
                WHERE p.SITEID = 'SITE-118' AND r1.result_status <> 'DERIVED' AND r2.result_status = 'DERIVED'"""},
    {"id": "lb_weight", "title": "Weight keyed in pounds",
     "rule": "lowest USUBJID whose derived Week 24 result uses a weight keyed in lb at the site",
     "sql": f"""SELECT min(v.USUBJID) AS u FROM {CS}.silver_vs v JOIN {CS}.gold_endpoint_result r
                ON r.USUBJID = v.USUBJID AND r.result_status = 'DERIVED'
                AND v.CPL_OBS_ID IN (r.followup_observation_id, r.baseline_observation_id)
                WHERE v.CPL_RAW_UNIT = 'lb'"""},
    {"id": "placebo_glp1", "title": "Placebo participant who started a GLP-1",
     "rule": "lowest placebo USUBJID with a PROHIBITED_MEDICATION_ON_TREATMENT major deviation",
     "sql": f"""SELECT min(USUBJID) AS u FROM {CS}.gold_participant_population WHERE ARMCD = 'PBO'
                AND exists(deviations, d -> d.deviation = 'PROHIBITED_MEDICATION_ON_TREATMENT')"""},
    {"id": "mh_hierarchy_exclusion", "title": "Excluded through the disease hierarchy",
     "rule": "lowest USUBJID excluded by EXC-MH whose coded history term sits below the excluded MONDO root",
     "sql": f"""SELECT min(USUBJID) AS u FROM {CS}.gold_eligibility_criterion
                WHERE criterion_id = 'EXC-MH' AND outcome = 'TRIGGERED' AND size(path) >= 2"""},
    {"id": "enrolled_in_error", "title": "Enrolled in error",
     "rule": "lowest randomized USUBJID that the EDC marked eligible but the eligibility rules exclude",
     "sql": f"""SELECT min(USUBJID) AS u FROM {CS}.gold_participant_population
                WHERE edc_eligible = 'Y' AND NOT rule_eligible AND randomized"""},
]
