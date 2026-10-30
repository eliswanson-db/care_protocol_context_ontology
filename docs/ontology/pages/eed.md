---
name: EED — Eye Exam for Patients With Diabetes
synonyms: [EED, eye exam, diabetic eye exam, retinal exam, retinal screening, diabetic retinopathy screening, dilated eye exam]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.care_protocol.gold_adherence_eed
  - eli_test_classic_catalog.care_protocol.eed_compliance_metrics
---

**EED (Eye Exam for Patients With Diabetes)** is a HEDIS measure for diabetic retinal screening — catching
diabetic retinopathy early.

- **Eligible population (denominator):** patients aged **18–75** as of the end of the measurement year in the
  **diabetes cohort**.
- **Numerator (compliant):** a **retinal / diabetic eye exam** during the measurement year, identified by the
  `EED_EYE_EXAM` value set of **SNOMED procedure** codes (e.g. `722161008` *Diabetic retinal eye exam*,
  `700070005` *Optical coherence tomography of retina*).

EED is the **procedure-based** measure of the set: it reads `silver_procedure` (conformed from
`bronze_procedure`), the only measure that uses procedures rather than labs, diagnoses, or medications.

> Full HEDIS also credits a negative retinal screen in the prior year; this demo uses the measurement year.
> SNOMED code values come from the synthetic data only — no licensed SNOMED hierarchy is shipped (ADR-0002).
> HEDIS-aligned demo, not NCQA-certified.
