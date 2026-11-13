---
document_id: CSL-A-SAP-v1.0
title: "CSL-A Statistical Analysis Plan, version 1.0"
study_id: CSL-A
doc_type: SAP
version: "1.0"
status: APPROVED
effective_date: "2025-01-15"
approval: "demo-fixture (seeded; no real human approval)"
access: "study:CSL-A"
---
# CSL-A Statistical Analysis Plan, version 1.0

SYNTHETIC DOCUMENT. Illustrative only; not a real trial. Results produced under this plan are descriptive and
synthetic; they are not evidence of efficacy.

## 9 Analysis of the primary endpoint

### 9.4 Derivations

#### 9.4.1 Percent change in body weight from baseline to Week 24

Reference date. The reference date is the date of the first dose of study treatment (CSL-101 or placebo). If the
first-dose date is incomplete, no endpoint is derived.

Study day. Study day is the date minus the reference date, plus one for dates on or after the reference date.
There is no study day 0.

Baseline. The baseline is the last valid body weight from study day -28 to study day -1, inclusive. A weight on
study day 1 counts as baseline only if it is recorded with a time before the first dose; a day-1 weight without a
time, or after the dose, is not used.

Week 24 target date. The target date is the reference date plus 168 days (study day 169).

Analysis window. A follow-up weight qualifies if its date is within ±7 days of the target date, inclusive. The
visit label does not matter; the date does.

Selection. The qualifying weight closest to the target date is used. If two are equally close, the later date is
used; if still tied, the lower record sequence number is used.

Valid values. A weight is valid if it is numeric, greater than zero, and recorded in kg, LB or g (converted to kg
with 1 lb = 0.45359237 kg). Records marked not done, with a missing result, a missing unit or any other unit are
not used. A record repeated with the same date and time, value and unit is counted once.

Missing data. If there is no valid baseline or no qualifying follow-up weight, no percent change is derived for
the participant. Values are not imputed.

Formula. Percent change = 100 × (follow-up weight − baseline weight) / baseline weight. The analysis value is
stored unrounded; it is rounded to one decimal place only for display.

### 9.5 Analysis populations

The full analysis set (FAS) is all randomized participants who received at least one dose of study treatment. The
per-protocol set (PPS) is the FAS minus participants with a major protocol deviation: an eligibility violation at
the applicable protocol version, or a prohibited medication started or taken during treatment.

### 9.6 Intercurrent events

Use of a GLP-1 receptor agonist during treatment is an intercurrent event. The FAS analysis uses observed weights
regardless (treatment-policy strategy); the PPS excludes these participants.
