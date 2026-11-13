---
name: Baseline and visit-window rules
synonyms: [baseline window, analysis window, visit window, closest to target, tie-breaker, same-day pre-dose, unscheduled visit, scheduling window]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.clinical_study.gold_endpoint_candidate
---

- **Dates decide, labels don't.** A visit labeled WEEK 24 outside the analysis window does not qualify; an
  unscheduled visit inside it does.
- **Windows are inclusive** (CSL-A R1: a weight exactly 7 days from the target qualifies; 8 days does not).
- **Closest wins**; equal distance → CSL-A uses the **later** date, CSL-B the **earlier** date; then the lower
  record sequence.
- **Day-1 weights (CSL-A only):** count as baseline only when recorded with a time **before** the first dose. A
  day-1 weight without a time is ambiguous and excluded (SAME_DAY_NO_TIME); after the dose, SAME_DAY_POST_DOSE.
  CSL-B never uses day 1 (SAME_DAY_NOT_ALLOWED).
- **Scheduling windows are not analysis windows.** The protocol's schedule (for example WEEK 24 at study days
  162 to 176 in CSL-A) is for booking visits. Assertions extracted from it are reviewed as *rejected* (not a rule).

Exclusion reasons on candidates: OUTSIDE_BASELINE_WINDOW, OUTSIDE_FOLLOWUP_WINDOW, DUPLICATE_RECORD, NOT_DONE,
MISSING_RESULT, MISSING_UNIT, UNSUPPORTED_UNIT, NONPOSITIVE_VALUE, MISSING_OR_PARTIAL_DATE. Eligible-but-not-chosen
candidates show BASELINE_NOT_LAST, FOLLOWUP_NOT_CLOSEST or FOLLOWUP_TIE_LOST.
