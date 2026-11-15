---
page: pages/daf1c1e0-3a33-4c44-ab7a-fbdeec213255
title: "SSD \u2014 Diabetes Screening for People With Schizophrenia or Bipolar Disorder Using Antipsychotics"
state: DRAFT
updated: 2026-11-01T22:42:45.675Z
synonyms: ["SMI diabetes screening", "SSD", "antipsychotic metabolic monitoring", "behavioral health diabetes screening", "diabetes screening antipsychotics", "schizophrenia bipolar glucose screening"]
description: "SSD is a HEDIS quality measure that screens a high-metabolic-risk behavioral-health population for diabetes."
---
**SSD (Diabetes Screening for People With Schizophrenia or Bipolar Disorder Who Are Using Antipsychotic
Medications)** is a HEDIS quality measure that screens a **high-metabolic-risk behavioral-health population**
for diabetes. It is a **cross-domain** measure: it joins a serious-mental-illness diagnosis, antipsychotic
dispensing (RxNorm), and a glucose/HbA1c result (LOINC) — the kind of multi-domain question that motivates a
governed semantic layer and a terminology graph.

- **Eligible population (denominator):** patients aged **18–64** during the measurement year with
  **schizophrenia, schizoaffective disorder, or bipolar disorder** (value set `SSD_SMI_COHORT`:
  ICD-10-CM F20 / F25 / F31) **and at least one antipsychotic dispensed** (value set `SSD_ANTIPSYCHOTIC`,
  RxNorm; drug class `DRUGCLASS-ANTIPSYCHOTIC`).
- **Numerator (compliant):** at least one **glucose test or HbA1c test** (value set `SSD_GLUCOSE_HBA1C`) in
  the measurement year.
- **Exclusions:** **pre-existing diabetes** (`EXCL_PREEXISTING_DM`, E10/E11/E13), hospice, or death.

A patient is **MET** when a glucose/HbA1c screen is found, otherwise **NOT_MET** (a screening gap). The
governed rate is the **SSD Compliance Rate** in `ssd_compliance_metrics`.

> Antipsychotic-associated hyperglycemia maps to the ICD-10-CM **E09** (drug/chemical-induced diabetes) family,
> linking this cohort to the diabetes terminology graph. HEDIS-aligned demo, not NCQA-certified; demo value
> sets, not NCQA/VSAC.
