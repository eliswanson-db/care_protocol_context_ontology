---
name: HbA1c (A1c) — Hemoglobin A1c
synonyms: [A1c, HbA1c, hemoglobin A1c, glycated hemoglobin, glycohemoglobin, A1C test, HgbA1c]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.care_protocol_terminology.loinc
  - eli_test_classic_catalog.care_protocol_terminology.value_set_segment
---

**HbA1c (A1c)** is a blood test that reflects average blood glucose over roughly the prior 2–3 months. It is
the primary marker of **glycemic control** in diabetes and the basis of the **GSD** measure numerator.

- **Terminology:** LOINC. The canonical code is **`4548-4`** (Hemoglobin A1c/Hemoglobin.total in Blood);
  the demo value set `GSD_A1C_TEST` also includes related A1c LOINC codes.
- **Interpretation (GSD measure bands):** **< 8%** good control; **> 9%** poor control.
- **Clinical targets (care protocol):** below 7.0% for most adults, individualized by comorbidity burden and life
  expectancy: 6.0–7.0% with no or minimal complications and over 10 years' life expectancy; 7.0–8.0% with moderate
  comorbidity (5–10 years); 8.0–9.0% with marked comorbidity or end-stage disease (under 5 years). The measure
  bands score a result; the target is what a specific patient should aim for.
- **Recheck cadence:** every 3 months while above the individualized goal or after a therapy change; after a
  result above 9.0%, intensify therapy and recheck within 90 days (*Protocol Step 3*).
- A1c results are conformed into `silver_observation` (one row per lab result) and feed `gold_adherence_gsd`.

> Codes are literal and attributed to LOINC. HEDIS-aligned demo, not NCQA-certified.
