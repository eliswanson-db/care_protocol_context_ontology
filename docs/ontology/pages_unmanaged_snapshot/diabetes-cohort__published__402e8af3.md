---
page: pages/402e8af3-3e5a-4a46-aa36-22dcd8df5e64
title: "Diabetes Cohort"
state: PUBLISHED
updated: 2026-10-30T15:36:03.633Z
synonyms: ["diabetes cohort", "diabetes denominator", "diabetes population", "diabetic patients", "patients with diabetes"]
description: "Patients with any ICD-10-CM diagnosis under E10, E11, or E13 (including all child codes); the base population for every diabetes measure."
---
## Definition
The set of patients with a diabetes diagnosis: any ICD-10-CM code that is a **descendant of E10, E11, or E13** (type 1, type 2, and other/specified diabetes).

## How it is resolved
The cohort is resolved semantically, not from a hand-maintained code list. `silver_condition` is joined to `icd10_closure` on `descendant_code` where `ancestor_code IN ('E10','E11','E13')`. One equality join captures the whole subtree (e.g. `E11.21`, `E11.319`); see **Code Subsumption**.

## Data
`silver_diabetes_cohort`: one row per distinct `patient_id`.

## Business use
All five diabetes measures apply their own age band to this cohort. A flat code list would miss specific child codes and undercount every measure.
