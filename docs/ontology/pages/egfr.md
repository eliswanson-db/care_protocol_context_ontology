---
name: eGFR — Estimated Glomerular Filtration Rate
synonyms: [eGFR, GFR, estimated glomerular filtration rate, kidney function test, glomerular filtration]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.care_protocol_terminology.value_set_segment
---

**eGFR (estimated glomerular filtration rate)** estimates how well the kidneys filter blood. It is one of the
two components of the **KED** numerator (the other is **uACR**).

- **Terminology:** LOINC codes eGFR by the equation used: **`98979-8`** (race-free CKD-EPI 2021) and **`33914-3`**
  (MDRD, retired by most US labs in 2022). The demo health system's lab switched to CKD-EPI 2021 on 2022-07-01,
  so later results carry `98979-8`.
- **Value set `KED_EGFR`:** MY2025 accepts both codes; MY2026 accepts `98979-8` only. Each measurement year uses
  its own version.
- eGFR tests are conformed into `silver_observation` and feed `gold_adherence_ked` (`egfr_flag`).

> The equation change is a real example of **value-set drift**: which code counts depends on the year
> (see *Measure Drift*). HEDIS-aligned demo, not NCQA-certified.
