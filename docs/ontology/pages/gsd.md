---
name: GSD — Glycemic Status Assessment for Patients With Diabetes
synonyms: [GSD, glycemic status assessment, A1c control measure, HbA1c measure, diabetes A1c testing, blood sugar control measure]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.care_protocol.gold_adherence_gsd
  - eli_test_classic_catalog.care_protocol.gsd_compliance_metrics
---

**GSD (Glycemic Status Assessment for Patients With Diabetes)** is a HEDIS quality measure. It assesses
whether patients with diabetes had their glycemic status evaluated during the measurement year.

- **Eligible population (denominator):** patients aged **18–75** as of the end of the measurement year who
  are in the **diabetes cohort** (an ICD-10-CM diabetes diagnosis under E10/E11/E13, resolved by subsumption
  over the ICD-10 hierarchy).
- **Numerator (compliant):** at least one **HbA1c (A1c)** test (LOINC value set `GSD_A1C_TEST`) in the
  measurement year.
- **Glycemic control bands:** the latest A1c value is also classified as **good control (<8%)** or
  **poor control (>9%)**.

A patient is **MET** when an A1c test is found, otherwise **NOT_MET** (a care gap). The governed rate is the
**GSD Compliance Rate** in `gsd_compliance_metrics` (compliant ÷ eligible).

> HEDIS-aligned demo, not NCQA-certified. GSD replaced the older "HbA1c Control for Patients With Diabetes"
> framing in recent HEDIS measurement years.
