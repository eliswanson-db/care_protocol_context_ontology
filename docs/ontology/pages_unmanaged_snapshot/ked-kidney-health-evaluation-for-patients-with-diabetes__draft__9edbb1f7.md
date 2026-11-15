---
page: pages/9edbb1f7-62bd-405e-9bb6-fa9413b7d243
title: "KED \u2014 Kidney Health Evaluation for Patients With Diabetes"
state: DRAFT
updated: 2026-11-01T22:42:45.675Z
synonyms: ["KED", "diabetic kidney screening", "eGFR and uACR testing", "kidney eval", "kidney health evaluation", "nephropathy screening"]
description: "KED (Kidney Health Evaluation for Patients With Diabetes) is a HEDIS quality measure for assessing kidney health in diabetic patients."
---
**KED (Kidney Health Evaluation for Patients With Diabetes)** is a HEDIS quality measure for assessing kidney
health in diabetic patients. Its numerator is **compound** — it requires two different tests in the same year.

- **Eligible population (denominator):** patients aged **18–85** as of the end of the measurement year in the
  **diabetes cohort**.
- **Numerator (compliant):** **both** of the following in the measurement year:
  1. an **eGFR** (estimated glomerular filtration rate) test — value set `KED_EGFR`, and
  2. a **uACR** (urine albumin-creatinine ratio) test — value set `KED_UACR`.

A patient is **MET** only when **both** components are present; missing either is a care gap. Because the two
components are tracked separately, the **eGFR Test Rate** and **uACR Test Rate** are each exposed in
`ked_compliance_metrics` alongside the combined **KED Compliance Rate**. In this demo uACR is the limiting
component (eGFR ~92%, uACR ~51%, combined ~51%).

> The eGFR value set spans LOINC vintages (e.g. `33914-3` MDRD and `98979-8`) — a reminder that value sets
> evolve and a measure must accept all valid codes for the concept. HEDIS-aligned demo, not NCQA-certified.
