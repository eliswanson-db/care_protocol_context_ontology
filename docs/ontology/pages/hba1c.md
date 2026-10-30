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
- **Interpretation (demo bands):** **< 8%** good control; **> 9%** poor control.
- A1c results are conformed into `silver_observation` (one row per lab result) and feed `gold_adherence_gsd`.

> Codes are literal and attributed to LOINC. HEDIS-aligned demo, not NCQA-certified.
