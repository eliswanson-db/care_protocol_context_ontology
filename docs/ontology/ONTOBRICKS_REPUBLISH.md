# Republishing the clinicaldomain graph (checked 2026-11-06; republished 2026-11-20)

**2026-11-20:** infra deleted and recreated `eswanson_demo`, so v3 was republished as-is (Path A) into
`eswanson_demo.ontobricks` (Ontobricks always publishes there). `check_graph_version.py`: REQUIRED 12/12, OPTIONAL
0/9 (the Path B fixes, not applied). Its predicate counts are the committed baseline
`docs/ontology/graph_baseline_clinicaldomain.json`. After a catalog recreate, re-run
`scripts/grant_app_uc_reader.py` so the app SP can read it again.

**What Ontobricks actually runs.** The published graph is built from the Ontobricks project's own mapping, compiled
into the live view `eswanson_demo.ontobricks.triplestore_clinicaldomain_v<N>` (copy of v3:
`ontobricks_compiled_mapping_v3.sql`). It is NOT generated from `src/ontology/care_protocol.r2rml.ttl`; that file
documents the intended sources but uses different IRIs (`patient/`, `drugclass/` vs the graph's `Patient/`,
`DrugClass/`). Because the view is live, querying it shows exactly what a republish would materialize.

**Before republishing:** the DMVM app is pinned to v3 (`CARE_ONTOBRICKS_TABLE` in `src/app/app.yaml`); without the
pin it would follow the new version within 5 minutes.

## 2026-11-24: v5 check (published by Eli) — do not move the app pin yet

`check_graph_version.py` on `triplestore_clinicaldomain_v5_graph`: REQUIRED 11/12. Items 1, 2, 3 and 4 above are in
(drug-class membership for all 16 ingredients, clean hasIngredient, the 7 appliesTo edges, the reflowed eGFR codes).
The failing check is a real regression:

**A. eligibleFor / hasCareGap cover GSD only** (13,133 -> 2,399 and 6,744 -> 618; HEDIS facts F09 and F24 no longer
resolve). The project keeps one relationship per (source class, property, target class), and both relationships now
read only `gold_adherence_gsd`. In the `clinicaldomain` project, replace the two relationship sources with:

- `Patient -eligibleFor-> Measure`:
  ```sql
   SELECT patient_id AS source_id, 'GSD' AS target_id FROM eli_test_classic_catalog.care_protocol.gold_adherence_gsd
   UNION ALL SELECT patient_id AS source_id, 'BPD' AS target_id FROM eli_test_classic_catalog.care_protocol.gold_adherence_bpd
   UNION ALL SELECT patient_id AS source_id, 'KED' AS target_id FROM eli_test_classic_catalog.care_protocol.gold_adherence_ked
   UNION ALL SELECT patient_id AS source_id, 'EED' AS target_id FROM eli_test_classic_catalog.care_protocol.gold_adherence_eed
   UNION ALL SELECT patient_id AS source_id, 'SPD' AS target_id FROM eli_test_classic_catalog.care_protocol.gold_adherence_spd
   UNION ALL SELECT patient_id AS source_id, 'MAD' AS target_id FROM eli_test_classic_catalog.care_protocol.gold_adherence_mad
  ```
- `Patient -hasCareGap-> Measure` (each NOT (...) is that measure's governed Compliance Status, missing evidence =
  gap; GSD is the HEDIS rule, last A1c <= 9%, so the gap is poor control or no test, as aligned 2026-11-21):
  ```sql
   SELECT patient_id AS source_id, 'GSD' AS target_id FROM eli_test_classic_catalog.care_protocol.gold_adherence_gsd WHERE NOT (COALESCE(evidence_value <= 9.0, false))
   UNION ALL SELECT patient_id AS source_id, 'BPD' AS target_id FROM eli_test_classic_catalog.care_protocol.gold_adherence_bpd WHERE NOT (COALESCE(systolic < 140 AND diastolic < 90, false))
   UNION ALL SELECT patient_id AS source_id, 'KED' AS target_id FROM eli_test_classic_catalog.care_protocol.gold_adherence_ked WHERE NOT (egfr_datetime IS NOT NULL AND uacr_datetime IS NOT NULL)
   UNION ALL SELECT patient_id AS source_id, 'EED' AS target_id FROM eli_test_classic_catalog.care_protocol.gold_adherence_eed WHERE NOT (evidence_datetime IS NOT NULL)
   UNION ALL SELECT patient_id AS source_id, 'SPD' AS target_id FROM eli_test_classic_catalog.care_protocol.gold_adherence_spd WHERE NOT (evidence_datetime IS NOT NULL)
   UNION ALL SELECT patient_id AS source_id, 'MAD' AS target_id FROM eli_test_classic_catalog.care_protocol.gold_adherence_mad WHERE NOT (COALESCE(pdc >= 0.8, false))
  ```
- `Measure` entity: add `UNION SELECT 'MAD'` (v3 had MAD; the source above includes it).

Expected after a rebuild: eligibleFor 13,136 (GSD 2,399, BPD 2,399, EED 2,399, KED 2,802, SPD 2,277, MAD 860) and
hasCareGap 6,988 (GSD 877, which is the GSD metric view's NOT_MET count).

**The other two shrinks are source changes, not losses:** `loincCode` 308 -> 11 and the LabTest labels follow the
`loinc` table (11 rows today). `label` 26,027 -> 15,466 follows the Patient entity, which now reads `panel_roster`
(3,031 attributed patients) instead of all 25,000 patients. Every measure patient is in the roster; the 4,563
patients outside it keep their diagnosis edges but lose their Patient type and age. Fine for the benchmark; say if you
want all patients typed (source `bronze_patient`, as v3).

**Still open from the list above:** 3b (Observation IRI: resultValue is on `Observation/` but the edges point at
`obs/`; F26), 5 (containsTest, F15), 5b (dates, F28), 6 (Clinic, F07).

After A and a rebuild, Claude reruns the gate, moves `CARE_ONTOBRICKS_TABLE` to the new version, moves F22, F23 and F25
from gap to pointer, and redeploys.

## 2026-11-21 republish: what the benchmark needs (Eli, in the `clinicaldomain` project)

The data was reflowed on 2026-11-21 (year-aware value sets, the lab's CKD-EPI 2021 eGFR switch, Step 3 > 9%), so v3
is stale. `tests/test_hedis_facts.py` lists the graph gaps. In the project's own terms (entity id columns as the
existing mappings use them), in priority order:

**Needed for the graph's benchmark questions (q9 contraindications, q2/q10 statins):**
1. **inDrugClass for every class** (fact F22). Replace source `src_30` with
   `SELECT code AS ing_code, parent_code AS drug_class FROM eli_test_classic_catalog.care_protocol_terminology.rxnorm_hier WHERE relationship = 'class_member'`.
2. **hasIngredient only for ingredients.** Add `WHERE relationship = 'ingredient_of'` to source `src_25`.
3. **appliesTo: Threshold → LoincPart** (F23, new). Add object property `appliesTo` (domain Threshold, range
   LoincPart) and a relationship with source
   `SELECT subject AS thr, object AS part_code FROM eli_test_classic_catalog.care_protocol_terminology.protocol_edges WHERE predicate = 'appliesTo'`
   (7 edges, e.g. `Threshold/eGFR_LT_30 appliesTo part/LP-EGFR`).
3b. **Observation IRI** (F26, found by the A1c trace). The project's Observation entity writes `rdf:type` and
   `resultValue` on `Observation/{obs_id}`, but `hasObservation` and `ofTest` use `obs/{obs_id}`, so a traversal from
   a patient never reaches a result value (it can't compare A1c 11.0 with 9, or eGFR 19.4 with 30). Change the
   Observation entity's IRI template to `obs/{obs_id}` (the edges' IRI; keep `obs/`, the app uses it).
4. **Republish** (F25). Picks up the reflowed observations (eGFR results since 2022-07-01 are `loinc/98979-8`).

**Recommended (q8):**
5. **containsTest: ValueSet → LabTest** for the measure lab value sets, current measurement year (F15). Add object
   property `containsTest` (domain ValueSet, range LabTest) with source
   `SELECT v.segment_id AS vs_id, v.code AS loinc_code FROM eli_test_classic_catalog.care_protocol_terminology.value_set_segment v WHERE v.code_system = 'LOINC' AND v.measurement_year = (SELECT max(measurement_year) FROM eli_test_classic_catalog.care_protocol_terminology.value_set_segment w WHERE w.segment_id = v.segment_id AND w.measurement_year <= '2026')`
   (e.g. `ValueSet/KED_EGFR containsTest loinc/98979-8`, and no MDRD).

5b. **Dates on diagnoses and orders** (F28, benchmark q6). q6 asks about conditions and orders active on 2026-10-30,
   but `hasDiagnosis` / `prescribed` carry no dates. Map them as dated nodes: a `ConditionRecord` per
   `silver_condition` row (`onset_date`, `stop_date`, `hasCode` → `icd/{code}`) and a `MedicationOrder` per
   `bronze_order_med` row (`start_ts`, `stop_ts`, `hasDrug` → `rx/{code}`), linked from the patient.

**Optional (parity only):**
6. **Clinic** (F07, q1). Entity `Clinic` from `SELECT DISTINCT clinic_id FROM eli_test_classic_catalog.care_protocol.panel_roster`;
   relationship `attributedTo` (Patient → Clinic) from `SELECT patient_id, clinic_id FROM eli_test_classic_catalog.care_protocol.panel_roster`.
7. **Labels on edge nodes** (Path B fix 3 below).

Then send Claude the new table name. Claude runs `check_graph_version.py --graph <table>_graph --save-baseline`,
`CARE_LIVE=1 tests/test_hedis_facts.py` (after moving the graph pointers from gap to pointer), moves the app pin,
and redeploys.

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
1. `.venv/bin/python -I scripts/check_graph_version.py --graph eswanson_demo.ontobricks.triplestore_clinicaldomain_v<N>_graph --save-baseline`
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
