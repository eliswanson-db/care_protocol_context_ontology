---
name: Diabetes Cohort
synonyms: [diabetes cohort, diabetic patients, patients with diabetes, diabetes population, diabetes denominator]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.care_protocol.silver_diabetes_cohort
  - eli_test_classic_catalog.care_protocol_terminology.icd10_closure
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
