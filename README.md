# Care Protocol Context & Evidence Lab (HEDIS / Ontology)

A Databricks demo showing the value of **semantics, ontology, and a context layer** for HEDIS diabetes
quality measures computed from synthetic, Epic-(Clarity-)shaped data — with **Genie One** as the front
door, multiple benchmarked retrieval approaches, record-level traceability, and a measure-drift demo.

> **Status:** scaffolding. Plan of record: [`docs/UNIFIED_BUILD_ROADMAP.md`](docs/UNIFIED_BUILD_ROADMAP.md).
> **Target workspace:** `ECT` (`fevm-eli-test-classic`, serverless). **Catalog:** `care_protocol_ontology`.
> **Label on all outputs:** *Synthetic · HEDIS-aligned · Not NCQA-certified · Not for clinical use.*

## Quick start

```bash
databricks bundle validate -t dev --profile ECT      # validate the bundle
databricks bundle deploy   -t ect --profile ECT      # deploy to ECT (later phases)
```

## Layout

```
databricks.yml            DAB: bundle, variables, targets (dev / ect)
resources/                DAB resource definitions (pipelines, jobs, apps, dashboards)
src/
  data_generation/        Synthea → "Epic-ize" into Clarity-shaped tables
  pipelines/              bronze → silver → gold + deterministic measure engine
  terminology/            loaders: LOINC (+Parts), ICD-10-CM (+hierarchy), RxNorm, demo value sets
  semantic/               metric_views · comments · pages · domains  (the context layer)
  genie/                  Genie Agent configs (DAB JSON)
  retrieval/              lakebase (hybrid) · mcp_custom · ontobricks (Eli-owned)
  benchmark/              hedis_eval harness + vendored Genie GenAI Evals notebook (A2 only)
  app/                    the demo app (tabs: quality, tracer, arena, drift, ontology…)
context/                  versioned context package + release manifest
tests/                    tracer-expectation + metric-parity tests
docs/                     roadmap, critical analysis, architecture diagram, ADRs, runbook
scripts/                  preflight/doctor, reset, replay
```

## Key docs

- [`docs/UNIFIED_BUILD_ROADMAP.md`](docs/UNIFIED_BUILD_ROADMAP.md) — the 16-phase build plan.
- [`docs/decisions.md`](docs/decisions.md) — ADRs (workspace, terminology, app, benchmark, scope).
- [`docs/RUNBOOK.md`](docs/RUNBOOK.md) — manual (⚙) and async-wait (⏳) steps.
- [`docs/architecture/architecture_diagram.svg`](docs/architecture/architecture_diagram.svg) — architecture.
- [`docs/CRITICAL_ANALYSIS_THREE_APPROACHES.md`](docs/CRITICAL_ANALYSIS_THREE_APPROACHES.md) + [`docs/sources/`](docs/sources/) — how the plan was derived.

## Terminology & licensing

Free code systems only — **no SNOMED/UMLS/VSAC required** (see ADR-0002): **LOINC 2.83**, **ICD-10-CM**,
**RxNorm**, plus hand-curated *demo* value sets. Terminology is staged into a UC Volume at runtime and
**never committed** (see [`context/terminology/LICENSES.md`](context/terminology/LICENSES.md)).
