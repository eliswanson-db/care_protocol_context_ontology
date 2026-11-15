---
page: pages/90137b0e-d1a0-4667-aea0-8aff1f754984
title: "SPD (Statin Therapy)"
state: PUBLISHED
updated: 2026-10-30T15:36:48.201Z
synonyms: ["SPD", "Statin Therapy for Patients With Diabetes", "cholesterol medication for diabetics", "lipid therapy", "statin adherence", "statin therapy"]
description: "Share of diabetic patients aged 40\u201375 dispensed at least one statin; statins resolved from RxNorm ingredients via subsumption."
---
## Definition
HEDIS measure of statin use in patients with diabetes.

## Measure specification
* **Denominator:** **Diabetes Cohort**, aged **40–75** at the end of the measurement year.
* **Numerator:** at least one statin dispensed during the measurement year.
* **Value set:** `SPD_STATIN` (RxNorm **ingredients**, e.g. `36567` simvastatin, `83367` atorvastatin)

## Why subsumption is required
Prescriptions carry RxNorm **clinical-drug** codes (e.g. `312961` *Simvastatin 20 MG Oral Tablet*), not ingredients. A flat ingredient match finds **zero** statins, so SPD resolves ingredients to their clinical drugs through `rxnorm_closure` (see **Code Subsumption**).

## Data
* **Metric view:** `spd_compliance_metrics`
* **Patient-level detail:** `gold_adherence_spd`

---
_HEDIS-aligned demo, not NCQA-certified._
