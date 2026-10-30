---
name: uACR — Urine Albumin-Creatinine Ratio
synonyms: [uACR, ACR, urine albumin creatinine ratio, microalbumin, microalbuminuria, albumin creatinine ratio]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.care_protocol_terminology.value_set_segment
---

**uACR (urine albumin-creatinine ratio)** measures albumin in the urine relative to creatinine — an early
marker of kidney damage (albuminuria). It is the second component of the **KED** numerator.

- **Terminology:** LOINC. The demo value set `KED_UACR` includes **`14959-1`** (Microalbumin/Creatinine
  [Mass Ratio] in Urine) and `9318-7`.
- uACR tests are conformed into `silver_observation` and feed `gold_adherence_ked` (`uacr_flag`).
- In this demo **uACR is the limiting component** of KED: far fewer patients have a uACR than an eGFR, so the
  combined KED rate tracks the uACR rate. Closing the KED gap means ordering more uACR tests.

> HEDIS-aligned demo, not NCQA-certified.
