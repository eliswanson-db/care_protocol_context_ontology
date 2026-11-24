# Ontobricks import: Clinical Study lab (life sciences)

Same pattern as HEDIS: an OWL ontology plus an R2RML mapping that reads the real Unity Catalog tables directly
(inline `rr:sqlQuery`). There are no staging views. Both files are hand-maintained:

- `src/ontology/life_sciences/clinical_study.owl.ttl`: 32 classes (study design, participants and their SDTM-shaped
  records, and the standards they're coded to: MONDO, RxNorm, MED-RT, MeSH, CDISC CT, COSMoS).
- `src/ontology/life_sciences/clinical_study.r2rml.ttl`: 32 entity maps and 75 relationship maps.

**Source scope:** `eli_test_classic_catalog.clinical_study` + `eli_test_classic_catalog.clinical_study_standards`.
Don't add `clinical_study_semantic`: plain `SELECT`s on its metric views abort the entity scan (HEDIS rev 3/5).

**IRIs:** class `https://clinical-study-lab.example/ontology#<Class>`, property
`https://clinical-study-lab.example/ontology/<name>`, instance `https://clinical-study-lab.example/ontology/<Class>/<id>`.

**Ontobricks reads the SQL text, not the result.** Its diagnostics take a map's output columns from the outer
`SELECT` list (no `*` expansion) and can't resolve an `owl:unionOf` domain or range. So every map names its columns,
and a property used by several classes states them in a comment instead. `tests/test_ls_knowledge_parity.py`
checks both offline.

**Id columns:** every class has its own id column, `<class>_id` (e.g. `disease_id`, `participant_id`). Every
relationship uses those exact names for its endpoints, because Ontobricks matches an endpoint to an entity by column
name. A same-class edge (Disease subClassOf Disease) uses `<class>_target_id` for its target.

## Before importing

`.venv/bin/python -I scripts/ls_graph_check.py` runs every map's SQL on ECT. It checks that each map returns rows,
that entity ids are unique, and that every relationship endpoint resolves (no dangling edge). Last run on
2026-11-23: 0 problems.

## Steps (Eli, ADR-0005)

1. Open the Ontobricks project/domain **`ClinicalStudyLab`** (CamelCase). If it doesn't exist, create it. Keep it
   separate from `clinicaldomain`, so the HEDIS graph and its app pin are untouched.
2. Import the ontology: `clinical_study.owl.ttl`. Make sure it **replaces** the loaded ontology: the current file has
   32 classes, including `HeightObservation`, and no `KnowledgeConcept` or `DrugConcept`. If those two still show up,
   the old file is loaded and Ontobricks auto-maps them.
3. Import the mapping: `clinical_study.r2rml.ttl`. It replaces the earlier view-based mapping.
4. Set the source scope to the two schemas above and run **Mapping → Diagnostics**. Expect 32 entities and 75
   relationships, all OK. Then build and publish to `eswanson_demo.ontobricks`.
5. Send Claude the published triplestore table name (e.g. `triplestore_clinicalstudylab_v1`). Claude then checks the
   graph facts in `docs/benchmark/ls_facts.yaml` against it.

If the importer rejects or rewrites a map, send Claude the error. The map ids say what each one is
(`map:DiseaseEntity`, `map:sub_class_of__disease__disease`, ...).
