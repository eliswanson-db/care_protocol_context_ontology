---
page: pages/79503778-0e4b-4f80-af63-47bbca97d35e
title: "Code Subsumption (Closure Table)"
state: PUBLISHED
updated: 2026-10-30T15:36:42.654Z
synonyms: ["ICD-10 hierarchy", "ICD-10 subsumption", "RxNorm subsumption", "closure table", "code rollup", "is-a hierarchy", "subsumption", "transitive closure"]
description: "Is-a hierarchy resolution (ICD-10, RxNorm) via a precomputed ancestor\u2013descendant table, so one parent code matches all its children."
---
## Definition
**Subsumption** is the "is-a" relationship between a broader concept and its narrower descendants. For example, `E11.21` *Type 2 diabetes with diabetic nephropathy* **is a** `E11` *Type 2 diabetes mellitus*. Querying by a parent concept should include all of its descendants.

## Structures
* **Adjacency** (`icd10_hier`): each code with its immediate parent. Rolling up requires a recursive query.
* **Transitive closure** (`icd10_closure`, `rxnorm_closure`): every `(ancestor_code, descendant_code)` pair at all depths (depth 0 = self). Membership becomes a **single equality join** with no recursive CTE, which is fast, portable, and easy for Genie to generate.

## Examples
* **Diagnoses:** E10/E11/E13 → every specific diabetes code (**Diabetes Cohort**).
* **Medications:** statin ingredients → their clinical-drug codes (**SPD**).

## Business use
This is meaning via hierarchy, not flat code lists: specific codes are included automatically, without anyone maintaining them.

---
_Implementation: built by `src/semantic/build_closure.py` (iterative BFS)._
