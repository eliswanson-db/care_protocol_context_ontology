---
page: pages/a9808138-3aba-4053-a080-e405d405721e
title: "Diabetes Cohort"
state: DRAFT
updated: 2026-11-01T22:42:45.675Z
synonyms: ["diabetes cohort", "diabetes denominator", "diabetes population", "diabetic patients", "patients with diabetes"]
description: "The diabetes cohort is the set of patients with a diabetes diagnosis, used as the basis for the diabetes quality measures (GSD, KED, etc.)."
---
The **diabetes cohort** is the set of patients with a diabetes diagnosis, used as the basis for the diabetes
quality measures (GSD, KED, etc.). It is resolved **semantically**, not by a hand-maintained code list.

- A patient is in the cohort if they have any ICD-10-CM diagnosis that is a **descendant of E10, E11, or
  E13** (type 1, type 2, and other/specified diabetes) in the ICD-10 hierarchy.
- This is computed by joining `silver_condition` to the **`icd10_closure`** table on `descendant_code` where
  `ancestor_code IN ('E10','E11','E13')` — a **single equality join** that captures the entire subtree
  (e.g. `E11.21`, `E11.319`) via **subsumption**.
- Result: `silver_diabetes_cohort` (distinct `patient_id`). A flat code list would miss specific children and
  undercount; the hierarchy closure catches them all.

> See also **ICD-10 Subsumption**. HEDIS-aligned demo, not NCQA-certified.
