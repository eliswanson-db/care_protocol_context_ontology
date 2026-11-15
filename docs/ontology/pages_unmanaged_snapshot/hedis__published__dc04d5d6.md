---
page: pages/dc04d5d6-2d8b-470e-95a4-4e81e297d7ad
title: "HEDIS"
state: PUBLISHED
updated: 2026-10-30T15:37:09.940Z
synonyms: ["HEDIS", "HEDIS measures", "Healthcare Effectiveness Data and Information Set", "diabetes quality measures", "quality measures"]
description: "Standardized quality-measure framework; parent concept for the five diabetes measures (GSD, KED, EED, BPD, SPD) in this domain."
---
## Definition
**HEDIS** is a standardized set of healthcare quality measures. Each measure defines an eligible population (denominator) and the care those patients should receive (numerator), evaluated over a measurement year.

## Measures in this domain
| Measure | What it checks | Eligible ages |
| --- | --- | --- |
| GSD | HbA1c test in the year | 18–75 |
| KED | Both eGFR and uACR tests in the year | 18–85 |
| EED | Retinal / diabetic eye exam in the year | 18–75 |
| BPD | Latest BP reading < 140/90 mmHg | 18–75 |
| SPD | At least one statin dispensed | 40–75 |

All five measures use the **Diabetes Cohort** as their base population.

## How the pieces fit
* **Measure → Care Gap:** patient-level MET / NOT_MET status.
* **Measure → Compliance Rate:** aggregate compliant ÷ eligible.
* **Measure → Value Set:** the codes that define each numerator, versioned by **Measurement Year**.

---
_HEDIS-aligned demo, not NCQA-certified. Value sets are hand-curated, not NCQA/VSAC._
