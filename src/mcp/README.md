# A6 — Supervisor + custom MCP (governed tools)

The A6 arm answers questions by routing to **trusted, deterministic tools** over the governed semantic
layer, rather than letting an LLM generate SQL (A2). This is the "context layer as tools" differentiator.

## Pieces
- **`care_protocol_tools.py`** — the governed tools. Each is a fixed, reviewed query over the semantic layer
  (metric views, Gold, subsumption closures, value sets). Pure functions taking a `query(sql)->rows`
  callable, so they run against any executor (warehouse, Lakebase, `aitools`). No LLM, no free-form SQL.
  Tools: `get_measure_rate`, `diabetes_cohort_size`, `subsumption_expand`, `resolve_value_set`, `list_care_gaps`.
- **`supervisor.py`** — pure-Python router: maps a question to a tool by intent, or defers to Genie (A2) for
  open-ended analysis. `answer()` executes; `summarize()` renders a one-line answer.
- **`server.py`** — FastMCP server exposing the tools over MCP (Statement Execution API against a SQL
  warehouse). Deploy as a Databricks App; or `python src/mcp/server.py` for stdio.
- **`_selftest.py`** — routes sample questions against live data via `aitools query` (proves correctness).

## Verify locally
```bash
python src/mcp/_selftest.py --profile ECT --catalog eli_test_classic_catalog
# GSD 86.7% / SPD 25.6% / cohort 56 / KED 25 gaps / E11->10 codes / SPD_STATIN 6 codes / Genie fallback
```

## Why A6 vs A2
A2 (Genie Agent) generates SQL with an LLM — flexible, but can misroute (see the benchmark's cohort-count
miss). A6 trades flexibility for **determinism and auditability** on the questions the ontology covers: the
tool's query is fixed and reviewed, so `get_measure_rate("GSD")` is always right. The supervisor hands
everything else to Genie, so coverage is a superset. The benchmark (`src/benchmark/`) runs the same
question set through A6 as a separate MLflow run (`--approach A6_supervisor_mcp`) for side-by-side comparison.

## Deploy as a Databricks App (MCP over HTTP)
`requirements.txt` here pins `mcp` + `databricks-sdk`. Scaffold/host via the `databricks-apps` skill;
set `DATABRICKS_WAREHOUSE_ID` and `CARE_CATALOG` in the app env, and grant the app SP `SELECT` on the
care_protocol + care_protocol_terminology schemas. (App deployment is the remaining manual step for A6.)
