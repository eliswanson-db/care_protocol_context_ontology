# A5 Ontobricks — ontology artifacts to import

Per ADR-0005, Eli deploys/configures **Ontobricks**; this directory is the **integration contract** — the
ontology files to import. The build does not automate Ontobricks.

## Files
- **`care_protocol.owl.ttl`** — the OWL **TBox**: classes (`Patient`, `Condition` + `DiabetesDiagnosis`/`CKD`/
  `HeartFailure`/`Pregnancy`/`HepaticDisease`, `LabTest`, `LoincPart`, `Medication`, `Ingredient`, `DrugClass`,
  `Measure`, `ValueSet`) and typed object properties (`hasDiagnosis`, `ofTest`, `hasComponent`, `hasIngredient`,
  `inDrugClass`, `recommendedFor`, `contraindicatedWith`, `monitoredBy`, `eligibleFor`, `hasCareGap`). ICD-10
  is-a is modeled on `rdfs:subClassOf`.
- **`care_protocol.r2rml.ttl`** — R2RML mapping UC tables → the ontology (the ABox): patients, diagnoses,
  ICD subClassOf (from `icd10_hier`), observations, LOINC axes (from `loinc_parts`), medications +
  ingredient/class (from `rxnorm_hier`), care-protocol edges (from `protocol_edges`), and measure results.

## What the graph adds over the SQL closure (the benchmark's point)
- ICD-10 `subClassOf` → the reasoner derives the transitive closure that `icd10_closure` materializes in SQL:
  **same answer** for is-a rollups → shows the closure suffices there.
- `hasComponent` (LOINC multiaxial), `hasIngredient`+`inDrugClass` (2-hop), and especially the care-protocol
  edges (`recommendedFor`/`contraindicatedWith`/`monitoredBy`) are **typed, cross-vocabulary, multi-hop** —
  where a single is-a closure cannot answer and the graph (traversal + inference) earns its place.

## Import notes
- Serialization is Turtle; mappings are standard **R2RML** (`rr:` vocabulary). Adjust the logical-table
  connector/quoting to what your Ontobricks deployment expects (standard R2RML `rr:tableName`/`rr:sqlQuery`
  vs a Databricks-native mapping). All source tables are produced by `bundle run setup` + the measures pipeline.
- License-clean: LOINC multiaxial Parts (LOINC License) + ICD-10-CM (public) + RxNorm (NLM) + care-protocol
  edges. **No SNOMED relationships** are used (ADR-0002).
