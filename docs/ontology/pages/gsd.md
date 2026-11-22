---
name: GSD — Glycemic Status Assessment for Patients With Diabetes
synonyms: [GSD, glycemic status assessment, A1c control measure, HbA1c measure, blood sugar controlled, blood sugar control measure, A1c poor control]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.care_protocol.gold_adherence_gsd
  - eli_test_classic_catalog.care_protocol_semantic.gsd_compliance_metrics
---

**GSD (Glycemic Status Assessment for Patients With Diabetes)** is a HEDIS quality measure of glycemic control:
it reads each eligible patient's **last** A1c of the measurement year.

- **Eligible population (denominator):** patients aged **18–75** as of the end of the measurement year who
  are in the **diabetes cohort** (an ICD-10-CM diabetes diagnosis under E10/E11/E13, resolved by subsumption
  over the ICD-10 hierarchy).
- **Two HEDIS indicators, both over all eligible patients:** **good control** = last A1c **below 8.0%**;
  **poor control** = last A1c **above 9.0%, or no A1c test** in the measurement year (a missing test counts as
  poor control; lower is better). A1c tests are the LOINC value set `GSD_A1C_TEST`.
- **Compliant (Blood Sugar Controlled):** last A1c **9.0% or below**, the inverse of the poor-control indicator.

A patient is **MET** when their last A1c is 9.0% or below, otherwise **NOT_MET** (a care gap: above 9.0% or no test).
In `gsd_compliance_metrics`: **GSD Compliance Rate** (compliant ÷ eligible), **Good Control Rate**, **Poor Control
Rate**, and **Tested Patients** (testing coverage, not a HEDIS indicator).

> HEDIS-aligned demo, not NCQA-certified. GSD replaced the older "HbA1c Control for Patients With Diabetes"
> framing in recent HEDIS measurement years.
