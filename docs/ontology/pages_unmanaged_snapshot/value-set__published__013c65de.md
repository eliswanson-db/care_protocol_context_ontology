---
page: pages/013c65de-c5b8-4fc8-824f-2d80cd5ca8ed
title: "Value Set"
state: PUBLISHED
updated: 2026-10-30T15:35:48.724Z
synonyms: ["code segment", "code set", "concept codes", "terminology set", "value set", "value set segment"]
description: "Named, year-versioned list of codes (LOINC, ICD-10-CM, RxNorm, SNOMED) that defines a clinical concept for a measure, e.g. GSD_A1C_TEST."
---
## Definition
A **value set** is a named list of terminology codes that defines a clinical concept, such as "the A1c tests that satisfy GSD". Measures reference value sets, not raw codes, so definitions stay readable and governable.

## Data
`value_set_segment` has the columns `(segment_id, code, code_system, measurement_year, owner)`. One concept can span multiple code systems and codes. The `measurement_year` column versions each set over time.

## Examples
| Value set | Concept | Code system |
| --- | --- | --- |
| `GSD_A1C_TEST` | HbA1c tests | LOINC |
| `KED_EGFR` / `KED_UACR` | Kidney labs | LOINC |
| `EED_EYE_EXAM` | Retinal exams | SNOMED |
| `SPD_STATIN` | Statin ingredients | RxNorm |
| `EXCL_ESRD` | ESRD exclusion | ICD-10-CM |

---
_Hand-curated demo value sets built from free terminologies, not NCQA/VSAC._
