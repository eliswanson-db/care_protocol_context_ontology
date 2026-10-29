# RUNBOOK — manual (⚙) and async-wait (⏳) steps

Ordered operational steps that are **not** automated by the bundle. Keep this current as phases land.

## P0 — setup
1. ⚙ **Auth** — `databricks auth login https://fevm-eli-test-classic.cloud.databricks.com --profile ECT` (already valid).
2. ⚙ **Capability gate** — confirm on ECT and record in `capability-matrix.md`: **Genie Ontology ON**,
   **Apps enabled**, MLflow 3, Lakebase, Model Serving + embedding endpoint, Genie Agent API.
3. 🤖 **Schemas + volume are declarative** (`resources/schemas.yml`, `resources/volumes.yml`) — created by
   `databricks bundle deploy -t ect --profile ECT`. The catalog pre-exists (ECT Default Storage blocks SQL
   catalog creation — ADR-0001).
4. 🤖 **Run the setup jobs (all bundle-managed — no ad-hoc SQL):**
   - `bundle run setup -t ect` → `load_terminology` (vendored CSVs → UC tables, no Drive, ADR-0007) → `build_closure` (iterative BFS → `icd10_closure`).
   - `bundle run generate_synthea -t ect` → classic job: stage pinned Synthea JAR to the Volume → run Synthea → `raw_synthea_*` tables.
   - `bundle run epicize -t ect` → SNOMED→ICD-10 crosswalk → `bronze_*` Clarity-shaped tables.

## Terminology — NO license wait (ADR-0002)
- No SNOMED/UMLS/VSAC. Curated LOINC + ICD-10-CM + RxNorm subsets **vendored in `src/terminology/`** (no Drive) + hand-curated demo value sets.

## Ontobricks (A5) — Eli-owned, do NOT automate (ADR-0005)
- ⚙ Eli deploys/configures Ontobricks (UI + `mcp-ontobricks`) with his own instructions; `ontobricks_wh` exists.
- 🤖 The build only supplies the **integration contract**: the Gold + terminology tables the ontology maps
  (R2RML targets), and the MCP tools the benchmark/app call. Capture this when Eli is ready.

## ⏳ Async waits (verify, don't assume)
| Wait | When | Verify by |
|---|---|---|
| Lakebase / Model Serving provisioning | P8/P11 | endpoint/instance READY |
| DLT pipeline first run | P2/P3 | run success; row counts |
| **Genie Ontology extraction** | P7 | Genie One answers **cite** Pages/metric views ("Ontology References") |
| Lakebase BM25 index build | P8 | index status; test query |

## Genie Ontology seeding (P7 / §7a)
- Build Pages + metric views + Genie Agents + dashboards (over-build — see roadmap §7a), assign Domains,
  certify. Run the query-history seeding job on a schedule. Trigger early; build other arms while it extracts.
