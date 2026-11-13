---
name: Protocol amendments (CSL-A)
synonyms: [amendment 1, amendment 2, amendment 3, protocol version, window change, ±14 days, obstructive sleep apnea, draft amendment, amendment impact]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.clinical_study_standards.study_version
  - eli_test_classic_catalog.clinical_study.gold_amendment_impact
  - eli_test_classic_catalog.clinical_study.rule_assertion
---

| Protocol | Effective | Change | Executable rule |
|---|---|---|---|
| 1.0 | 2025-01-15 | original | EP-A-WT24.R1, ELIG-A-V1 |
| 2.0 (Amendment 1) | 2025-09-01 | Week 24 analysis window ±7 → **±14 days**; nothing else | EP-A-WT24.R2 |
| 3.0 (Amendment 2) | 2025-11-01 | **obstructive sleep apnea** added to weight-related comorbidities for screening on/after the effective date (central sleep apnea not added) | ELIG-A-V2 |
| Amendment 3 | none | **DRAFT memo** proposing ±21 days. **Not approved. Never executed.** | none |

**Reading amendment impact** (`gold_amendment_impact`, R1 → R2): one row per participant with
`endpoint_became_derivable`, `selected_followup_changed`, `eligible_candidates_changed`,
`endpoint_value_changed` and an explanation. Most recovered participants were at one site whose Week 24 visits ran
8 to 13 days late. A participant can gain an eligible candidate without the selected record changing (closest still
wins).

**Eligibility is decided at screening.** Amendment 2 does not re-qualify participants who screened before
2025-11-01.
