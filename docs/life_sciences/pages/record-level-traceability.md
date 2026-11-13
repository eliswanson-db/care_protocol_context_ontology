---
name: Record-level traceability
synonyms: [provenance, lineage, trace, source record, execution run, why was this observation excluded, which records contributed]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.clinical_study.gold_provenance_edge
  - eli_test_classic_catalog.clinical_study.gold_endpoint_candidate
  - eli_test_classic_catalog.clinical_study.gold_tracer_registry
---

Every endpoint result can be walked back: **result** → baseline and follow-up **observations**
(`baseline_observation_id`, `followup_observation_id`) → **raw EDC source records** (`CPL_SOURCE_RECORD_ID`,
`CPL_SOURCE_FILE`) and forward to the **rule version** → **document section** that states it, and the
**execution run** (content-addressed: the same rules, standards and data give the same run id).

To explain an exclusion, read `gold_endpoint_candidate` for the participant and rule version: every observation has
a role (BASELINE/FOLLOWUP), decision (SELECTED / ELIGIBLE_NOT_SELECTED / EXCLUDED), reason and days from target.

`gold_tracer_registry` lists 29 named participants: 20 endpoint edge cases (EDGE-01 … EDGE-20) and 9 eligibility
cases (ELIG-E1 … E9). Their expected outcomes were worked out by hand and are checked after every run
(`gold_verification_run`).
