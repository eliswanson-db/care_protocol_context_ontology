---
name: Measurement Year
synonyms: [measurement year, MY, reporting year, measure year, HEDIS year]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.care_protocol.gold_adherence_gsd
  - eli_test_classic_catalog.care_protocol.gold_adherence_ked
---

The **measurement year (MY)** is the calendar year a HEDIS measure is computed for. Eligibility (e.g. age),
the numerator window (e.g. "an A1c test **in the measurement year**"), and value-set versions are all
evaluated relative to the MY.

- In this demo the MY is **2025** (configured via the pipeline setting `care.measurement_year`).
- Age is evaluated at **period_end** (Dec 31 of the MY); the numerator window is `period_start`–`period_end`
  (Jan 1 – Dec 31).
- Value sets carry a `measurement_year`, so a measure's definition can change year over year — the basis of
  the **measure-drift** demonstration.

> HEDIS-aligned demo, not NCQA-certified.
