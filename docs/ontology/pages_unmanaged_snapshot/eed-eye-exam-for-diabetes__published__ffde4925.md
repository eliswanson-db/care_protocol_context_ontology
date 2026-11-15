---
page: pages/ffde4925-9200-4d93-96bc-7f1cb5cb860e
title: "EED (Eye Exam for Diabetes)"
state: PUBLISHED
updated: 2026-10-30T15:36:21.628Z
synonyms: ["EED", "Eye Exam for Patients With Diabetes", "diabetic eye exam", "diabetic retinopathy screening", "dilated eye exam", "retinal exam", "retinal screening"]
description: "Share of diabetic patients aged 18\u201375 with a retinal eye exam in the year; the only procedure-based (SNOMED) measure."
---
## Definition
HEDIS measure of diabetic retinal screening, which catches diabetic retinopathy early.

## Measure specification
* **Denominator:** **Diabetes Cohort**, aged **18–75** at the end of the measurement year.
* **Numerator:** a retinal / diabetic eye exam during the measurement year.
* **Value set:** `EED_EYE_EXAM` (SNOMED procedure codes, e.g. `722161008` *Diabetic retinal eye exam*, `700070005` *Optical coherence tomography of retina*)

## Data
* **Metric view:** `eed_compliance_metrics`
* **Patient-level detail:** `gold_adherence_eed`, sourced from `silver_procedure` (EED is the only measure built on procedures rather than labs, diagnoses, or medications)

---
_Full HEDIS also credits a negative retinal screen in the prior year; this demo uses only the measurement year. SNOMED codes come from synthetic data; no licensed SNOMED hierarchy is shipped. HEDIS-aligned demo, not NCQA-certified._
