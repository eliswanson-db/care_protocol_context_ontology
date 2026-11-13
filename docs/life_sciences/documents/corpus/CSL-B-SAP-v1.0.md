---
document_id: CSL-B-SAP-v1.0
title: "CSL-B Statistical Analysis Plan, version 1.0"
study_id: CSL-B
doc_type: SAP
version: "1.0"
status: APPROVED
effective_date: "2025-02-01"
approval: "demo-fixture (seeded; no real human approval)"
access: "study:CSL-B"
---
# CSL-B Statistical Analysis Plan, version 1.0

SYNTHETIC DOCUMENT. Illustrative only; not a real trial.

## 8 Endpoint derivations

### 8.3 Percent change in body weight from baseline to Week 24

Reference date and study day are as in CSL-A: the date of the first dose (CSL-101 or placebo); no study day 0.

Baseline. The baseline is the mean of all valid body weights from study day -14 to study day -1, inclusive. Weights
on study day 1 are not used, even if recorded before the dose.

Week 24 target date. The target date is the reference date plus 167 days (study day 168).

Analysis window. A follow-up weight qualifies if its date is within ±10 days of the target date, inclusive.

Selection. The qualifying weight closest to the target date is used. If two are equally close, the earlier date
is used; if still tied, the lower record sequence number is used.

Valid values, missing data and formula follow the same rules as CSL-A: kg, LB or g only; greater than zero;
duplicates counted once; no imputation; percent change = 100 × (follow-up − baseline) / baseline, stored unrounded.
The population is the full analysis set.
