---
name: Endpoint definitions (Week 24 weight change)
synonyms: [primary endpoint, EP-A-WT24, EP-B-WT24, percent change in body weight, PCHG, WTPCHG24, Week 24]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.clinical_study_standards.rule_version
  - eli_test_classic_catalog.clinical_study.gold_endpoint_result
---

**Percent change in body weight from baseline to Week 24** = 100 × (follow-up kg − baseline kg) / baseline kg.
Negative means weight loss. `PCHG` is stored unrounded; `PCHG_DISPLAY` is rounded to one decimal for display.

| Rule version | Study | Protocol / SAP | Baseline | Target | Window | Tie-breaker | Source |
|---|---|---|---|---|---|---|---|
| EP-A-WT24.R1 | CSL-A | 1.0 / 1.0 | last valid, day −28 to −1 (+ day 1 if timed pre-dose) | reference + 168 d | ±7 d | later date, lower seq | CSL-A SAP v1.0 §9.4.1 |
| EP-A-WT24.R2 | CSL-A | 2.0 / 2.0 | same as R1 | reference + 168 d | **±14 d** | later date, lower seq | CSL-A SAP v2.0 §9.4.1 |
| EP-B-WT24.R1 | CSL-B | 1.0 / 1.0 | **mean** of valid, day −14 to −1 (no day 1) | reference + **167** d | ±10 d | **earlier** date, lower seq | CSL-B SAP v1.0 §8.3 |

Result statuses: DERIVED, NO_VALID_BASELINE, NO_QUALIFYING_FOLLOWUP, NO_REFERENCE_DATE, NOT_IN_POPULATION. A
participant without a valid baseline or qualifying follow-up has **no** derived value (no imputation).
Population: FAS. Always state the rule version with any number.
