---
page: pages/c460dae0-4e87-4176-bf48-c30e423c1966
title: "BPD (Blood Pressure Control)"
state: PUBLISHED
updated: 2026-10-30T15:36:56.209Z
synonyms: ["BP control", "BPD", "Blood Pressure Control for Patients With Diabetes", "controlled blood pressure", "hypertension control"]
description: "Share of diabetic patients aged 18\u201375 whose most recent BP reading in the year is controlled (< 140/90 mmHg)."
---
## Definition
HEDIS measure of blood-pressure control in patients with diabetes.

## Measure specification
* **Denominator:** **Diabetes Cohort**, aged **18–75** at the end of the measurement year.
* **Numerator:** the **most recent** BP reading in the measurement year has **systolic < 140 mmHg AND diastolic < 90 mmHg**.
* **Reading definition:** a systolic (LOINC `8480-6`) and a diastolic (LOINC `8462-4`) observation from the **same encounter/timestamp**.
* **Care gap:** no reading in the year, or an uncontrolled latest reading.

## Data
* **Metric view:** `bpd_compliance_metrics`
* **Patient-level detail:** `gold_adherence_bpd`

---
_HEDIS-aligned demo, not NCQA-certified._
