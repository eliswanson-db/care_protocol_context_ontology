# Retrieval-science eval (controlled-supervisor arm)

Scores **retrieval approaches**, not reasoners (the charter reframe, ADR-0020). It holds **one fixed vanilla
agent** (`agent.py`) constant and varies the **injected retrieval approach** (`providers.py`) one component at
a time, with `closed_book` as the floor. This is the complement to the Genie-One *product* arm: Genie One
answers end-to-end (and we read its attribution from `system.access.audit` → `genieChat.mcpToolInvocation`),
while this arm isolates *what each retrieval approach contributes in the absence of any other context*.

## The three judges (MLflow GenAI)

| judge | question it answers | how |
|---|---|---|
| **correctness** | Did this approach's context let the agent reach the hand-verified gold? | `is_correct(expected_facts)` |
| **groundedness** | Was the answer actually built from the retrieved context (vs. parametric knowledge)? | `meets_guidelines(answer ⊆ documents)` |
| **sufficiency** | Did retrieval even surface enough to answer? | `meets_guidelines(documents ⊨ facts)` |

**Necessity** is not a fourth judge — it falls out as **correctness lift over `closed_book`**. An approach is
*necessary* for a question when closed-book misses and adding that approach's context flips it to correct.

## Arms (`providers.py`)

- `closed_book` — no retrieval. The parametric-knowledge floor.
- `metric_view` — governed `MEASURE()` over a metric view (build-time resolution).
- `closure_sql` — fixed-shape SQL over the closure/edge tables; reuses the hand-verified `gold_queries.sql`.
- `rag` — A4 Lakebase hybrid passages over the care-protocol corpus (same retriever the RAG-MCP exposes to
  Genie One, so both arms call identical retrieval). Best-effort from local (doc-RLS / Lakebase Search); the
  arm reports degraded mode rather than failing the run.
- `ontobricks` — A5 graph arm: **entity-linked subgraph retrieval** against the published, live triplestore
  `eswanson_demo.ontobricks.triplestore_clinicaldomain_v2_graph` (~55M triples). **Eli owns the modeling
  (ADR-0005); this is only the retrieval plumbing.** It links the question's clinical terms to IRI *nodes* (a
  synonym→node lexicon — the standard graph-RAG NER/EL layer, pointing at entities not answers), then returns
  their typed 1-hop neighbourhood (the cross-vocab guideline/structural edges, then a small sample of patient
  membership edges) — the same traversal shape the app's `routes/ontobricks.py` uses. Point it elsewhere with
  `CARE_ONTOBRICKS_{CATALOG,SCHEMA,TABLE}`. Consequence, by design: the graph reaches typed PATHS and cross-vocab
  DEFINITIONS but NOT aggregate COUNTS (a retrieved triple set isn't aggregated — that's `closure_sql`'s job).

Every retrieving arm emits an MLflow **RETRIEVER span** so groundedness and sufficiency can read the documents
back off the trace. `closed_book` emits none (grounding is N/A by design).

## Run

```bash
# from the repo root; TEST_SPN = the ECT workspace SP
PYTHONPATH=src DATABRICKS_CONFIG_PROFILE=TEST_SPN \
  .venv/bin/python -m benchmark.retrieval_eval.run_retrieval_eval
```

Scored set = 9 questions chosen to exercise every arm's lift AND its blind spot, incl. the graph-native class 8
(rationale path, defined-class) where the graph should be the only arm to reach, and the aggregate-COUNT classes
where a triple neighbourhood should NOT. Output: the capability matrix (correctness per arm × question) + the
lift-over-closed-book table, and `docs/benchmark/retrieval_eval.json`. The remaining graph-claimed matrix
questions are scored ontobricks-only by `scripts/score_graph_remaining.py` →
`docs/benchmark/retrieval_eval_graph_remaining.json`. The measured graph verdicts feed
`docs/benchmark/capability_matrix.csv` (see `docs/benchmark/GRAPH_EVAL_RESULTS.md`).

Env knobs: `CARE_AGENT_MODEL` (default `databricks-claude-sonnet-5`), `CARE_JUDGE_MODEL`
(`databricks:/databricks-claude-sonnet-5`), `CARE_EVAL_EXPERIMENT`, `CARE_RAG_AS_USER` (seeded RLS reader).
