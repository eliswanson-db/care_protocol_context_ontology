# Clinical Study Context & Evidence Lab — plan of record

`demo_id: life_sciences_clinical`, alongside `healthcare_hedis`. Decisions: ADR-0021 through ADR-0024. Ontology
evidence: `ONTOLOGY_RICHNESS_GATE.md`. Synthetic · CDISC-grounded · SDTM-/ADaM-shaped · Not submission-ready · Not for
clinical use.

**Core story:** from a raw study observation to a reproducible endpoint result, with CDISC-grounded meaning,
protocol-aware context, and record-level traceability. The graph has to earn its place by answering eligibility,
contraindication, prohibited-medication and amendment-diff questions that RAG and Genie Ontology cannot (G1–G6 in
the gate doc).

## 1. Inventory: what exists (HEDIS lab) and how the new lab reuses it

| Component | HEDIS today | Life sciences | Reuse |
|---|---|---|---|
| Bundle | `databricks.yml`. Targets dev/ect/dmvm. `&shared_uc` owns 3 schemas + volumes | 3 new schemas + volumes in `&shared_uc` (dev+ect). New jobs/pipeline are `*_${bundle.target}` | Pattern |
| Terminology-as-data | `src/terminology/*.csv` → `setup` job → BFS closures (`build_closure.py`) | `src/standards/life_sciences/*_subset.csv` → closures over MONDO, MED-RT classes, COSMoS BC | **Closure builder reused** |
| Data generation | Synthea → `epicize` → `care_behavior` (seeded) | **dbldatagen** EDC exports + injected named fixtures (ADR-0024) | Net-new |
| Pipeline | `src/pipelines/measures.py` (Lakeflow) → `silver_*`, `gold_adherence_*` | `src/pipelines/clinical_study.py` → SDTM-shaped silver, ADaM-shaped gold | Pattern |
| Rule engine | Measures in pipeline SQL; drift via `measure_drift_demo.sql` | Versioned engine over the approved rule registry. All candidates kept with reasons | Net-new |
| Gold oracle | `src/benchmark/gold_queries.sql` + `verify_gold.py` (`-- expect:`) | `src/benchmark/life_sciences/gold_queries.sql` + hand-authored expected outcomes | **verify_gold reused** (add `--suite`) |
| Semantic | Comments, 8 metric views in `care_protocol_semantic`, Domains script, Pages md | Comments, metric views in `clinical_study_semantic`, 12 Pages, Domains | Pattern + scripts |
| Genie | 4 bundle Genie spaces (`resources/*.geniespace.json`) | Study Analytics, Protocol Evidence, Standards & Semantics spaces | Pattern |
| Documents | `docs/care_protocol/{corpus,html,pdf}` → `stage_source_documents` | `docs/life_sciences/documents/{corpus,html,pdf}` (protocols, amendments, SAPs, mapping spec) | Renderer + stager reused |
| A4 RAG | Lakebase hybrid + doc-level RLS (`src/retrieval/lakebase/schema.sql`) | Same tables plus a `demo_id` column/filter. Study-level ACL | Extend |
| A5 graph | Ontobricks `clinicaldomain` (Eli-owned). TBox `src/ontology/care_protocol.owl.ttl` | New TBox + R2RML in `src/ontology/life_sciences/`. **Eli imports** | Pattern |
| A6 MCP | `src/mcp/care_protocol_tools.py` (`make_tools(catalog, schema, …)`) + supervisor | `clinical_study_tools.py` (bounded, no free-form SQL), scoped by `demo_id` | Pattern |
| Retrieval eval | `src/benchmark/retrieval_eval/` (providers, judges, closed_book floor) | Same harness, `--demo` flag, LS question set + deterministic checks | **Reused** |
| App | FastAPI + React. 3 mounted tabs (Tracer, Arena, Scorecard). DriftLab/OntologyExplorer unmounted | Demo switcher. Both demos get Tracer, Arena, Scorecard, **Drift/Amendment Lab**, **Ontology Explorer** + header strip | Extend |
| Config | `server/config.py`: single `CARE_SCHEMA` / Genie title / corpus | `DemoContext` per `demo_id`. Every route takes `demo` | Refactor |

## 2. Dependency map (life-sciences bootstrap job)

```
validate_environment
  └─ acquire_and_validate_standards (checksums vs manifest; cache in volume) ──┐
  └─ generate_synthetic_data (dbldatagen + fixtures) ─┐                         │
  └─ render_documents (md → html → pdf) ──────────────┼─ stage to volumes       │
                                                      ▼                         ▼
                                     load_standards + build_closures (MONDO, MED-RT, BC)
                                                      ▼
                         pipeline: bronze → silver (SDTM-shaped) → gold (endpoint engine, provenance)
                                                      ▼
                    data_quality_checks ─ verify_gold --suite life_sciences ─ expected-outcome fixtures
                                                      ▼
            semantic (comments, metric views) → genie spaces (bundle) → rag corpus (Lakebase) → smoke tests
                                     ⚙ manual: Pages import, Ontobricks import/publish, Domains if capped
```

## 3. Phases and status

Status vocabulary (kept strictly separate): **implemented** · **tested** · **deployed** · **blocked** · **manual action required**.

| Phase | Scope | Status |
|---|---|---|
| 1 Inspect & plan | Inventory, ontology gate, manifest, ADR-0021..0024, CLAUDE.md, customer-name removal | implemented |
| 2 Deterministic data path | dbldatagen generator + 20 fixtures, pipeline, endpoint engine v1/v2 + Study B, provenance, oracle | — |
| 3 Semantic path | Vendored subsets + closures, TBox/R2RML (USDM-aligned + `cpl:`), validation checks | — |
| 4 Documents & governed context | Protocol/SAP/amendment PDFs, parsing, candidate→approved registry, Pages | — |
| 5 Deployment & agents | Bundle resources, Genie spaces, MCP tools, RAG corpus, readiness tracking | — |
| 6 App | Demo switcher, `DemoContext` refactor, LS tabs, Drift/Amendment + Ontology Explorer for both | — |
| 7 Evaluation & hardening | LS benchmark (10 categories), HEDIS regression, isolation tests | — |
| 8 Demo package | Presenter script, architecture diagram, runbook, known limitations | — |

## 4. Fixed design choices for Phase 2 (illustrative rules, not any real protocol)

- **Study A (`CSL-A`):** 72-week metabolic study. Reference date = first exposure (`EX.EXSTDTC`, date precision). Target day 168. Baseline window: day −28 to day −1, **plus same-day records with a pre-dose time**. Baseline = last valid observation. A same-day record without a time is ambiguous and excluded with a reason.
  - **Rule v1:** follow-up window 168 ±7 days, inclusive. Pick the closest valid observation. Tie-breaker: the later date, then the lower `VSSEQ`.
  - **Rule v2 (Amendment 1):** window 168 ±14 days. Nothing else changes.
  - **Amendment 2:** adds sleep apnea to the weight-related-comorbidity class (G4).
- **Study B (`CSL-B`):** target day 182 ±10 days. Baseline = **mean of all valid pre-treatment values in the window**. Same Biomedical Concept, different definition, so the two studies can't be pooled automatically.
- **Endpoint:** `100 × (fu_kg − bl_kg) / bl_kg`, stored unrounded and rounded only for display. Units: LB/g/kg per the COSMoS DSS. Anything else is `unsupported_unit`.
- **Analysis population:** randomized ∧ ≥1 dose ∧ eligible (BMI ≥30, or BMI ≥27 + a comorbidity class member) ∧ no contraindicating MH (G2).
- **Day arithmetic:** `day = date − ref_date (+1 if ≥0)`, CDISC-style with no day 0. Simplified: it does not implement every study-day convention, and this is stated in the Known limitations page.

## 5. Manual actions (expected)

- ⚙ Ontobricks: create the life-sciences domain and import the TBox + R2RML, then publish (Eli, ADR-0005).
- ⚙ Pages: bulk import per workspace (no API) using `PAGES_IMPORT_PROMPT.md`.
- ⚙ Domains: ECT has hit the tag-policy cap, so the existing tag may need reuse (same as HEDIS).
- ⚙ MED-RT terms: confirm before external distribution (open item in the manifest).
