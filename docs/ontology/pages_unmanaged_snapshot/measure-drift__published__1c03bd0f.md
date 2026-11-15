---
page: pages/1c03bd0f-573e-4dc8-b03e-0c05bb4473cc
title: "Measure Drift"
state: PUBLISHED
updated: 2026-10-30T15:35:58.936Z
synonyms: ["measure definition change", "measure drift", "spec change", "value set drift", "year over year measure change"]
description: "A rate change caused by a change in the measure's definition (value-set version), not in actual care; e.g. eGFR coverage dropping from 79 to 0 patients."
---
## Definition
**Measure drift** happens when a measure's result changes because its **definition** changed, not because care changed. Value sets are year-stamped, so drift is explicit, auditable, and reproducible rather than a silent edit to a code list.

## Examples
**eGFR code modernization (KED):** MY2025 `KED_EGFR` accepts `98979-8` and `33914-3`; MY2026 accepts only `98979-8`. The lab data is identical (Synthea emits `33914-3`):

| Value-set version | Patients with eGFR | Codes matched |
| --- | --- | --- |
| 2025 | **79** | 33914-3 |
| 2026 | **0** | (none) |

KED would collapse with zero change in actual testing.

## Business use
* Reproduce any year's measure exactly as it was defined.
* Attribute a rate change to a definition change or a care change.
* Before shipping a spec update, see which codes it would drop.

---
_Demo query: `src/semantic/measure_drift_demo.sql`._
