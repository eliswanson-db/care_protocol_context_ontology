---
page: pages/1045ab28-3390-4c2f-a056-381c1019c345
title: "GSD (Glycemic Status Assessment)"
state: PUBLISHED
updated: 2026-10-30T15:35:53.474Z
synonyms: ["A1c control measure", "GSD", "Glycemic Status Assessment for Patients With Diabetes", "HbA1c Control for Patients With Diabetes", "blood sugar control measure", "diabetes A1c testing"]
description: "Share of diabetic patients aged 18\u201375 with at least one HbA1c test in the measurement year; also bands A1c control."
---
## Definition
HEDIS measure of whether patients with diabetes had their glycemic status (**HbA1c**) assessed during the measurement year.

## Measure specification
* **Denominator:** **Diabetes Cohort**, aged **18–75** at the end of the measurement year.
* **Numerator:** at least one HbA1c test in the measurement year.
* **Value set:** `GSD_A1C_TEST`
* **Control bands (latest A1c):** good control **< 8%**, poor control **> 9%**.

## Data
* **Metric:** `GSD Compliance Rate` in `gsd_compliance_metrics`
* **Patient-level detail:** `gold_adherence_gsd` (MET / NOT_MET with test evidence)

---
_GSD replaces the older "HbA1c Control for Patients With Diabetes" framing. HEDIS-aligned demo, not NCQA-certified._
