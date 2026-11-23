---
name: Record-level traceability
synonyms: [provenance, lineage, trace, source record, execution run, why was this observation excluded, which records contributed]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.clinical_study.gold_provenance_edge
  - eli_test_classic_catalog.clinical_study.gold_endpoint_candidate
---

Every endpoint result can be walked back: **result** → baseline and follow-up **observations**
(`baseline_observation_id`, `followup_observation_id`) → **raw EDC source records** (`CPL_SOURCE_RECORD_ID`,
`CPL_SOURCE_FILE`) and forward to the **rule version** → **document section** that states it, and the
**execution run** (content-addressed: the same rules, standards and data give the same run id).

To explain an exclusion, read `gold_endpoint_candidate` for the participant and rule version: every observation has
a role (BASELINE/FOLLOWUP), decision (SELECTED / ELIGIBLE_NOT_SELECTED / EXCLUDED), reason and days from target.

After every run, `gold_verification_run` records the checks every correct run must pass: one result per
full-analysis-set participant and rule version, each derived value equals (follow-up − baseline) / baseline × 100,
each selected follow-up lies inside its rule version's window, and widening the window (Amendment 1) only adds
derivations.
