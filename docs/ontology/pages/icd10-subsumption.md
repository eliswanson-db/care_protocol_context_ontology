---
name: ICD-10 Subsumption & the Closure Table
synonyms: [subsumption, ICD-10 hierarchy, is-a hierarchy, ancestor descendant, transitive closure, code rollup, hierarchical codes]
domain: Clinical Domain
owner: eli.swanson@databricks.com
related_assets:
  - eli_test_classic_catalog.care_protocol_terminology.icd10_closure
  - eli_test_classic_catalog.care_protocol_terminology.icd10_hier
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
