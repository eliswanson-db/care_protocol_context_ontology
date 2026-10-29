# src/ layout

Build code, organized by the roadmap phases (`docs/UNIFIED_BUILD_ROADMAP.md`).

| Dir | Phase | Purpose |
|---|---|---|
| `data_generation/` | P1 | Synthea → "Epic-ize" into Clarity-shaped Bronze tables + synthetic docs + tracers |
| `pipelines/` | P2/P3 | Lakeflow medallion + the deterministic, versioned measure engine; Gold + provenance |
| `terminology/` | P2 | Loaders: LOINC (+Parts), ICD-10-CM (+hierarchy), RxNorm, hand-curated demo value sets |
| `semantic/` | P4/P5 | `metric_views/` · `comments/` · `pages/` · `domains/` — the governed context layer |
| `genie/` | P6 | Genie Agent configs (DAB JSON) — Quality / Clinical Evidence / Terminology + ablation |
| `retrieval/lakebase/` | P8 | Hybrid (BM25 + vector) search over documents |
| `retrieval/mcp_custom/` | P10 | Bounded read-only MCP tools |
| `retrieval/ontobricks/` | P9 | Integration contract only — Ontobricks itself is Eli-owned (ADR-0005) |
| `benchmark/` | P12 | `hedis_eval` harness + the vendored Genie GenAI Evals notebook (A2 seed) |
| `app/` | P13 | The demo app (tabs) — reuse-vs-net-new pending (ADR-0003) |
