---
page: pages/2917aa8e-38e0-48a0-90b5-040c2931541a
title: "KED (Kidney Health Evaluation)"
state: PUBLISHED
updated: 2026-10-30T15:36:01.337Z
synonyms: ["KED", "Kidney Health Evaluation for Patients With Diabetes", "diabetic kidney screening", "kidney health evaluation", "nephropathy screening"]
description: "Share of diabetic patients aged 18\u201385 with BOTH an eGFR and a uACR test in the year; uACR is the limiting component."
---
## Definition
HEDIS measure of kidney-health evaluation in patients with diabetes. Its numerator is **compound**: it requires two different lab tests in the same year.

## Measure specification
* **Denominator:** **Diabetes Cohort**, aged **18–85** at the end of the measurement year.
* **Numerator:** **both** an **eGFR** test and a **uACR** test in the measurement year. Missing either one is a care gap.
* **Value sets:** `KED_EGFR`, `KED_UACR`

## Data
* **Metrics** in `ked_compliance_metrics`: `KED Compliance Rate` (combined), `eGFR Test Rate`, `uACR Test Rate`
* **Patient-level detail:** `gold_adherence_ked` (`egfr_flag`, `uacr_flag`)

## Examples
Demo rates: eGFR \~92%, uACR \~51%, combined \~51%. The combined rate tracks uACR.

---
_KED is the worked example for Measure Drift (eGFR code versions). HEDIS-aligned demo, not NCQA-certified._
