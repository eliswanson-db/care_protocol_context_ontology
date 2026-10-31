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
  ingredient/class (from `rxnorm_hier`), care-protocol edges (from `protocol_edges`), and measure results
  (all five: GSD/BPD/KED/EED/SPD, each with `eligibleFor` + `status` + `hasCareGap`).
- **`care_protocol_graph.mmd` / `.svg` / `.png`** — the cross-vocabulary graph: patient → HEDIS measure →
  guideline → drug/lab, across ICD-10 · LOINC · RxNorm. Thick red edges are the care-protocol knowledge
  that crosses vocabularies (the graph's reason to exist); dashed edges are per-patient instance links.
  Rendered with `docs/architecture/mermaid-config.json` (`mmdc -i … -c … -b white`).

## What the graph adds over the SQL closure (the benchmark's point)
- ICD-10 `subClassOf` → the reasoner derives the transitive closure that `icd10_closure` materializes in SQL:
  **same answer** for is-a rollups → shows the closure suffices there.
- `hasComponent` (LOINC multiaxial), `hasIngredient`+`inDrugClass` (2-hop), and especially the care-protocol
  edges (`recommendedFor`/`contraindicatedWith`/`monitoredBy`) are **typed, cross-vocabulary, multi-hop** —
  where a single is-a closure cannot answer and the graph (traversal + inference) earns its place.

## Revision notes (2026-10-30 rev 4 — metric views relocated to a separate schema, ADR-0013)
Rev 3 mitigated the scan choke two ways (remove ABox-less OWL classes; exclude the view layer from the
Ontobricks source scope). We now go one better and make it structural **as code**: the governed metric
views were **relocated out of `care_protocol` into a dedicated `care_protocol_semantic` schema** (their
`source:` still points at `care_protocol.gold_adherence_*`). A scan scoped to the base schema therefore
cannot see a metric view even if the per-view exclude is forgotten. Consequence for the Ontobricks config
(still Eli-owned, ADR-0005): the mapping **source scope must remain `care_protocol.{bronze_*,silver_*,gold_*}`
+ `care_protocol_terminology.*`** and must **NOT** add `care_protocol_semantic` — that schema is the
Genie/BI/SQL consumption layer, not graph entities. The rev-3 per-view exclude is now belt-and-suspenders.

## Revision notes (2026-10-30 rev 3 — metric views choke the entity scan)
Third pass surfaced `Entity: ValueSet → Table: gsd_compliance_metrics` failing with
`METRIC_VIEW_MISSING_MEASURE_FUNCTION`. Neither `ValueSet` nor that metric view is in this R2RML —
so **Ontobricks auto-binds every declared OWL class to a catalog table it discovers**, and the two
ABox-less classes (`ValueSet`, `ProtocolRule`) got bound to leftover `*_compliance_metrics` **metric
views**, which cannot be probed with a plain `SELECT` (they require `MEASURE()`/`AGG()`). That hard SQL
error appears to abort the entity scan, which is why valid entities (icd/obs/loinc) still showed
"not found". Two fixes:
- **OWL:** removed `ValueSet` / `ProtocolRule` (no ABox) so nothing auto-binds to the metric views.
- **Ontobricks config (Eli-owned, ADR-0005):** restrict the mapping **source scope** to base Delta tables
  only — `care_protocol.{bronze_*,silver_*,gold_*}` + `care_protocol_terminology.*` — and **exclude the
  entire `src/semantic` view layer** (`*_compliance_metrics` metric views; also any `*_metrics` / metric
  views). Those are Genie/SQL surfaces, not graph entities. After excluding them and re-importing this
  R2RML, the rev-2 entity/relationship resolution should complete.

## Revision notes (2026-10-30 rev 2 — Ontobricks endpoint-resolution fixes)
Second import pass (18 pass / 13 err) showed Ontobricks resolves a relationship endpoint to an entity by
its **id column name**, which must map to exactly one entity/prefix. Only `patient_id`→Patient,
`loinc_code`→LabTest, `drug_class`→DrugClass resolved; the rest collided (`code` used by both `icd/` and
`rx/`; `parent_code` used by both `icd/` and `rx/`; the `rx/` prefix hosted both Medication and Ingredient).
Fixed by enforcing two invariants (verified by a column→prefix uniqueness check):
- **One entity per IRI prefix** — Ingredient moved to its own prefix `ing/` (was sharing `rx/`).
- **One unique, prefix-qualified id column per entity**, aliased identically in every referencing map:
  `patient_id · icd_code · icd_parent · loinc_code · part_code · rx_code · ing_code · drug_class ·
  measure_id · obs_id`. The Observation surrogate now includes `loinc_code` so a multi-analyte panel at one
  timestamp stays unique.
- **Expected residual:** `rdfs:subClassOf` still shows "property not in ontology" (it's an RDFS built-in)
  and its parent endpoint uses `icd_parent` (not the Condition key `icd_code`), so Ontobricks may flag that
  one endpoint — benign; the triple still links two `icd/` Condition IRIs. Drop `IcdSubClassMap` if you want
  is-a to live only in `icd10_closure` + the reasoner.

## Revision notes (2026-10-30 rev 1 — Ontobricks validation fixes)
First Ontobricks import surfaced "target entity not found" / "property not found" errors. Root cause: only
4 of 8 node types declared an `rr:class`, object-IRI templates didn't match their entity's subject template,
and the LOINC-axis / measure-status predicates didn't exist (or were misspelled) in the TBox. Fixed by:
- **Every node type now has an explicit entity map** (subjectMap + `rr:class`): `patient/ icd/ loinc/ part/
  rx/ drugclass/ measure/ obs/`. Previously `rx/ part/ measure/ drugclass/` had none.
- **IRI templates unified** — one prefix + one `{placeholder}` per node type; sqlQueries alias columns so
  every object IRI is byte-identical to the entity subject it points at (e.g. `icd10_code AS code` →
  `icd/{code}`). The compound `obs/{patient_id}/{result_ts}` became `obs/{obs_id}` (surrogate key).
- **LOINC axes**: added `hasSystem` / `hasMethod` to the TBox and mapped `loinc_parts.predicate`
  (`has_component`/`has_system`/`has_method`) onto the canonical camelCase properties, one map per axis.
- **Protocol edges split per predicate** so each object lands in the right namespace (recommend/contra →
  `icd/`, `monitoredBy` → `part/`, `inDrugClass` → `drugclass/`). The old generic `concept/` namespace
  (which never joined the coded nodes) is gone.
- **Measure status** uses `cp:status` (the TBox property); the old `cp:measureStatus` didn't exist. Added
  `hasCareGap` (NOT_MET) and `hasObservation` maps.
- `rdfs:subClassOf` stays an RDFS built-in — Ontobricks listing it apart from the `cp:` properties is
  expected, not an error. Edge qualifiers (`protocol_edges.value`, thresholds) remain unmodeled (need
  reification). `ValueSet`/`ProtocolRule` are reserved/unmapped until that data is generated.

## Import notes
- Serialization is Turtle; mappings are standard **R2RML** (`rr:` vocabulary). Adjust the logical-table
  connector/quoting to what your Ontobricks deployment expects (standard R2RML `rr:tableName`/`rr:sqlQuery`
  vs a Databricks-native mapping). All source tables are produced by `bundle run setup` + the measures pipeline.
- License-clean: LOINC multiaxial Parts (LOINC License) + ICD-10-CM (public) + RxNorm (NLM) + care-protocol
  edges. **No SNOMED relationships** are used (ADR-0002).
