---
name: Value Set (Code Segment)
synonyms: [value set, code set, value set segment, measure codes, concept codes, terminology set]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.care_protocol_terminology.value_set_segment
---

A **value set** is a named list of terminology codes that defines a clinical concept for a measure — e.g. "the
A1c tests that satisfy GSD" or "the statins that satisfy SPD". Measures are defined in terms of value sets,
not raw codes, so the definition stays readable and governable.

- Stored in **`value_set_segment`** as `(segment_id, code, code_system, measurement_year, owner)`. One concept
  can span multiple **code systems** (LOINC, ICD-10-CM, RxNorm) and multiple codes.
- Examples: `GSD_A1C_TEST` (A1c LOINC codes), `KED_EGFR` / `KED_UACR` (kidney labs), `SPD_STATIN` (statin
  RxNorm ingredients), `EXCL_ESRD` (ESRD exclusion ICD-10 codes).
- The **`measurement_year`** column lets a value set **version** over time — the basis of the measure-drift
  story: the same measure can resolve to different codes in different years.

> These are hand-curated **demo** value sets (not NCQA/VSAC) built from free terminologies. HEDIS-aligned demo.
