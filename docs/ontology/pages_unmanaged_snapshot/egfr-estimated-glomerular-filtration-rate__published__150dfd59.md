---
page: pages/150dfd59-85b9-4efd-8014-bb170bfe626e
title: "eGFR (Estimated Glomerular Filtration Rate)"
state: PUBLISHED
updated: 2026-10-30T15:35:55.848Z
synonyms: ["GFR", "eGFR", "estimated glomerular filtration rate", "glomerular filtration", "kidney function test"]
description: "Kidney-function lab estimating how well kidneys filter blood (LOINC 33914-3 MDRD, 98979-8 CKD-EPI); one of KED's two tests."
---
## Definition
A lab estimate of how well the kidneys filter blood.

* **Value set:** `KED_EGFR`, containing **`33914-3`** (MDRD-based, the code Synthea emits) and **`98979-8`** (newer CKD-EPI).
* A measure must accept **every** valid code for the concept. Relying on a single code undercounts.

## Data
Conformed into `silver_observation`. Feeds `gold_adherence_ked` as `egfr_flag` and the `eGFR Test Rate` metric.

---
_The two eGFR code vintages are the worked example on the **Measure Drift** page._
