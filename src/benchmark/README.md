# benchmark/ — Genie GenAI Evals (starting point for P12)

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
