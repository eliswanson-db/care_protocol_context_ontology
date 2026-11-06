# Republishing the clinicaldomain graph (checked 2026-11-06)

**What Ontobricks actually runs.** The published graph is built from the Ontobricks project's own mapping, compiled
into the live view `eswanson_demo.ontobricks.triplestore_clinicaldomain_v<N>` (copy of v3:
`ontobricks_compiled_mapping_v3.sql`). It is NOT generated from `src/ontology/care_protocol.r2rml.ttl`; that file
documents the intended sources but uses different IRIs (`patient/`, `drugclass/` vs the graph's `Patient/`,
`DrugClass/`). Because the view is live, querying it shows exactly what a republish would materialize.

**Before republishing:** the DMVM app is pinned to v3 (`CARE_ONTOBRICKS_TABLE` in `src/app/app.yaml`); without the
pin it would follow the new version within 5 minutes.

## Path A — republish as-is (verified safe)
Diff of the live view vs published v3 (observations excluded): +1 `icd/E11.22 subClassOf icd/N18` (the multi-parent
edge), and `Measure/BPD monitoredBy` `part/BP` -> `part/LP-SBP` + `part/LP-DBP` (the Nov 4 protocol_edges fix,
committed in a9bc57a, loaded by the Nov 6 setup run). `scripts/check_graph_version.py` on the live view: REQUIRED
12/12. Graph eval on it: `docs/benchmark/republish_check/graph_eval_republish_as_is.json`.

## Path B — also port the mapping fixes into the Ontobricks project (optional, then republish)
Simulated (no tables written) in `docs/benchmark/republish_check/simulated_graph_with_fixes.sql`; checks: REQUIRED
12/12, OPTIONAL 9/9. The three changes, in the compiled mapping's terms:
1. **inDrugClass for every class** — replace source `src_30` (statins only, from rxnorm_statin) with
   `SELECT code AS ing_code, parent_code AS drug_class FROM eli_test_classic_catalog.care_protocol_terminology.rxnorm_hier WHERE relationship = 'class_member'`.
2. **hasIngredient only for ingredients** — add `WHERE relationship = 'ingredient_of'` to source `src_25`
   (today it also emits `rx/<ingredient> hasIngredient ing/DRUGCLASS-*`, 16 wrong edges).
3. **Names on the nodes the edges use** — `rdfs:label` on `icd/{code}` (icd10_hier.name), `rx/{code}`
   (rxnorm_hier.name / bronze_order_med.description), `ing/{code}`, `DrugClass/{code}`, `ValueSet/{id}`
   (segment_name). Important: the project's entities today put type/label on DIFFERENT IRIs than the edges
   (`Condition/{code}` vs `icd/{code}`, `Medication/` vs `rx/`, `Ingredient/` vs `ing/`), so labels set on those
   entities would not reach the traversed nodes. Keep the edge IRIs unchanged (the app, entity linker and graph
   tools depend on `icd/`, `rx/`, `ing/`, `DrugClass/`, `ValueSet/`, `Measure/`, `Patient/`).

## After republishing (either path)
1. `.venv/bin/python -I scripts/check_graph_version.py --graph eswanson_demo.ontobricks.triplestore_clinicaldomain_v<N>_graph`
   — every REQUIRED check must pass (Path B: OPTIONAL too).
2. Move the pin in `src/app/app.yaml` to the new version, deploy.
3. Re-run the eval: `PYTHONPATH=src DATABRICKS_CONFIG_PROFILE=ECT CARE_ONTOBRICKS_TABLE=triplestore_clinicaldomain_v<N> .venv/bin/python -m benchmark.retrieval_eval.run_retrieval_eval --out retrieval_eval_arena.json`,
   copy it to `src/app/server/benchmark_data/`, deploy.

## Known, not blocking
- The ICD closure is already DAG-aware in the shared catalog: CKD found *through the closure* is 1,882 patients
  (1,792 by N18 code prefix; +90 with E11.22 and no N18 code); a closure-based cardiorenal cohort is 12 (gold, by
  code prefix, stays 10). Gold queries, measures and the demo questions are unaffected.
- Fixed 2026-11-06: the Tracer's graph stage shows a code's ancestors as a chain only when it is one (a code with
  two parents lists `ancestor [hops]`); the MCP `get_measure_rate` tool uses each metric view's own numerator.
