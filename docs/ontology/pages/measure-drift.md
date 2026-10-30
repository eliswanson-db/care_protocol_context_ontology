---
name: Measure Drift (Value-Set Versioning)
synonyms: [measure drift, value set versioning, value set drift, measure definition change, spec change, code set change, year over year measure change]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.care_protocol_terminology.value_set_segment
  - eli_test_classic_catalog.care_protocol.silver_observation
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
