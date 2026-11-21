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

**Worked example — eGFR equation change (KED):**
- **MY2025** `KED_EGFR` accepts `98979-8` (CKD-EPI 2021) **and** `33914-3` (MDRD).
- **MY2026** `KED_EGFR` accepts `98979-8` only: MDRD is retired.
- The demo health system's lab switched equations on **2022-07-01**, so every MY2026 eGFR result is `98979-8` and
  retiring MDRD doesn't change the MY2026 KED rate.
- Applying the 2026 version to an older year would. Every pre-switch result is `33914-3`, so 2021 eGFR coverage
  drops to zero under the 2026 set. Each measure therefore uses the value set of its own measurement year.

The demo query is `src/semantic/measure_drift_demo.sql` (patients with eGFR, per result year, under each version).

**Why the context layer matters:** because the value set is governed and year-stamped, you can (a) reproduce a
measure exactly as defined in any year, (b) attribute a rate change to a definition change vs. a care change,
and (c) see, before shipping a spec update, which codes you are about to drop.

> HEDIS-aligned demo, not NCQA-certified.
