---
page: pages/c84e5ba4-05b5-47b2-9126-370c57c488a9
title: "Measurement Year"
state: PUBLISHED
updated: 2026-10-30T15:37:00.542Z
synonyms: ["HEDIS year", "MY", "measurement year", "reporting year"]
description: "The calendar year a measure is computed for (MY2025 here); sets the age cutoff, the numerator window, and which value-set version applies."
---
## Definition
The **measurement year (MY)** is the calendar year a HEDIS measure is computed for. Eligibility, the numerator window, and the value-set version are all evaluated relative to it.

* **Current MY:** **2025**, set by the pipeline setting `care.measurement_year`.
* **Age:** evaluated at `period_end` (Dec 31 of the MY).
* **Numerator window:** `period_start`–`period_end` (Jan 1 – Dec 31).
* **Value-set version:** `value_set_segment.measurement_year`.

## Business use
To compare rates across years, also compare the value-set versions in effect; see **Measure Drift**.
