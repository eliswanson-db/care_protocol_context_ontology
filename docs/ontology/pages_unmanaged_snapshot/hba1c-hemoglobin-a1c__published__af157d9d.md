---
page: pages/af157d9d-48f0-4ecc-80f4-5110c59018e9
title: "HbA1c (Hemoglobin A1c)"
state: PUBLISHED
updated: 2026-10-30T15:36:52.332Z
synonyms: ["A1C test", "A1c", "HbA1c", "HgbA1c", "glycated hemoglobin", "glycohemoglobin", "hemoglobin A1c"]
description: "Lab test of average blood glucose over the prior 2\u20133 months (LOINC 4548-4); the test counted by GSD."
---
## Definition
A blood test that reflects average blood glucose over roughly the prior 2–3 months. It is the primary lab marker of glycemic control in diabetes.

* **Canonical code:** LOINC **`4548-4`** (Hemoglobin A1c/Hemoglobin.total in Blood). Related A1c codes are included in the `GSD_A1C_TEST` value set.
* **Interpretation (demo bands):** **< 8%** good control, **> 9%** poor control.

## Data
One row per lab result in `silver_observation`. Feeds `gold_adherence_gsd`.

---
_LOINC codes are literal and attributed to LOINC._
