# benchmark/ — capability map + Genie GenAI Evals

## Capability-map gold layer (the answer key + closure_sql arm)

The serious benchmark is a **capability map** (ADR-0010, `docs/BENCHMARK_CHARTER.md`), not a leaderboard:
for each class of hard clinical question, *which context/retrieval approach is sufficient / adds value /
necessary, and why*. The question set and hand-verified expected answers live in
`docs/benchmark/ground_truth.yaml` (classes 1–9).

- **`gold_queries.sql`** — one hand-verified query per question id (classes 1–6, SQL-computable), with its
  `-- expect:` value inline. This file is **two things at once**: the ground-truth *answer key*, and the
  **`closure_sql` arm** reference (fixed-shape SQL over the materialized closure/edge tables —
  `icd10_closure`, `loinc_parts`, `rxnorm_closure`, `value_set_segment`, `protocol_edges`). Class 7 (RAG over
  the PDF/Pages) and class 8 (Ontobricks graph) are not scalar SQL golds and are not here; class 9
  (operational/temporal root-cause) is the ADR-0012 care-behavior hero signal.
- **`verify_gold.py`** — runs every `gold_queries.sql` query on a warehouse and asserts each result matches
  its `-- expect:`. A reproducible **regression gate** (catches a reflow/crosswalk/schema change that moves a
  gold value) and the runnable closure_sql arm. All 13 pass at 25k on `ect` (verified 2026-10-30, post the
  ADR-0012 regen): `python src/benchmark/verify_gold.py --warehouse_id <WH> --profile ECT`.

The other arms (Genie One A1, metric-view-only M0, Lakebase RAG A4, Ontobricks A5) are scored *against* this
gold as they come online; their columns in the capability-map matrix fill in per class.

## Genie GenAI Evals (starting point for P12)

## What this is

`Genie GenAI Evals.dbc` — an MLflow 3 `mlflow.genai.evaluate()` harness that evaluates **one Genie Agent
(space)** against ground truth, with full MLflow tracing. Authored by Eli; already run on an FEVM
workspace. Import it into a Databricks workspace (Workspace → Import → `.dbc`), set the widgets, Run all.

It evaluates a Genie Agent in **two modes**:
- **chat** — the Conversation API (`/api/2.0/genie/spaces/{space_id}/...`)
- **agent** — Genie **Research** / deep mode (streaming Responses API, `/api/2.0/genie/agents/{space_id}/responses`)

### ⚠️ Scope: Genie **Agents** only — NOT Genie One

Both modes above are the **Genie Agent** surface. This notebook does **not** evaluate **Genie One**, the
unified front-door experience over spaces + the ontology. In this project's benchmark that means:

| Arm | Surface | Covered by this notebook? |
|---|---|---|
| **A2** | Genie **Agent** (space), chat + Research modes | ✅ yes — this is exactly what it does |
| **A1** | **Genie One** (front door) | ❌ no — needs a separate `predict_fn` (e.g. against Genie One MCP); reuse this notebook's *scorer + tracing pattern*, not its callers |
| A4 / A5 / A6 | Lakebase hybrid / Ontobricks / supervisor + custom MCP | ❌ not yet — extend `predict_fn` + the scorer registry (see roadmap P12) |

## How it scores (the epistemics worth reusing)

- Ground truth = the space's own **benchmarks** (SQL executed live) + optional hand-written cases.
- **`sql_result_match`** — compares Genie's **result rows**, never SQL text, with numeric tolerance. This
  is the deterministic oracle. (Applies only to arms that return result rows — doc/graph arms need a
  fact/patient-set scorer instead, and a correct refusal must not be penalized.)
- Deterministic: `genie_completed`, `latency_sla`, `citations_valid` (agent mode).
- LLM judges: `correctness`, `groundedness` (one RETRIEVER span), `analytic_clarity`; optional `relevance`, `safety`.
- **canary** deliberately-wrong cases prove the scorers actually catch errors.
- Full MLflow tracing (span per Genie state/tool), per-space experiment, cross-run history.

## Pinned dependencies (verify in-workspace)

`mlflow[databricks]==3.17.2`, `databricks-sdk==0.157.0`.

## Role in this project

This is the **seed for P12** (see `../UNIFIED_BUILD_ROADMAP.md` §0a① and P12):
1. Repoint `space_id` + cases at the HEDIS **Genie Agents** → gets the **A2** arm immediately.
2. Write a **new caller** for **A1 (Genie One)** reusing the scorer/tracing pattern (confirm what Genie
   One exposes headlessly at the P0 capability gate first; evaluate observationally + label if it can't
   be driven programmatically).
3. **Extend** `predict_fn` + the scorer registry for **A4/A5/A6**.

> Provenance: exported from a Databricks workspace by Eli. No SLA — treat as a reusable internal asset,
> pin versions, verify before relying on it.

## `run_benchmark.py` — the committed, bundle-run A2 harness (live now)

A lightweight, fully code-reproducible benchmark that complements the `.dbc` notebook (which stays the
richer MLflow-3 / LLM-judge harness). Run it with the bundle:

```bash
databricks bundle run benchmark -t ect --profile ECT
```

- **Question set:** `benchmark_questions.json` — ground-truth Q&A for all 5 measures (expected value +
  expected governed asset).
- **What it does:** starts a Genie **Agent** conversation per question (`w.genie.start_conversation_and_wait`
  on the `genie_spaces.care_protocol_agent` space id, wired via `${resources...id}` in `resources/jobs.yml`),
  then scores two things:
  - **`answer_accuracy`** — the expected value appears in the agent's text answer.
  - **`asset_grounding`** — the agent's generated SQL references the expected metric view / gold table.
- **Logs to MLflow** (experiment `/Users/eli.swanson@databricks.com/care_protocol_benchmark`): `answer_accuracy`,
  `asset_grounding`, `avg_latency_s`, and a per-question results table, in a run tagged by `approach`.
- **Adding arms:** run again with a different `--approach` (and a different caller for A1/A4/A6) to get a
  second MLflow run in the same experiment for side-by-side comparison. A2 is wired today.
