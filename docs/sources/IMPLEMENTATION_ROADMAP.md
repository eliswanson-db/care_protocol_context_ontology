# Implementation Roadmap — Care Protocol Context Layer Demo (HEDIS / Epic)

**Owner:** Eli Swanson (Databricks SA, Field Engineering)
**Asset type:** Reusable HLS vertical demo — semantic/context layer, ontology, retrieval benchmark
**Promo signal:** High. Reusable field asset + competitive differentiation (semantic layer vs. Snowflake/Fabric) + multi-product surface (Genie One, metric views, Lakebase, MCP, Agent Bricks, MLflow eval, Ontobricks, Apps). Worth doing well; worth *scoping* well.
**Companion docs:** `DOMAIN_CONTEXT_PACK.md` (domain + platform facts), `CODING_AGENT_PROMPT.md` (the kickoff prompt).

---

## How to read this roadmap

Each phase has: **Goal · Tasks · Databricks tooling (skills) · Done when · Promo/WLB note.**
The dependency spine is linear (data → semantic layer → retrieval paths → benchmark → app),
but phases 2b–2e (the retrieval paths) are **parallelizable** once Gold exists.

**MVP line is after Phase 5.** Phases 6–7 (Ontobricks + full ablation/drift polish) are the
differentiators but also the risk; if time/energy runs short, a credible demo stops at Phase 5
with 3 of 5 paths. Don't let the stretch sink the core.

**WLB guardrail:** this is ~a multi-week build. Do not attempt in one sitting. The natural
checkpoints below are also natural stop points. If a day's plan exceeds 3 focuses, cut to the
critical path (data → Genie semantic layer → app lineage tab → one benchmark run).

---

## Phase 0 — Decisions & scaffolding *(half day)*

**Goal:** Remove ambiguity before any code; stand up the repo skeleton.

**Tasks**
- Confirm with Eli (see "Open decisions" at bottom): target **profile**, **catalog.schema**,
  SQL Warehouse, whether to reuse an existing HLS workspace (`newhls`?), Lakebase availability,
  Ontobricks deploy appetite, and scope (MVP 3 paths vs. all 5).
- Create repo layout:
  ```
  care_protocol_context/
    terminology/        # LOINC/SNOMED/RxNorm/CVX subsets + LICENSES.md
    data_generation/    # synthetic Epic-shaped data
    pipelines/          # bronze→silver→gold (Lakeflow Declarative Pipelines)
    semantic_layer/     # metric views YAML, UC comments/synonyms scripts, measure config
    retrieval/
      genie/            # Genie Agents + Genie One config
      unstructured/     # Lakebase hybrid search
      mcp_custom/       # custom MCP server
      ontobricks/       # Ontobricks deploy config + ontology (OWL/R2RML)
    benchmark/          # MLflow eval notebook + gold question set
    app/                # forked hospital control tower (+ new tabs)
    resources/          # DAB resource definitions
    databricks.yml  variables.yml  README.md
  ```
- Initialize DAB (`databricks-dabs`), wire `variables.yml` (catalog, schema, warehouse_id, lakebase, endpoints).

**Tooling:** `databricks-core` (auth/profile), `databricks-dabs`.
**Done when:** `databricks bundle validate --profile <chosen>` passes; decisions recorded in README.
**Promo/WLB:** Front-load decisions so later phases don't stall on "which catalog?".

---

## Phase 1 — Terminology + synthetic data *(2–3 days)*

**Goal:** A believable Epic-shaped lakehouse with the terminology backbone and *deliberate* defects.

**Tasks**
- Load curated **LOINC / SNOMED / RxNorm / CVX / ICD-10** subsets to `terminology.*`
  tables + `LICENSES.md` (see Context Pack §3 — ask before downloading licensed content).
- Load/author public **CMS eCQM value sets** (CMS122, CMS165) and the diabetes measure
  value sets from VSAC; store as `value_sets` tables keyed for the measure config.
- Generate **Bronze** synthetic Epic data (Clarity/Caboodle-shaped — Context Pack §4), a few
  thousand patients, with the four seeded defects (missing LOINC map, PDF-only eye exam,
  SNOMED-child diabetes patient, split albumin/creatinine pair).
- Generate the protocol **PDFs** for the unstructured path: ADA-style summary, a VA/DoD-style
  flowchart, and a synthetic "local health system diabetes pathway" (so it's legal to ship).

**Tooling:** `databricks-synthetic-data-gen` / `databricks-data-generation`, `databricks-unity-catalog`.
**Done when:** Bronze tables + terminology + value sets queryable; the five golden-thread patients
(Context Pack §6) exist with their intended quirks; a one-page data dictionary is written.
**Promo/WLB:** The seeded defects *are* the demo. Don't ship clean data — the defects create the path differences.

---

## Phase 2 — Bronze→Silver→Gold adherence pipeline *(3–4 days)*

**Goal:** The adherence event log — the single source of truth every path and the benchmark agree on.

**Tasks**
- **Silver:** conform local codes → LOINC/RxNorm/SNOMED/CVX via `clarity_component` crosswalk;
  disambiguate timestamps (specimen-collected vs. order vs. result vs. MAR). Model the
  unmapped-LOINC and flowsheet-not-mapped gaps explicitly.
- **Measure config:** load the step definitions (Who→What→When→Evidence→Exceptions, research §8.5)
  as a UC table driven by `value_sets`. Implement value-set expansion including **SNOMED
  subsumption** (descendants of the diabetes concept) — this is what makes the ontology story true.
- **Gold:** build the adherence event log (research §8.4 schema) + HEDIS-aligned numerator/
  denominator rollups for GSD, BPD, KED, EED, SPD. KED must implement the compound all-of/any-of/
  ≤4-days logic.
- Author as a **Lakeflow Declarative Pipeline** (`databricks-pipelines`) so re-materialization
  (for drift) is one command.

**Tooling:** `databricks-pipelines`, `databricks-ai-functions` (ai_parse_document for PDFs if
landing extracted fields), `databricks-unity-catalog`, `databricks-serverless`.
**Done when:** Gold event log reconciles to hand-computed numerators for the 5 golden-thread
patients; the Protocol-vs-HEDIS reconciliation quadrant (research §8.7) is reproducible.
**Promo/WLB:** This is the backbone — get it *correct* before building five things on top. Natural stop point.

---

## Phase 3 — The Databricks-native semantic layer *(2–3 days)*

**Goal:** The context layer that makes Genie good — and that we can ablate.

**Tasks**
- **Metric views** (`databricks-metric-views`): GSD/BPD/KED/EED/SPD as governed rates with
  dimensions (PCP, department, payer, demographics for the equity view).
- **UC enrichment:** table/column **COMMENT**s (clinically meaningful), **synonyms**
  (A1c/HbA1c/glycohemoglobin; uACR/microalbumin; eGFR/kidney function), **certified** tags,
  **PK/FK constraints**, business glossary.
- Make each context component a **toggle** (comments, synonyms, metric-views-vs-raw,
  Genie instructions, value-set/ontology expansion) so the ablation in Phase 6 is a config flip.

**Tooling:** `databricks-metric-views`, `databricks-unity-catalog`, `databricks-data-discovery`.
**Done when:** Metric views return correct rates; UC objects carry comments/synonyms/constraints;
toggles are parameterized.
**Promo/WLB:** This phase *is* the thesis. The ablation chart that comes out of it is the most reusable slide.

---

## Phase 4 — Retrieval paths 1–3 (Genie front door) *(3–4 days)*

**Goal:** Genie One as front door over a rich Genie Agent (path 1), the unstructured path (path 2),
and composed per-domain Genie Agents (path 3).

**Tasks**
- **Path 1 — Genie Ontology:** a Genie Agent over Gold + metric views, loaded with curated
  instructions, SQL examples, and the semantic-layer context. (`databricks-genie-agents`)
- **Path 2 — Lakebase hybrid:** parse protocol PDFs (`ai_parse_document`), chunk, load to
  **Lakebase** with `pgvector` + full-text; implement hybrid search + a thin retrieval agent.
  (`databricks-lakebase`)
- **Path 3 — Genie Agents via Genie One:** split into per-domain curated Genie Agents; compose
  under Genie One / **Agent Bricks** multi-agent supervisor. (`databricks-agent-bricks`)
- Front-door: wire **Genie One** (`databricks-data-discovery`) as the conversational entry.

**Tooling:** `databricks-data-discovery`, `databricks-genie-agents`, `databricks-agent-bricks`,
`databricks-lakebase`, `databricks-ai-functions`.
**Done when:** Each path answers the gold question set end-to-end and returns citations/evidence.
**Promo/WLB:** **MVP demo is viable here** (3 paths + app). Paths 4–5 are differentiation, not prerequisites.

---

## Phase 5 — Retrieval paths 4–5 (MCP + Ontobricks) *(3–5 days, stretch-ish)*

**Goal:** The two MCP paths — custom deterministic retrieval and the knowledge-graph path.

**Tasks**
- **Path 4 — Custom agent via MCP:** MCP server exposing adherence-log + measure-step tools
  (e.g. `get_measure_status(patient, measure)`, `expand_value_set(measure)`); host as a Databricks
  App or via Unity Gateway MCP. Deterministic, fully traceable. (`databricks-model-serving`,
  `databricks-unity-gateway`)
- **Path 5 — Ontobricks:** deploy `databrickslabs/ontobricks` (its own App; `uv sync --extra
  lakebase`, SQL Warehouse + Lakebase + UC Volume). Author the OWL ontology (Patient, Measure,
  MeasureStep, ValueSet, Observation, LabTest; object properties hasEvidence/satisfiesStep/
  mappedToLOINC/isa-SNOMED), **R2RML** map to Gold + terminology, SHACL validate, publish as MCP.
  Use SNOMED is-a for the subsumption demo.

**Tooling:** `databricks-unity-gateway`, `databricks-model-serving`, `databricks-lakebase`,
Ontobricks (external labs repo — deploy, don't rebuild).
**Done when:** Both MCP paths callable head-to-head on the gold set; the subsumption question
(golden-thread `P-003901`) is answered correctly by path 5 and demonstrably missed by a naive path.
**Promo/WLB:** Highest-risk, highest-differentiation. Timebox Ontobricks deploy; if it blocks, ship
paths 1–4 and add 5 later. Don't burn a weekend fighting someone else's deploy.

---

## Phase 6 — Benchmark harness + ablation *(2–3 days)*

**Goal:** The credible numbers — path comparison and per-context-component impact.

**Tasks**
- Author the gold question set (~30–60 Qs, tagged by measure / difficulty / requires-ontology /
  requires-unstructured / requires-compute) with reference answers + expected codes.
- **MLflow 3 eval** (`databricks-mlflow-evaluation`): LLM-judge correctness + faithfulness, plus
  a **custom exact scorer** vs. Gold ground truth (the number execs will trust). Latency/cost from traces.
- **Ablation runs:** sweep the Phase 3 toggles; tag runs by context config; produce the
  "impact of each context component" chart.
- Write results to a Delta table the app reads; enable MLflow tracing on every path call.

**Tooling:** `databricks-mlflow-evaluation`, `databricks-jobs`.
**Done when:** One MLflow experiment ranks the 5 paths per question-type; ablation shows monotonic
degradation as context is removed; results table populated.
**Promo/WLB:** Deliver *one* honest benchmark run before polishing. Resist infinite question-set expansion.

---

## Phase 7 — The app: lineage, benchmark, drift tabs *(4–5 days)*

**Goal:** The visual payoff — trace specific items, compare paths, trigger drift.

**Tasks** (fork + extend `hopital_control_tower` — React/Vite + Flask + DABs)
- Point the **chat** at Genie One.
- **Golden Thread / Lineage tab:** select a golden-thread item → visualize Bronze→Silver→Gold→
  metric view→value set→ontology node; show all 5 paths' answers side-by-side (answer, latency,
  cost, citations, which context components fired). Replay a real MLflow trace.
- **Retrieval Benchmark tab:** read the results table; render the path ranking + ablation chart.
  Use the `dataviz` skill for chart design.
- **Measure Drift tab:** a button that triggers the eGFR-code-migration config change → re-run
  pipeline + metric views + Ontobricks sync + benchmark → before/after diff (which patients
  flipped, how each path's answer changed, elapsed time/step count).
- Deploy via DAB; UI-test with the web dev-loop tester / Chrome DevTools.

**Tooling:** `databricks-apps` / `databricks-apps-python`, `databricks-app-design`, `dataviz`,
`fe-specialized-agents:web-devloop-tester`, `databricks-dabs`.
**Done when:** A reviewer can, unaided, pick a patient, see it flow through all 5 paths, read the
benchmark, and hit "drift" to watch the semantic layer update live.
**Promo/WLB:** This is where the demo becomes *showable*. Keep the three tabs; resist scope creep into a product.

---

## Phase 8 — Narrative, docs, dry-run *(1–2 days)*

**Goal:** It demos itself.

**Tasks**
- A `README` demo script: the 10-minute path (question → 5 answers → benchmark → drift) and the
  2-minute exec version.
- The reusable slides: the context-component ablation chart, the path-comparison table, the
  Protocol-vs-HEDIS reconciliation quadrant, the drift timer.
- One-command stand-up (`./setup.sh dev`-style) + teardown; label everything "HEDIS-aligned,
  synthetic, not NCQA-certified."
- Full dry run against a clean workspace.

**Done when:** A peer SA can stand it up and run the script from the README alone.

---

## Critical path (if you must compress)

`Phase 0 → 1 → 2 → 3 → (Path 1 Genie) → (app Lineage tab, 1 benchmark run) → drift`.
That's a real demo with the semantic-layer thesis intact. Everything else is additive.

## Risks & gotchas

- **Ontobricks deploy friction** (labs project, community-supported) — timebox; have a path-1–4 fallback.
- **Genie capability drift** — verify current Genie One / Genie Agents behavior via the skills; don't code from memory.
- **Lakebase availability** in the chosen workspace — confirm in Phase 0; if absent, Vector Search is the fallback for path 2 (note the substitution).
- **Terminology licensing** — the single biggest "gets the asset killed" risk. Obey Context Pack §3.
- **Measure correctness** — HEDIS logic is fiddly (timestamps, exclusions). The custom exact scorer in Phase 6 is your safety net; reconcile Gold to hand-computed numbers in Phase 2.
- **Scope creep** — five paths × five measures × ablation × three app tabs is a lot. The MVP line and critical path exist to protect WLB and promo focus; use them.

## Open decisions for Eli (confirm at kickoff)

1. Databricks **profile** + **catalog.schema** + SQL Warehouse? (`newhls` the right workspace?)
2. Is **Lakebase** available there (path 2 + Ontobricks need it)? Fallback to Vector Search ok?
3. **Scope:** MVP (paths 1–3) first, or commit to all 5 now?
4. Appetite to deploy **Ontobricks** (external labs App) vs. defer path 5?
5. Any existing HLS synthetic dataset to reuse, or generate fresh?
6. Where does this get *shown* (internal enablement, specific customer, conference)? Shapes the narrative.
