---
page: pages/19b0d253-a325-493e-ba7b-9ffb42c6ab53
title: "ICD-10 Subsumption & the Closure Table"
state: DRAFT
updated: 2026-11-01T22:42:45.675Z
synonyms: ["ICD-10 hierarchy", "ancestor descendant", "code rollup", "hierarchical codes", "is-a hierarchy", "subsumption", "transitive closure"]
description: "Subsumption is the \"is-a\" relationship between a broader concept and its narrower descendants."
---
**Subsumption** is the "is-a" relationship between a broader concept and its narrower descendants (e.g.
`E11.21` *Type 2 diabetes with diabetic nephropathy* **is a** `E11` *Type 2 diabetes mellitus*). Querying by a
parent concept should automatically include all descendants.

- **Adjacency** (`icd10_hier`): each code with its immediate parent — needs a recursive query to roll up.
- **Transitive closure** (`icd10_closure`): every `(ancestor_code, descendant_code)` pair at all depths
  (depth 0 = self). A cohort or value-set membership check becomes a **single equality join** — no recursive
  CTE — which is fast, portable, and easy for Genie to generate.

This is the core ontology differentiator: **meaning via hierarchy**. A flat list of diabetes codes catches
only the exact codes listed; the closure resolves the whole E10/E11/E13 subtree, so specific diagnoses like
`E11.21` are included automatically.

> Built by `src/semantic/build_closure.py` (iterative BFS, no recursive CTE). HEDIS-aligned demo.
