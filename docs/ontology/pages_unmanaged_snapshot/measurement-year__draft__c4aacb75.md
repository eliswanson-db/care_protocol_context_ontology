---
page: pages/c4aacb75-c618-44b0-b93e-1d703604ea2f
title: "Measurement Year"
state: DRAFT
updated: 2026-11-01T22:42:45.675Z
synonyms: ["HEDIS year", "MY", "measure year", "measurement year", "reporting year"]
description: "The measurement year (MY) is the calendar year a HEDIS measure is computed for."
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
