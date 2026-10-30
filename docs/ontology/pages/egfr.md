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

- **Terminology:** LOINC. The demo value set `KED_EGFR` includes **`33914-3`** (MDRD-based eGFR, the code
  Synthea emits) and **`98979-8`** (a newer CKD-EPI eGFR code). A measure must accept **all** valid LOINC
  codes for the concept — relying on a single code would undercount.
- eGFR tests are conformed into `silver_observation` and feed `gold_adherence_ked` (`egfr_flag`).

> This multi-code value set is the concrete example of **value-set / terminology drift** — the "right" code
> depends on vintage and source system. HEDIS-aligned demo, not NCQA-certified.
