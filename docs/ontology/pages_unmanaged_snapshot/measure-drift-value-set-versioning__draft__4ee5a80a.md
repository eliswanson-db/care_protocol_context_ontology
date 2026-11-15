---
page: pages/4ee5a80a-a4b7-47d5-93aa-f765943b8605
title: "Measure Drift (Value-Set Versioning)"
state: DRAFT
updated: 2026-11-01T22:42:45.675Z
synonyms: ["code set change", "measure definition change", "measure drift", "spec change", "value set drift", "value set versioning", "year over year measure change"]
description: "Measure drift is when a quality measure's result changes because its definition changed \u2014 not because the underlying care changed."
---
**Measure drift** is when a quality measure's *result changes because its definition changed* — not because
the underlying care changed. Value sets are versioned by **measurement year** (`value_set_segment.measurement_year`),
which makes drift explicit, auditable, and reproducible instead of a silent code-list edit.

**Worked example — eGFR code modernization (KED):**
- **MY2025** `KED_EGFR` accepts `98979-8` (CKD-EPI) **and** `33914-3` (MDRD).
- **MY2026** `KED_EGFR` is "modernized" to `98979-8` (CKD-EPI) only.
- The lab data is identical (Synthea records eGFR as `33914-3`, MDRD). Yet eGFR coverage for 2025 observations
  under each value-set version is:

| Value-set version | Patients with eGFR | Codes matched |
|---|---|---|
| 2025 | **79** | 33914-3 |
| 2026 | **0** | (none) |

Switching the value set silently erases eGFR coverage — which would collapse the KED rate — with zero change
in actual testing. The demo query is `src/semantic/measure_drift_demo.sql`.

**Why the context layer matters:** because the value set is governed and year-stamped, you can (a) reproduce a
measure exactly as defined in any year, (b) attribute a rate change to a definition change vs. a care change,
and (c) see, before shipping a spec update, which codes you are about to drop.

> HEDIS-aligned demo, not NCQA-certified.
