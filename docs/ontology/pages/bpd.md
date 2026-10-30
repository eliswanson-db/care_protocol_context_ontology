---
name: BPD — Blood Pressure Control for Patients With Diabetes
synonyms: [BPD, blood pressure control, BP control, hypertension control, controlled blood pressure, systolic and diastolic]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.care_protocol.gold_adherence_bpd
  - eli_test_classic_catalog.care_protocol.bpd_compliance_metrics
---

**BPD (Blood Pressure Control for Patients With Diabetes)** is a HEDIS measure for blood-pressure control in
diabetic patients.

- **Eligible population (denominator):** patients aged **18–75** as of the end of the measurement year in the
  **diabetes cohort**.
- **Numerator (compliant):** the patient's **most recent blood-pressure reading** in the measurement year is
  **controlled**, i.e. **systolic < 140 mmHg AND diastolic < 90 mmHg**.

A blood-pressure "reading" pairs a **systolic** (LOINC `8480-6`) and a **diastolic** (LOINC `8462-4`)
observation from the **same encounter/timestamp**; the measure uses the latest such reading in the year.
Missing a reading, or an uncontrolled latest reading, is a care gap.

> HEDIS-aligned demo, not NCQA-certified.
