# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Databricks demo ("Care Protocol Context & Evidence Lab") that shows what **semantics, ontology, and a
context layer** add to HEDIS diabetes quality measures computed over **synthetic, Epic/Clarity-shaped data**.
Genie One is the front door. Several retrieval approaches ("arms") are benchmarked against a hand-verified
gold answer key, and there is record-level tracer traceability plus a measure-drift demo. All outputs are
labeled *Synthetic · HEDIS-aligned · Not NCQA-certified · Not for clinical use*.

The plan of record is `docs/UNIFIED_BUILD_ROADMAP.md`. Design decisions live as ADRs in `docs/decisions.md`,
and many code comments cite them (e.g. "ADR-0018"). Read the relevant ADR before changing behavior it governs.
Manual (⚙) and async-wait (⏳) steps are in `docs/RUNBOOK.md`.

## Workspaces, catalog, and bundle targets (the key constraint)

- **One shared UC catalog**, `eli_test_classic_catalog`, holds schemas `care_protocol` (medallion + base
  tables), `care_protocol_semantic` (metric views only, ADR-0013), and `care_protocol_terminology`.
- **Two workspaces read that catalog** (ADR-0018). `ect` (profile `ECT`) is the ontology-OFF baseline.
  `dmvm` (profile `DMVM`) is the ontology-ON arm. Genie Ontology can't be toggled. The variable being tested
  is the workspace snippet count: inferred snippets are only fetched above roughly 1,000.
- **Only `dev` and `ect` own the shared schemas and volumes**, through the `&shared_uc` anchor in
  `databricks.yml` (ADR-0019). Do not add `resources/schemas.yml`/`volumes.yml` to `include:`, and do not give
  `dmvm` those resources: its Terraform state would try to create, or later drop, the shared schemas.
- **Do not run the data jobs/pipeline on DMVM.** Their outputs already live in the shared catalog. DMVM only
  gets workspace-local assets: Genie spaces, dashboards, query-history seeding, and analytics notebooks.
- Always pass `--profile` explicitly. Never pick one automatically.

## Commands

```bash
# Bundle
databricks bundle validate -t ect --profile ECT          # or -t dmvm --profile DMVM
databricks bundle deploy   -t ect --profile ECT
databricks bundle run <job_key> -t ect --profile ECT     # job keys in resources/jobs.yml

# Python env (repo-root .venv; extras: dev, lakebase, eval)
pip install -e '.[dev]'        # ruff line-length = 110
ruff check .

# Tests (plain scripts that also run under pytest)
python3 -I tests/test_rag_corpus_build.py      # deterministic, no workspace
pytest tests/test_rag_corpus_build.py::test_patient_letter_is_care_team_restricted
python3 -I tests/test_rag_rls.py               # needs live Lakebase; skips if LAKEBASE_HOST unset

# Gold regression gate: every gold_queries.sql query must match its inline `-- expect:` value
python src/benchmark/verify_gold.py --warehouse_id <WH> --profile ECT

# Benchmark arms
python src/benchmark/run_capability_map.py --arm A1     # or --arm M0 (see src/benchmark/README.md)
PYTHONPATH=src DATABRICKS_CONFIG_PROFILE=TEST_SPN .venv/bin/python -m benchmark.retrieval_eval.run_retrieval_eval

# A6 MCP tools self-test against live data
python src/mcp/_selftest.py --profile ECT --catalog eli_test_classic_catalog

# Ad-hoc read-only SQL against ECT (dev helper)
.venv/bin/python scripts/q.py "SELECT ..." [--json]
```

### App devloop (`src/app`, FastAPI + React/Vite/Tailwind)

```bash
lsof -nP -iTCP:8011 -sTCP:LISTEN -t | xargs -r kill -9        # kill any stale backend first
cd src/app && DATABRICKS_PROFILE=ECT ../../.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8011
cd src/app/frontend && npm run dev                            # http://localhost:5180, proxies /api → :8011
cd src/app/frontend && npm run build                          # REQUIRED before bundle deploy (dist is gitignored
                                                              # but force-synced via databricks.yml sync.include)
```

Gotcha: FastAPI has a catch-all SPA route. If a stale backend still holds :8011, a new `/api/...` route
returns `index.html` instead of a 404, and the frontend shows `Unexpected token '<'`. There is no local `tsc`,
and `vite build` does not type-check.

## Build/data flow (bundle jobs, in order, on `ect`)

`setup` (load vendored terminology CSVs → `icd10_closure`/`rxnorm_closure` via iterative BFS) →
`generate_synthea` → `epicize` (SNOMED→ICD-10 crosswalk → `bronze_*` Clarity-shaped tables) →
`care_behavior` (seeded generative model: panels/PCP handoff → `care_order_*`, ADR-0012) and `ssd_cohort`
(synthesized SMI/antipsychotic cohort, ADR-0017) → `measures` (Lakeflow pipeline `src/pipelines/measures.py`
→ `silver_*`, `gold_adherence_{gsd,ked,bpd,spd,eed,mad,ssd}`, `gold_protocol_adherence`) → `semantic`
(column comments + 8 metric views) → `seed_query_history`.

- If any `src/terminology/*.csv` changes, rerun `setup` **first**. Otherwise the closures won't subsume the
  new nodes. Then reflow `epicize → measures → semantic`.
- The Genie space validates against the metric views. On first creation, deploy, then run `semantic`, then
  deploy again.
- Generators are deterministic (seeded) and idempotent. Changes that move a gold value must be caught by
  `verify_gold.py`, and `gold_queries.sql` / `docs/benchmark/ground_truth.yaml` must be updated deliberately.

## Retrieval arms (what's being compared)

| Arm | What | Where |
|---|---|---|
| A1 | Genie One (product front door), read headless via `databricks genie ask` | `src/benchmark/run_capability_map.py` |
| A2 | Genie Agent (LLM-generated SQL), from the vendored Genie GenAI Evals `.dbc` | `src/benchmark/run_benchmark.py`, `resources/*.geniespace.json` |
| M0 / metric_view | Governed `MEASURE()` over metric views | `src/semantic/metric_views/` |
| closure_sql | Fixed-shape SQL over closure/edge tables; also the gold answer key | `src/benchmark/gold_queries.sql` |
| A4 | Lakebase hybrid RAG (BM25 + vector) over the care-protocol corpus, with **document-level RLS** through a SECURITY DEFINER function (ADR-0014/0016) | `src/retrieval/a4_lakebase.py`, `src/retrieval/lakebase/schema.sql`, `scripts/lakebase_*.py` |
| A5 | Ontobricks OWL graph, published live (`eswanson_demo.ontobricks.triplestore_clinicaldomain_v2*`, ~55M triples) | `src/ontology/*.ttl` (TBox + R2RML), app `routes/ontobricks.py` |
| A6 | Supervisor + custom MCP: deterministic, reviewed tools with no free-form SQL | `src/mcp/` |

- The benchmark is a **capability map, not a leaderboard** (ADR-0010, `docs/BENCHMARK_CHARTER.md`). For each
  question class it records which approach is sufficient, adds value, or is necessary. Results are in
  `docs/benchmark/capability_map.md`.
- `src/benchmark/retrieval_eval/` holds one vanilla agent fixed and swaps the injected retrieval provider
  (`providers.py`), using `closed_book` as the floor. It scores with three MLflow GenAI judges: correctness,
  groundedness, and sufficiency. Necessity is measured as lift over closed_book. Every retrieving provider
  must emit an MLflow RETRIEVER span.
- **Ontobricks is Eli-owned (ADR-0005).** The repo only supplies the integration contract (the ontology/R2RML
  files and retrieval plumbing), so don't automate its deployment. The graph is live: query it to verify
  rather than assume.

## App architecture

- `src/app/app.py` mounts the routers in `server/routes/` under `/api` and serves `frontend/dist` as an SPA.
  Tabs are in `frontend/src/tabs/`.
- `server/config.py` handles dual-mode auth. Locally it uses the CLI profile in `DATABRICKS_PROFILE` (default
  ECT). Deployed as a Databricks App, it uses the ambient service principal. **No hardcoded endpoints:** the
  warehouse (by name), Genie space (by title), and Lakebase host (from the endpoint path) are all resolved at
  runtime, and environment-specific settings come from `CARE_*` env vars (`app.yaml`). Keep it that way so
  one build deploys to both workspaces.
- The app is **read-only** over the shared catalog. RLS on A4 stays on for the deployed SP.
- `server/benchmark_data/` contains copies of `docs/benchmark/` artifacts (e.g. `capability_matrix.csv`,
  `a1_runs/`). When you update one, update the other too.

## Content-as-code for the context layer

- Ontology Pages: `docs/ontology/pages/*.md`. `stage_pages` copies them to a UC volume, and then they are
  bulk-imported **manually** per workspace with `docs/ontology/PAGES_IMPORT_PROMPT.md`, because no API exists.
- Metric views: `src/semantic/metric_views/*.metric_view.sql`. Comments: `src/semantic/comments/*.sql`.
  Domains: `scripts/create_domains.py`, which is scripted and outside the DAB. ECT hit the tag-policy cap and
  reuses the `Clinical Domain` tag.
- Terminology covers free code systems only, vendored as curated subsets in `src/terminology/` (ADR-0002/0007).
  Never commit licensed LOINC/SNOMED raw content (see `.gitignore`).
