---
page: pages/ba2bd2b4-c6e3-4dad-a3e9-89e9946b11e4
title: "HbA1c (A1c) \u2014 Hemoglobin A1c"
state: DRAFT
updated: 2026-11-01T22:42:45.675Z
synonyms: ["A1C test", "A1c", "HbA1c", "HgbA1c", "glycated hemoglobin", "glycohemoglobin", "hemoglobin A1c"]
description: "HbA1c (A1c) is a blood test that reflects average blood glucose over roughly the prior 2\u20133 months."
---
**HbA1c (A1c)** is a blood test that reflects average blood glucose over roughly the prior 2–3 months. It is
the primary marker of **glycemic control** in diabetes and the basis of the **GSD** measure numerator.

- **Terminology:** LOINC. The canonical code is **`4548-4`** (Hemoglobin A1c/Hemoglobin.total in Blood);
  the demo value set `GSD_A1C_TEST` also includes related A1c LOINC codes.
- **Interpretation (demo bands):** **< 8%** good control; **> 9%** poor control.
- A1c results are conformed into `silver_observation` (one row per lab result) and feed `gold_adherence_gsd`.

> Codes are literal and attributed to LOINC. HEDIS-aligned demo, not NCQA-certified.
