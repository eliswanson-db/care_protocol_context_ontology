# ECT capability matrix

Target: **ECT** (`fevm-eli-test-classic.cloud.databricks.com`). Mark AVAILABLE / MANUAL_SETUP / UNAVAILABLE.
Re-verify at P0 start (preview features move).

| Capability | Status | Evidence / note |
|---|---|---|
| Serverless compute | ✅ AVAILABLE | Serverless Starter Warehouse present |
| SQL warehouses | ✅ AVAILABLE | `genie_koans_wh` (running), `ontobricks_wh`, Serverless Starter |
| Lakebase (Postgres) | ✅ AVAILABLE | `databricks database …` (Public Preview) |
| Model Serving (LLMs) | ✅ AVAILABLE | Claude Opus/Sonnet/Haiku, GPT, Gemini, etc. |
| Embedding endpoints | ✅ AVAILABLE | `databricks-gte-large-en`, `bge-large-en`, `qwen3-embedding` |
| Terminology (LOINC/ICD-10/RxNorm) | ✅ VENDORED | curated subset in `src/terminology/` — no Drive (ADR-0007) |
| Ontobricks | 🟡 Eli-owned | `ontobricks_wh` exists; Eli sets up (ADR-0005) |
| Genie Ontology ON | ❓ VERIFY | confirm enabled before P7 seeding |
| Apps enabled | ❓ VERIFY | needed for P13 (and Ontobricks apps) |
| MLflow 3 GenAI eval | ❓ VERIFY | needed for P12 (notebook pins mlflow 3.17.2) |
| SNOMED/UMLS/VSAC | ⛔ NOT USED | no license; ADR-0002 (free terminologies only) |
