# Unified Build Roadmap — HEDIS Context & Evidence Lab

**Date:** 2026-10-29 · **Target:** a reproducible, demoable Databricks demo on an **FEVM serverless workspace**
**Supersedes for execution:** the three source plans in `planning/sources/`
(`PROMPT_AND_ROADMAP_FROM_GENIE_ONE.md`, `PROMPT_AND_ROADMAP_FROM_PERPLEXITY.md`, and this session's
`IMPLEMENTATION_ROADMAP.md` + `DOMAIN_CONTEXT_PACK.md` + `CODING_AGENT_PROMPT.md`); analysis in
`planning/CRITICAL_ANALYSIS_THREE_APPROACHES.md`. Architecture picture: `diagrams/architecture_diagram.(svg|png)`.

---

## 0. Design tenets (hold all four at once)

1. **Epistemically correct** — the measure **engine** computes truth deterministically; context *explains*
   it, never *implements* it. `UNKNOWN ≠ NOT_MET`. `evidence found ≠ reviewed ≠ accepted`. Benchmark
   honesty: `OBSERVED / DECLARED / UNAVAILABLE`, never "not observable = 0". Everything labeled
   **"Synthetic · HEDIS-aligned (eCQM-proxied) · Not NCQA-certified · Not for clinical use."**
2. **Buildable** — everything reproducible lands in a **DAB + scripts**; manual steps are few, listed, and
   scripted-around. One command stands up a fresh FEVM workspace.
3. **Visually attractive** — the app is the payoff. Design bar in §8; use the `databricks-app-design` +
   `dataviz` skills, not default scaffolding.
4. **Demoable** — a 15-minute scripted path that a non-author can run. Live where safe, **replay fallback**
   for anything async.

**Golden-slice-first (⭐):** before fanning out to all retrieval arms, make ONE vertical slice work end to
end — `one patient → one A1c mapping issue → deterministic evaluation → metric view → one Genie One answer
→ one record-level trace → one approved mapping change → reproduced-then-changed answer`. Everything else is
an extension of that slice. This prevents impressive-but-disconnected pieces.

**Legend:** 🤖 agent-automatable (DAB/scripts) · ⚙ manual human/admin step (→ `docs/RUNBOOK.md`) ·
⏳ async / wait (duration + how to verify) · 🔒 epistemic-correctness checkpoint · ⭐ part of golden slice.

---

## 0a. Reuse & accelerators (start here — don't reinvent)

Two existing assets shortcut large parts of this build and double as a "breadth of Databricks" story.
Treat both as **accelerators, not dependencies** — they shorten P2/P4/P12 and anchor the close; both are
community/industry-solutions assets (no SLA), so pin versions, label Preview/Labs, and verify in-workspace.

**① `Genie GenAI Evals` notebook** — *Eli's own; already proven on an FEVM workspace; pins
`mlflow[databricks]==3.17.2`, `databricks-sdk==0.157.0`.* A production-grade `mlflow.genai.evaluate()`
harness for any Genie space in **chat** (Conversation API) or **agent** (Genie Research, streaming
Responses API) mode. It already implements, exactly to this plan's epistemics:
- ground truth from the space's **benchmarks** (SQL executed live) + optional hand-written cases;
- **`sql_result_match`** — compares Genie's **result rows**, never SQL text, with numeric tolerance (the deterministic oracle);
- deterministic `genie_completed`, `latency_sla`, `citations_valid` (agent mode) + LLM judges `correctness`, `groundedness` (one RETRIEVER span), `analytic_clarity`;
- full MLflow **tracing** (span per Genie state/tool), per-space experiment, run history, and **canary** deliberately-wrong cases that prove the scorers catch errors.
→ **Starting point for P12**, scoped to the **Genie Agent arm (A2) only** — it evaluates a *Genie Agent
(space)* in both its **chat** (Conversation API) and **Research/agent** (Responses API) modes. It does
**not** evaluate **Genie One (A1)**, which is a separate front-door surface over spaces + the ontology
(handle A1 with its own caller — see P12). **Vendored at `benchmark/`** (see `benchmark/README.md`).

**② HLS Vital Skills** (`databricks-industry-solutions/vital-skills`) — agent skills for Genie Code
(installable into Genie Code; optionally synced to Unity Gateway as MCP). Relevant building blocks + the breadth story:
- **semantic builder** (payer/provider measure catalogs → Unity Catalog) → scaffolding for the HEDIS **measure catalog / semantic layer** (P4);
- **cohort builder** (reproducible cohorts from coded + free-text data) → starting point for the **eligible-population / denominator** logic (P2);
- **PHI de-identification** (HIPAA Safe-Harbor, k-anonymity) → reinforces the synthetic/no-PHI posture and is a showable capability;
- **RWE cohort studies**, **skill evaluation (MLflow)**, **report/presentation/figure builders**, **bioinformatics** (RNA-seq, single-cell, pathway) → the **"broader utility" showcase** (§8a).

---

## 1. Target environment (FEVM serverless)

- **Workspace:** AWS Serverless Stable via FEVM (`fe_vm_client.py deploy-serverless`). Serverless is
  required for **Apps, Lakebase, Model Serving**. Deploy ~5–10 min. **Lifetime ≤ 30 days** → the entire
  build must be re-runnable on a fresh workspace (this is the core reproducibility constraint).
- **Catalog:** use the pre-created `<workspace_name_with_underscores>_catalog`. Do **not** create a new
  catalog. Put everything under schema(s) within it, e.g. `…_catalog.care_protocol`,
  `…_catalog.terminology`, `…_catalog.eval`, `…_catalog.demo`.
- **Never auto-select a profile** — authenticate `databricks auth login <url> --profile fe-vm-<name>` and
  pass `--profile` explicitly.
- **Capability gate (Phase 0):** confirm in *this* workspace, because FEVM templates vary and these are
  preview/Labs: Genie One + **Genie Ontology** (preview; may be OFF — verify), **Pages** (beta; CRUD API may
  be absent → bulk-import fallback), **Domains** (beta API + Terraform), **Lakebase Search**
  (`lakebase_ann`/`lakebase_bm25`), **Managed/Genie One MCP**, **Model Serving** + an **embedding endpoint**,
  **MLflow 3 GenAI eval**. Produce `docs/capability-matrix.md` marking each `AVAILABLE / MANUAL_SETUP / UNAVAILABLE`.

---

## 2. Reproducibility model — what's automated vs. manual vs. async

**🤖 Reproducible via DAB + scripts** (the goal is ≥90% of the build here): medallion pipeline, terminology
loaders, measure engine, metric views (YAML), UC comments/tags/constraints, Genie Agent configs (DAB JSON),
Lakebase schema/indexes/sync, custom MCP + supervisor, MLflow harness + question set, the app, drift configs,
preflight/reset/replay commands.

**⚙ Irreducibly manual** (consolidated registry in §5): FEVM deploy + profile login; licenses (UMLS/SNOMED,
LOINC, VSAC key); enabling previews; publishing/certifying **Pages** and assigning **Domains** if CRUD API
absent; Ontobricks UI steps (Registry → Initialize, R2RML review, SHACL, **Publish**); any grant/approval a
service principal shouldn't self-escalate.

**⏳ Async / needs wait** (consolidated registry in §6, with durations): **Genie Ontology extraction** after
Pages/metric-views/agents/query-history exist (the big one — hours, no SLA; verify by citations appearing);
Lakebase BM25 index build (after load); embedding/vector sync; Ontobricks graph materialization; Model
Serving + Lakebase instance provisioning; DLT first run; FEVM deploy.

**Scheduling insight:** the ⏳ **ontology sync is the critical-path bottleneck.** Order the build so Pages +
metric views + agents + a query-history seeding script exist **as early as possible**, trigger the seeding,
then build Lakebase / Ontobricks / eval / app **while extraction runs in the background.** Do not sit idle
waiting for it.

---

## 3. Dependency order (the DAG)

```
P0 Setup/licenses ──┬─> P1 Data (Synthea→Epic-ize) ──> P2 Pipeline+Terminology+Engine ──> P3 Gold+Provenance+Tracers
  (UMLS lead time!) │                                                                           │
                    │                                                                           ├─> P4 Semantic layer (metric views, comments) 
                    │                                                                           │        │
                    │                                                                           │        └─> P5 Pages/Domains/Cert (⚙) ─> P6 Genie Agents
                    │                                                                           │                                              │
                    │                                                                           │                                              v
                    │                                                                           │                              P7 ⏳ Seed usage → ONTOLOGY SYNC → verify Genie One
                    │                                                                           │                                 (kick off early; runs in background) 
                    │                                              ┌────────────────────────────┼──────────────┬───────────────────────┐
                    │                                              v                            v              v                       v
                    │                                     P8 Lakebase (hybrid)        P9 Ontobricks (⚙⏳)   P10 Custom MCP        (uses Gold + terminology)
                    │                                              └──────────────┬───────────────┴──────────────┘
                    │                                                             v
                    │                                                   P11 Supervisor agent (A6)
                    │                                                             │
                    └────────────────────────> P12 Eval harness + SQL oracle + question set <─── (all arms A1–A6)
                                                                  │
                                                                  v
                                                        P13 App (tabs) ──> P14 Drift scenarios ──> P15 Rehearsal + reset/replay
```

**Start Day 1 in parallel (no license on the critical path — ADR-0002):** (a) stage terminology from Drive
into a UC Volume (LOINC 2.83) + fetch ICD-10-CM / RxNorm; (b) confirm the ECT capability gate (Genie
Ontology ON, Apps enabled); (c) repo scaffold. The golden slice ⭐ runs P1→P4→P6→P7(min)→P13(min)→P14(min)
on GSD only, before the other arms.

---

## 4. Phases with to-do checklists

### P0 — Setup, licenses, capability gate  ⚙⏳
- [ ] 🤖 **No SNOMED/UMLS or VSAC needed (de-risked — ADR-0002).** Terminology = **LOINC 2.83** (already in Eli's Drive) + **ICD-10-CM** + **RxNorm** (public/free) + hand-curated demo value sets. Honor `LoincLicense_5.8`; stage all terminology into a **UC Volume** on ECT (read from Drive, never commit, never write back to Drive). *(SNOMED base/Extension only if Eli later licenses it for the Ontobricks track.)*
- [ ] ⚙⏳ Deploy FEVM **serverless** workspace (`fe_vm_client.py deploy-serverless --name hedis-context-lab`); `wait` for completion (~5–10 min); `databricks auth login … --profile fe-vm-hedis-context-lab`.
- [ ] ⚙ Enable/verify previews; write `docs/capability-matrix.md` (AVAILABLE/MANUAL_SETUP/UNAVAILABLE). **Explicitly confirm Genie Ontology is ON.**
- [ ] 🤖 Scaffold repo: DAB (`databricks.yml`/`variables.yml` bound to the FEVM catalog), `context/` package (concepts, mappings, value_set_manifests, measure_definitions, pages, metric_views, genie_agents, ontology, evaluation_cases) with a **release manifest** (terminology/value-set/mapping/metric/ontology versions + git commit), `docs/{RUNBOOK,capability-matrix,decisions,current-state}.md`, `AGENTS.md`.
- [ ] 🤖 Build a read-only **`preflight`/doctor** command verifying: auth, warehouse, catalog privileges, model+embedding endpoints, Genie Agent API, Genie One MCP, Lakebase + extensions, MCP discovery, Ontobricks domain/version, MLflow access.
- **Gate:** one real query succeeds through each available surface; unavailable capabilities documented.

### P1 — Data: Synthea → "Epic-ize"  🤖 ⭐
- [ ] 🤖 Run **Synthea** (fixed seed, ~5–10k patients, enrich adult T2DM) → FHIR/CSV into a UC Volume. (Pre-coded SNOMED/LOINC/RxNorm/CVX = ground truth by construction.)
- [ ] 🤖 Transform to **Clarity-shaped** Bronze tables (PATIENT, PAT_ENC(_HSP/_DX), PROBLEM_LIST, ORDER_PROC, ORDER_RESULTS, **CLARITY_COMPONENT** with ~8% intentionally **unmapped** LOINC, ORDER_MED, **IP_FLWSHT_MEAS** partially mapped, IMMUNE, COVERAGE, CLARITY_SER/DEP, Care-Everywhere/external results). Label "Clarity-shaped, synthetic."
- [ ] 🤖 Generate synthetic **unstructured docs** → Volume: outside eye-exam PDF letters, local diabetes protocol, **MY2025 + MY2026** measure-spec summaries, payer policy memo, a superseded policy, one prompt-injection-test doc.
- [ ] 🤖 Plant **tracers T1–T6 / GT-01–06** (§7) and write `demo.tracer_registry` with each tracer's expected value **at every layer** and expected winning approach.
- [ ] 🔒 **No real PHI; no committed licensed artifacts** (load terminology from Volume at runtime). Synthetic names like "Alex Tracer", MRNs `TRC-0001…`.
- **Gate:** tracers visible in Bronze; registry populated.

### P2 — Pipeline + terminology + measure engine  🤖 ⭐
- [ ] 🤖 **Starting point (§0a②):** evaluate Vital Skills **cohort builder** for the eligible-population / denominator logic (coded + free-text) before hand-rolling; keep the deterministic engine as the source of truth.
- [ ] 🤖 **Lakeflow Declarative Pipeline** Bronze→Silver: normalize events, map local codes → LOINC/SNOMED/RxNorm/CVX, **quarantine** (not drop) unmapped codes via expectations, preserve **multiple timestamps** (ordered/collected/observed/resulted/updated/ingested) + raw/normalized value+unit + mapping_id/version + result/correction status + source_record_id/version.
- [ ] 🤖 Load **terminology-as-data** — **free code systems only, no SNOMED/UMLS/VSAC license** (see ADR-0002): `loinc` + `loinc_parts` (curated subset vendored in `src/terminology/`, ADR-0007), `icd10cm` **with its code hierarchy** (chapter→category→subcategory — this carries the subsumption story in place of SNOMED is-a), `rxnorm` (free NLM), and **hand-curated demo `value_set_version`** tables for the 5 measures built from LOINC/ICD-10-CM/RxNorm (labeled *demo value sets — not NCQA/VSAC*), keyed by measurement_year + effective dates. *Optional (Eli/Ontobricks, license permitting): the LOINC SNOMED Extension (license-gated; not vendored) for LOINC-side ontology.*
- [ ] 🤖 **Build hierarchy encodings (ADR-0006):** `icd10_closure` (transitive closure of the ICD-10-CM tree, recursive CTE paid once at build time; "all diabetes" = `WHERE ancestor_code IN ('E10','E11','E13')`, auto-includes `E11.21` = T3 tracer), optional `loinc_part_closure`, and `value_set_segment` (cross-branch value sets/cohorts, named owner). A third relational differentiator vs Genie Ontology & Ontobricks; also the "Genie + closure view" arm. Spec: `src/semantic/{hierarchy_encodings.md,closure_tables.sql}`.
- [ ] 🤖 `ai_parse_document` + `ai_extract` over PDFs → `silver.supplemental_evidence` (source doc id, confidence, **review state**). 🔒 extraction = *candidate*, not accepted evidence.
- [ ] 🤖 **Deterministic versioned measure engine** — a few tested **rule families** (latest-accepted-observation-in-window; required-evidence-combination; approved-exclusion; coverage-qualification; reviewed-supplemental-acceptance). Not a general CQL compiler. Scope: **GSD, KED, EED, BPD, SPD** (+ protocol-only DM-03, DM-05 for the "HEDIS misses this" story). KED = eGFR **AND** (uACR OR albumin+creatinine ≤4 days). Use collection/result time per spec, not order time.
- [ ] 🔒 States: `MET / NOT_MET / EXCLUDED / NOT_ELIGIBLE / UNKNOWN / PENDING_REVIEW` (+ `MET_LATE`/`EXCEPTION` for protocol). Enrollment gap → `UNKNOWN`/labeled provider-cohort, **never an invented health-plan denominator**. Protocol status kept separate from HEDIS status.
- [ ] 🤖 **Unit tests first**: each tracer's computed status at each layer matches `tracer_registry` — **no LLM involved.**
- **Gate (🔒⭐):** golden-slice patient's GSD status reproduces by SQL/tests without any LLM.

### P3 — Gold + provenance + reconciliation  🤖 ⭐
- [ ] 🤖 Gold: `adherence_event_log` (1 row per patient×protocol×step×period, full schema), `hedis_member_measure` (num/denom/rate), `protocol_vs_hedis_recon` (aligned / data-coding gap / measure-too-narrow / true gap 2×2).
- [ ] 🤖 **Provenance tables** (trimmed): `source_record, evidence_artifact, evidence_assertion, mapping_decision, measure_evaluation, measure_evaluation_evidence, provenance_edge, retrieval_event(_item), answer_evidence_link` — each with stable_id, version, context_release_id, valid/recorded time.
- **Gate:** recon 2×2 reproducible; tracer T1 shows protocol-MET / HEDIS-NOT_MET (data gap).

### P4 — Semantic layer (Unity Catalog)  🤖 ⭐
- [ ] 🤖 **Starting point (§0a②):** evaluate Vital Skills **semantic builder** (measure catalog → UC) as scaffolding for the HEDIS measure catalog before hand-rolling metric views.
- [ ] 🤖 **Metric views** (YAML in Git): `hedis_measures` (num/denom/rate by MY, PCP, dept, payer, demographics), `protocol_adherence`, `recon`; value-set version resolved by measurement_year.
- [ ] 🤖 **Over-build metric views on purpose (ontology fuel):** ~20–25 total — one per measure × key dimension/variant (more than the demo strictly needs); each is a high-authority modeled snippet source for the ontology (§7a).
- [ ] 🤖 **Comments / governed tags / PK-FK** carrying precision ("an order is not a result"; "rate among the explicitly qualified denominator…"). 🔒 descriptions/formulas/synonyms/examples must **agree** — conflicts = failed deploy.
- [ ] 🤖 Make context components **toggleable** (comments / synonyms / metric-views-vs-raw / instructions / ontology-expansion) for ablation.
- [ ] 🤖 **Several AI/BI dashboards (6–8)** over the metric views, each with many widgets/queries — they feed the app *and* are a major inferred-snippet + usage source for the ontology (§7a).
- **Gate (🔒⭐):** metric views reconcile to the deterministic gold SQL (parity test).

### P5 — Pages / Domains / certification  ⚙ (🤖 drafts)
- [ ] 🤖 Draft `context/pages/*.md` (Measure-vs-Protocol, Accepted-Evidence, Glycemic Status, Kidney Eval, Eye Evidence, Order-vs-Completed, Measurement-Year/As-of, Mapping Confidence, Data Completeness, Current-vs-Historical, HBD→GSD alias) — each with definition, synonyms, authoritative assets, accepted vs. insufficient evidence, related pages, owner, effective dates, version. **Author ~40 Pages — more than strictly needed** (add per-measure, per-step and per-terminology-concept pages): certified Pages are the *highest-authority* ontology snippets, so over-authoring here pays off (§7a).
- [ ] ⚙ Publish Pages (CRUD API if available; else **Genie Code bulk import** from the markdown, then **manually add page-to-page links** — bulk import drops them) and **certify**.
- [ ] ⚙/🤖 **Domains/subdomains are a prerequisite, not optional** — the ontology weights snippets by domain, so they must **exist before P7**. Create them (Terraform `databricks_domain` or REST) if not already present, and assign **every** asset via governed tags: Clinical Quality (HEDIS, Protocol Adherence), Clinical Terminology (LOINC, SNOMED, Value Sets), Patient & Encounter. **Certify** the canonical asset per concept (certification = authority in the ontology).
- **Gate:** Pages published + certified; domains/subdomains exist and every asset is assigned. *(Triggers readiness for P7 ontology extraction.)*

### P6 — Genie Agents  🤖 + ⚙ tune  ⭐
- [ ] 🤖 Three agents as **DAB JSON**: **Diabetes Quality**, **Clinical Evidence**, **Terminology Quality** — narrow assets, grain/join guidance, **≥15–20 tested example SQL each** (also ontology snippet fuel — the ontology consults Genie Agents first), trusted UC functions (`terminology.descendants_of`, `measure_status(patient,measure,my)`), **abstention** instructions, measurement-year/as-of conventions, evidence-citation convention, own regression questions.
- [ ] 🤖 Create ablation agents over duplicated schemas `ctx_l0…ctx_l5` (C0 minimal → C5 terminology/graph).
- [ ] ⚙ Human-tune instructions; validate by round-trip readback + real questions (use **actual** current agent config schema, not an invented payload).
- **Gate:** native Genie Agent benchmark ≥ target on the regression set; golden-slice Genie answer matches oracle.

### P7 / §7a — Seed the ontology → ⏳ SYNC → verify Genie One  ⚙⏳  ⭐ (kick off EARLY)

**How Genie Ontology is built (so we can drive it).** The ontology = **modeled context** you fully control
(metric views, Pages, Domains, certification, UC comments) **+ inferred snippets** extracted from assets &
usage (dashboards, Genie Agents, query history). Each snippet is scored for **authority, usage, freshness**.
Precedence: **certified Pages outrank inferred snippets**; the ontology consults **Genie Agents & dashboards
first, then metric views, then UC metadata**; **Domains add weight**. *You influence extraction via asset
quality + usage + time — you cannot force it; it is async with no SLA and may be OFF by default (verify at P0).*

- [ ] 🤖 **Hit a ~1,000-snippet budget by over-building** (planning estimate — validate actual yield in-workspace):

  | Source (built in phase) | Target count | ~snippets | Main lever |
  |---|---|---|---|
  | UC table + column **comments** (P3/P4) | ~30 tables × ~15 cols | ~450 | breadth + precision of comments |
  | **Metric views** (P4) | 20–25 | ~200 | one per measure × dimension/variant |
  | **Pages** (P5) | ~40 | ~120 | certified = highest authority |
  | **Dashboards** widgets/queries (P4) | 6–8 × ~20 | ~120 | inferred + usage signal |
  | **Genie Agent** example SQL (P6) | 3 × ~15–20 | ~50 | ontology consults agents first |
  | **Query-history** distinct patterns (here) | few hundred | ~100+ | usage + freshness |
  | | | **≈1,000+** | |

- [ ] 🤖 **Query-history seeding job:** run a few hundred realistic NL questions (`databricks genie ask`) + the dashboard/metric-view SQL across all assets, and **re-run on a schedule** for a few days so usage & freshness signals accumulate (not a one-shot).
- [ ] ⚙ **Trigger seeding the moment P4–P6 exist**, then build P8–P13 **while extraction runs** — this is the critical-path overlap, not idle waiting.
- [ ] ⏳ **Wait for extraction** (hours+, no SLA). **Verify** — no standalone ontology UI ships ("Ontology Home" is PRD-stage), so confirm via: (a) Genie One answers **citing Pages/metric views** ("Ontology References") on the golden-slice questions; (b) spot-checking several seeded concepts; (c) the app's **Ontology Explorer** tab. If an ontology-inspection API exists in this workspace, use it (confirm at P0). Capture screenshots as **replay fallback**.
- [ ] 🔒 Genie One draws on the **workspace-wide** ontology → the **ablation ladder applies to Genie Agents, not Genie One** — say so on stage.
- [ ] 🔒 **Reproducibility:** keep every source in Git (Pages markdown, metric-view YAML, domain/tag manifests, dashboard defs, agent JSON, seed-query list) so a fresh FEVM workspace can rebuild the modeled context and re-trigger seeding deterministically — extraction *yield/timing* still varies, so always plan the wait in.
- **Gate:** Genie One cites certified assets for the golden slice; spot-checked concepts resolve to the right Pages/metric views.

### P8 — Lakebase hybrid retrieval (A4)  🤖⏳
- [ ] 🤖 Provision Lakebase instance (⏳); chunk docs (structure-aware ~500–800 tok, overlap) with full metadata (doc/version, patient nullable, effective dates, superseded_by, access_scope, content_hash, offsets, corpus_release_id).
- [ ] 🤖 Embed via pinned embedding endpoint/version; **sync table** to Lakebase; build `lakebase_ann` + **`lakebase_bm25` (AFTER load** — corpus stats at build time) ⏳.
- [ ] 🤖 Adapters: keyword / vector / **hybrid RRF** / hybrid+terminology-expansion. 🔒 don't add raw BM25+cosine; keep each rank separate; exact lookup for codes like `4548-4`; apply patient/access/version filters per candidate; return real passages + freshness.
- **Gate:** tracer T2 (outside eye-exam) retrieved top-3; EED flips to MET only after **reviewed acceptance**.

### P9 — Ontobricks (A5)  ⚙⏳ (🤖 scripts/deploy)
- [ ] 🤖 Deploy pinned Ontobricks release (two Apps: UI/API + `mcp-ontobricks`); `make deploy` / `make bootstrap-lakebase`; record the tag in repo.
- [ ] ⚙ UI: **Settings → Registry → Initialize**; design OWL (Patient, Encounter, Condition⊑SNOMED, Observation⊑LOINC, MappingDecision, ValueSetVersion, MeasureVersion, **MeasureEvaluation** as a graph entity, EvidenceArtifact/Assertion, SourceRecord); **R2RML** auto-map + review; **SHACL** shapes; **build** ⏳; **Publish** (only Published domains are exposed over MCP).
- [ ] 🤖 Smoke-test via **discovered** MCP tools (don't assume `query_sparql`); `describe_entity(TRC-0003)` returns the SNOMED hierarchy. 🔒 read-only tool subset; asserted-vs-inferred edges visible; missing edge ≠ care gap (open-world).
- **Gate:** graph answers the three relationship questions; subsumption tracer T3 included via closure/graph.

### P10 — Custom MCP tools  🤖
- [ ] 🤖 Bounded read-only MCP: `get_measure_definition`, `get_patient_measure_evidence`, `get_quality_metrics`, `explain_mapping_impact`, `search_clinical_documents`. Shared request/result envelope (question, patient scope, measurement_year, as_of_date, context_release, mode, timeout, correlation id → answer, evidence refs, versions, observable tool metadata, freshness, warnings, latency, errors). 🔒 least-privilege identity; verify end-user access; no SQL-keyword "security".

### P11 — Supervisor agent (A6)  🤖
- [ ] 🤖 Custom agent (Model Serving/App) composing Genie One MCP + Lakebase + Ontobricks MCP + UC terminology functions. 🔒 **recursion guard** (no Genie One → supervisor → Genie One loop); distinguish tool-via-MCP vs. agent-via-MCP budgets.

### P12 — Evaluation harness  🤖  ⭐(min)
- [ ] 🤖 **A2 (Genie Agent) — start from the `Genie GenAI Evals` notebook** (§0a①; vendored in `benchmark/`): repoint `space_id` + cases at the HEDIS Genie Agents and reuse its `predict_fn` + scorers + MLflow tracing wholesale. It delivers the Genie **Agent** arm in both **chat** and **Research/agent** modes, the `sql_result_match` **oracle**, and `canary` validation. **Scope: Genie Agents only — it does *not* evaluate Genie One.**
- [ ] 🤖 **A1 (Genie One) — separate, net-new caller.** Genie One is a different surface (unified front door over spaces + ontology), so reuse the notebook's *scorer + tracing pattern* but write a **new `predict_fn`** against whatever Genie One exposes programmatically (e.g. Genie One MCP). 🔒 Confirm at the P0 capability gate what's actually callable/observable for Genie One; if it can't be driven headlessly, evaluate it **observationally and label it so** — do not claim parity with the Agent arm.
- [ ] 🤖 **Extend `predict_fn` + the scorer registry to the remaining arms** (A4 Lakebase, A5 Ontobricks, A6 supervisor, custom MCP): each returns answer text + a RETRIEVER span of evidence, so the judges carry over unchanged. 🔒 `sql_result_match` applies **only** where an arm returns result rows — for doc/graph arms, score extracted-fact / patient-set match against the oracle, and **never penalize a correct refusal** (question-type scoring).
- [ ] 🤖 Package as `hedis_eval/` + thin notebook entry + Databricks **Job**; results → `eval.results(arm, level, question_id, category, run_id, score_*, latency_ms, trace_id)`.
- [ ] 🤖 Question set (60–100, held out from Pages/examples) across 7 types: aggregate, definitional, hierarchy, multi-hop, unstructured, patient-trace, drift. 🔒 **score by question type** (a doc-retriever *should* refuse a population count), **leave-one-out** + incremental ladder, **3–5 repeats + variance** (per-arm service principals), `OBSERVED/DECLARED/UNAVAILABLE` (native cost/retrieval = not-observable, **not 0**), + security/abstention tests.
- [ ] 🔒 Don't claim causal isolation of native-ontology effects; label observational.
- **Gate:** all arms run end-to-end; scorecard renders; no fabricated evidence.

### P13 — App (net-new or forked)  🤖  ⭐(min)
- [ ] ⚙ **Decide reuse vs. net-new** (see `planning/CRITICAL_ANALYSIS_THREE_APPROACHES.md` §5a). If reusing Control Tower: **read repo first**, **disable date-shifting/startup mutation** (breaks MY reproducibility), replace string-based SQL "security". Net-new (thin FastAPI/Flask + React, OBO auth, Lakebase app state) is plausibly cleaner.
- [ ] 🤖 Tabs: **Quality Overview** (rates, denominator, UNKNOWNs, recon 2×2), **Patient Evidence / Tracer Journey** (Bronze→Silver mapping→closure→gold→metric→Page/agent→each arm's answer + MLflow spans), **Context Explorer**, **Retrieval Arena** (one question, 2–3 arms side-by-side: answer, evidence, observable tools, latency), **Trace Explorer** (provenance + lineage), **Benchmark Scorecard** (accuracy by arm×category, ablation ladder, cost/latency), **Drift Lab**, **Ontology Explorer** (SNOMED/LOINC subgraph + link to Ontobricks).
- [ ] 🤖 Show data/context **version** + **synthetic** label on every view; deep-link from Genie One where supported (don't require embedding native Genie).
- **Gate (⭐):** a visitor follows one tracer end-to-end unaided.

### P14 — Drift scenarios  🤖  ⭐(min: one)
- [ ] 🤖 Three PR-sized changes: (1) **mapping repair** (T1 unmapped A1c → approve versioned mapping → recompute); (2) **value-set version** MY2026 dropping legacy eGFR (T4) → KED rate changes, Genie One updates with no prompt edits; (3) **metadata-only** HBD→GSD alias (results unchanged). 🔒 distinguish the three change types; "updating a Page ≠ updating a measure"; hypothetical local change **labeled not an official HEDIS change.**
- [ ] 🤖 Drift Lab shows YAML diff, before/after rates, flipped patients, drift-benchmark rerun, **stale-RAG contrast** (Lakebase returns old spec without version filter), regression results, approver, timestamp; distinguish **published / in serving copy / observed in a new answer**; keep immutable history + `active_release` pointer + rollback.
- **Gate:** one controlled change propagates and the same question's answer changes for the right reason.

### P15 — Rehearsal, reset, replay  🤖 + ⚙
- [ ] 🤖 One-command stand-up (preflight → deploy → pipeline → semantic → agents → seed) + **deterministic reset** + **replay** (recorded traces/screenshots for async bits).
- [ ] 🤖 README: architecture diagram, 15-min + 45-min demo scripts, GA/Preview/Labs labels per feature, troubleshooting.
- [ ] ⚙ Two clean rehearsals from a fresh (or reset) FEVM workspace.
- **Gate:** a peer stands it up and runs the script from the README alone.

---

## 5. Manual-step registry (⚙ — put all in `docs/RUNBOOK.md`, ordered)
1. UMLS/SNOMED license (lead time), LOINC account, VSAC API key.
2. FEVM serverless deploy + `databricks auth login` profile.
3. Enable/verify previews; confirm Genie Ontology ON.
4. Publish + certify **Pages** (if no CRUD API: Genie Code bulk import + manual page-to-page links).
5. Create/assign **Domains** (if not Terraform-able in this workspace).
6. Ontobricks: Registry Initialize, R2RML review, SHACL, **Publish** domain.
7. Any grant/approval (service-principal scopes, app grants, MCP registration) — **never self-escalate**.
8. App reuse-vs-net-new decision.
9. Two demo rehearsals.

## 6. Async / wait registry (⏳ — durations are estimates; always verify, don't assume)
| Wait item | When | Est. | Verify by |
|---|---|---|---|
| FEVM serverless deploy | P0 | 5–10 min | `wait --run-id`; login succeeds |
| Lakebase + Model Serving provisioning | P8/P11 | mins–tens of mins | endpoint/instance READY |
| DLT pipeline first run | P2/P3 | mins | run success; row counts |
| **Genie Ontology extraction** | **P7** | **hours, no SLA** | Genie One answers **cite** Pages/metric views ("Ontology References") |
| Lakebase **BM25** index build | P8 | mins (post-load) | index status; test query |
| Embedding/vector sync | P8 | mins | sync watermark; top-k returns |
| Ontobricks graph build/materialize | P9 | mins–tens of mins | `describe_entity` returns hierarchy |

**Overlap the long waits:** kick off P7 seeding right after P4–P6, and UMLS on Day 1, so extraction and
licensing run *under* the rest of the build.

## 7. Tracers / golden threads (planted, with expected winner)
| ID | Planted fact | Proves | Expected winner |
|---|---|---|---|
| T1/GT-01 | Send-out A1c 7.2% under local component, **no LOINC map** | protocol MET, GSD NOT_MET (data gap); mapping fix closes it | Genie One/Agent via recon; RAG can't compute |
| T2/GT-03 | Retinal exam only in **outside PDF** | structured misses; hybrid finds; **review→accept**→EED MET | Lakebase / supervisor |
| T3 | Diabetes coded as a specific **ICD-10-CM subcategory** (e.g. `E11.21`, T2DM w/ diabetic nephropathy) absent from a naive flat code list | **hierarchy/prefix expansion** (ICD-10-CM tree) includes the patient in the denominator; a flat list misses them | ontology-as-data (code hierarchy), Ontobricks, Genie w/ expansion view |
| T4/GT-05 | eGFR with **legacy race-based LOINC** | value-set version change flips KED → drift | metric view + versioned value set |
| T5 | Last BP 128/78 in **ED**, outpatient 148/92 | BPD excludes ED readings → NOT_MET | Genie One w/ Page+metric view; RAG often wrong |
| T6/GT-02/06 | Hospice exclusion / order-only / **unknown enrollment** | EXCLUDED/UNKNOWN ≠ failure; order ≠ result | structured; honest abstention |
| +perm | aggregate visible, patient report **not** | access scope enforced across arms | security test |

---

## 8. Visual & demo bar (so it's attractive and demoable, not just correct)
- Use `databricks-app-design` + `dataviz` skills. Clean, branded, legible in light/dark; the **recon 2×2**, the **ablation ladder chart**, and the **Retrieval Arena side-by-side** are the hero visuals.
- Every answer card shows: question · mode · data/context version · answer · supporting evidence · **rejected evidence + reason** · observable tools/SQL · freshness · eval score · trace link. Max **2–3 arms** side-by-side, never 7 columns.
- **15-min live path:** Genie One gap question → open patient evidence (a test that didn't count) → follow the record to the missing mapping → compare 2–3 retrieval arms → show an order-only false-closure avoided → find the outside eye report (extraction≠acceptance) → **repair the mapping** → reproduce old vs. new answer → open the scorecard (accuracy, abstention, latency, limits). Replay fallback for anything async.

## 8a. Broader-utility showcase (illustrate the wider Databricks / HLS platform)
A deliberate **closing beat** (one app panel or 2–3 slides) that frames this demo as one slice of a much
larger HLS platform — the "how much broader utility there is in Databricks" message.
- **Vital Skills gallery** (§0a②): cohort builder, semantic builder, PHI de-id, RWE, report/figure/
  presentation builders, and genomics (RNA-seq, single-cell, pathway). Run **one** live (e.g., cohort
  builder or a scientific-figure skill) so it's concrete, not a logo slide.
- **Message:** "the same lakehouse + governed semantics + Genie One that answered these HEDIS questions
  also powers genomics, RWE, and de-identification — one platform, one governance model, Genie Code as
  the authoring surface."
- Keep it a **showcase, not a build target** — point to the repo; the core demo takes no dependency on it.

## 9. Risk register (top)
- **Ontology extraction lag / no citations** → seed early (P7), screenshots as fallback, label observational.
- **Preview APIs (Pages/Domains) absent in FEVM** → content stays as Git markdown/YAML; RUNBOOK manual path.
- **Ontobricks version churn / deploy friction** → pin a tag; it's the most likely to slip → golden slice + arms A1/A2/A4 don't depend on it.
- **FEVM 30-day expiry** → everything re-runnable; keep a reset/replay; don't hand-craft in-UI without scripting it.
- **No SNOMED/UMLS** (ADR-0002) → terminology is LOINC + ICD-10-CM + RxNorm (free) + hand-curated demo value sets; the subsumption demo uses the **ICD-10-CM hierarchy** instead of SNOMED is-a. SNOMED/VSAC fidelity is a *future* enhancement, not a blocker.
- **Overclaiming** → GA/Preview/Labs labels; "synthetic, not NCQA-certified" everywhere.
- **Reused assets are community/Labs (no SLA)** → Vital Skills (industry-solutions) + the Genie Evals notebook pin specific versions (`mlflow 3.17.2`, `databricks-sdk 0.157.0`); pin + verify them in-workspace, and label Preview/Labs. They accelerate; they are not load-bearing for the core demo.

## 10. Open decisions (confirm before/at P0)
1. FEVM workspace name + region (drives catalog name)?
2. App: **reuse Control Tower or net-new**? (recommend net-new unless scaffolding clearly pays off)
3. Commit to all 6 arms, or golden-slice + A1/A2/A4 first, then A5/A6?
4. Who owns the ⚙ clinical/spec sign-off (measure interpretation, mapping approvals)?
5. Where/when is this shown (shapes the 15- vs 45-min script)?
```

---

## 11. Session log

### 2026-11-01 (latest+2) — Capability map split into A1-off/A1-on and made live on both workspaces

Eli imported the 16 Pages on DMVM. Next step per ADR-0018: split the single `a1_genie_one` arm into **a1_off
(ECT baseline)** and **a1_on (DMVM treatment)**, as code. Snippet density (~200 ECT / ~1,100 DMVM) is UI-observed
only (no CLI/API), so that measurement stays manual; this session did the reproducible restructure + made it live.

**Did (committed `12ebdb8`, then deployed):**
- `capability_matrix.csv`: `a1_genie_one` → `a1_off` (the existing hand-verified verdicts were taken on ECT =
  the baseline workspace); added `a1_on` = **`pending`** for all 20 (NOT fabricated — awaits DMVM post-extraction
  hand-verification, which is Eli's per the charter).
- `persist_capability_map.py`: 4 arms now (m0 / closure / a1_off / a1_on); `SCORE` adds `pending → null` (distinct
  from `not_reached` = 0.0); arm/column comments updated.
- `benchmark_capability.lvdash.json`: `ds_matrix` shows `genie_one_off` + `genie_one_on`; `ds_coverage` /
  `ds_by_class` exclude `pending` from scorable coverage.
- `capability_map.md` (source of truth): A1 bullet explains the off/on split + ~1,000-snippet threshold; legend
  adds ⏳ = pending; the matrix table gained an **A1-on (DMVM)** column (⏳ across all 20 rows).

**Made live (Eli approved all 4 steps):**
- `bundle deploy` to **ect** (2 resources changed) + **dmvm** (7 changed) — pushed the new dashboard + persist script.
- `persist_benchmark -t ect` (shared tables): **20 questions / 80 tidy rows** (20 × 4 arms).
- Smoke-tested live on the ECT warehouse: coverage **a1_off 17/20, closure 15/17, m0 6/20; a1_on correctly
  excluded (all pending)** — matches the local dry-run exactly.
- Republished the `benchmark_capability` dashboard on **both** workspaces.

**Open (Eli's, once DMVM extraction completes ~daily):** hand-verify Genie One on DMVM against the 20 questions,
fill `a1_on` in `capability_matrix.csv`, re-run `persist_benchmark`. Then the three-way read (baseline vs inferred
ontology vs explicit graph) is fully populated.

### 2026-11-01 (latest+1) — DMVM bring-up executed: workspace-local assets + A4 Lakebase RAG at ECT parity

Deployed the ontology-ON arm to DMVM over the shared catalog, then brought A4 (Lakebase RAG) to full parity.
All external writes confirmed by Eli.

**DAB scoping fix (ADR-0019) — had to land first.** A second production target (`dmvm`) over the ONE shared
catalog collided: `schemas.yml`/`volumes.yml` manage **unsuffixed** UC objects, so two prod TF states would try
to create already-existing schemas AND a future `bundle destroy -t dmvm` could drop the shared schemas + data.
Fix: inlined schemas+volumes into `databricks.yml` under a `&shared_uc` anchor attached to **dev + ect only**;
dropped them from the include glob; deleted the two files. Verified: `dmvm` resolves **0 schemas / 0 volumes**,
same 13 jobs / 1 pipeline / 4 dashboards as ect. All three targets validate OK.

**Deployed to DMVM (steps 1–5, all green):**
- `bundle deploy -t dmvm`: **22 resources** (4 Genie agents, 4 dashboards, 13 jobs, 1 pipeline), 0 schemas/volumes.
- `seed_query_history -t dmvm`: SUCCESS (DMVM-local query history — the per-workspace inferred-snippet fuel).
- `smoke_test_snippets --profile DMVM`: **74/74 pass** (58 Genie snippets + 16 dashboard datasets).
- `stage_pages` + `stage_source_documents`: refreshed the **shared** volume to **17 Pages** (added `ssd.md` +
  `document-access-scope.md`; the Oct-30 staleness that Genie Code flagged is now fixed for BOTH workspaces) + 9
  source docs. Verified from the ECT side too.
- Published all 4 DMVM dashboards.

**A4 Lakebase RAG — brought to ECT parity on DMVM:**
- Created the `care-protocol` Lakebase project on DMVM (`ep-divine-wildflower-d2l62zpy`).
- **Detected ECT's actual path** (read its live Postgres): Lakebase Search — `lakebase_vector`/`lakebase_text`,
  `lakebase_ann` + `lakebase_bm25` indexes. **Finding: ECT's `rag.chunks` has 0 embeddings** — ECT runs
  **lexical/BM25-only** today (the ANN index sits over an all-NULL column; `a4_lakebase.py` embeds the *query*
  at search time). So "mirror ECT" = corpus + BM25, embeddings absent on both.
- Eli **enabled Lakebase Search** on the DMVM project (the one irreducible manual UI step; `lakebase_vector`
  needs `shared_preload_libraries`, which that toggle sets — confirmed by a clean pre-enable failure).
- Applied `schema.sql` (preferred Lakebase Search path) → loaded corpus (`lakebase_rag_corpus.py
  --emit_demo_roles`): **7 docs / 36 chunks / 13 ACLs / 3 members / 36 BM25** — matches ECT exactly.
- **RLS verified live:** `tests/test_rag_rls.py` → **4/4 negative-security tests pass** (analyst can't retrieve
  LETTER-EYE-TRC-0003; clinician can; enforced via the `rag.acl_allows()` SECURITY DEFINER fn, ADR-0016).
- DMVM has `databricks-gte-large-en` READY, so embedding both envs' chunks is a fast-follow if we want the
  semantic/ANN half live (would be a *new* capability on both, not just DMVM — flag as such).

**Remaining manual (yours) — note the corrected mechanism (commit `91f81f7`): there is NO Genie Ontology
toggle; it's always on, and the baseline/treatment split is the ~1,000-snippet density threshold (ECT ≈200 =
below = baseline; DMVM ≈1,100 = above = treatment).** So the job is to drive DMVM's snippet count up, not flip a
switch: import the **16 Pages** via Genie Code (`docs/ontology/PAGES_IMPORT_PROMPT.md`) → Clinical Domain; the
query-history seed + dashboards + Genie agents already deployed this session also mint snippets. Then ⏳ wait for
extraction (**~daily cadence, not minutes**) and compare density vs ECT; split `a1_genie_one` → `a1_off`/`a1_on`.

### 2026-11-01 — Two-workspace design (ADR-0018): DMVM = ontology-ON arm, ECT = baseline

Committed the four-in-one session (`23801e0`). Then designed the A1 (Genie One) **with vs. without native
ontology** experiment. **Why two workspaces:** Genie Ontology is workspace-level — once on, Genie One always
uses it (no per-query off switch; the ablation ladder is Agents-only, P7/line 214). **Verified:** ECT + DMVM
share one metastore and the **one** `eli_test_classic_catalog` (bound RW to both); DMVM already reads all
`care_protocol*` schemas + comments, has a Serverless Starter Warehouse, Genie API reachable. So: one catalog
(data + modeled metadata held constant), two workspaces, vary only the native-ontology layer. See **ADR-0018**.

**DMVM bring-up plan (ontology-ON arm) — mirrors P5–P7 on the shared catalog:**
1. 🤖 **DAB:** add `dmvm` target (**done** this session); `bundle validate -t dmvm` green. Capability gate so
   far: warehouse ✓, Genie API ✓, shared catalog ✓. **Open:** confirm Genie Ontology is enableable on DMVM
   (workspace **admin** setting) + Apps if the app ships there.
2. ⚙ **Deploy workspace-local assets to DMVM** (`bundle deploy -t dmvm --profile DMVM`): 4 Genie spaces +
   dashboards + persist_benchmark. External write → **confirm**.
3. ⚙ **Enable Genie Ontology** (admin) + author/publish **Pages** + create **Domains** + assign governed tags —
   the high-authority snippet sources ECT's tag-policy cap can't make.
4. 🤖⏳ **Run query-history seeding** on DMVM (per-workspace usage/freshness) → **wait** for extraction (hours,
   no SLA). Verify by Genie One citing Pages/metric views.
5. 🔒 **Verify + measure:** capture DMVM snippet density vs ECT; **split `a1_genie_one` → `a1_off` (ECT) /
   `a1_on` (DMVM)** in the capability map; label observational (ON env also adds Pages/Domains).

**Done this session:** commit `23801e0`; ADR-0018; `dmvm` DAB target + annotated `ect` as baseline; this plan.
**Held (external → confirm):** steps 2–5 (all DMVM deploys / admin enablement / seeding).

### 2026-11-01 (cont.) — DMVM bring-up prep: Pages import prompt + runbook; three shared-object corrections

Prepping the DMVM ontology-ON buildout the user asked for ("deploy to DMVM; get Pages, same dashboards, Genie
agents, schedules, everything that creates ontology snippets"). Read-only grounding surfaced **three things that
simplify the plan vs. ADR-0018's first draft** — all because *domains and the catalog are metastore-level, not
per-workspace*:
- **Domain is shared, not per-workspace.** `Clinical Domain` (`b624f99f-…`) is the **same object** on ECT and
  DMVM (same id, same create time). No `create_domains.py` re-run on DMVM. ADR-0018 corrected: ECT's OFF-ness
  comes from the **Genie Ontology workspace toggle**, not from "absent Domains/Pages" (can't remove a shared
  object from one workspace).
- **Genie agents deploy to DMVM unchanged.** RUNBOOK had a "find/replace the catalog for DMVM" note that assumed
  separate catalogs; the catalog is **shared**, so the `.geniespace.json` identifiers + warehouse lookup resolve
  on DMVM as-is. Corrected the note.
- **The staging volume is shared and was stale.** `/Volumes/…/care_protocol/ontology_pages` (one object both
  workspaces read) was missing `ssd.md` + `document-access-scope.md` and had measure links on `care_protocol`
  not `care_protocol_semantic` (2026-10-30 staging, pre-SSD). The **source files are correct**; one `stage_pages`
  re-run fixes both workspaces. (Genie Code's review flagged exactly this.)

**Did (local, committed):** new **`docs/ontology/PAGES_IMPORT_PROMPT.md`** — de-duplicated, workspace-agnostic
Genie Code bulk-import prompt (refresh-volume pre-req, 16-Pages/skip-README, semantic-layer links, review-table
gate, + a Step-2 "propose don't publish" for the MAD / Step-3 / contraindication gaps). Fixed stale "14 files"
→ "16 Pages + README (17)" in `pages/README.md` + RUNBOOK. Added a consolidated **DMVM bring-up checklist** to
the RUNBOOK (shared=no-action / workspace-local=deploy / manual=admin) and the ADR-0018 correction.

**Held (external → confirm):** the DMVM deploy + seed + Pages import + ontology enablement (the actual writes).

### 2026-11-01 (cont. 2) — DMVM ontology-ON arm DEPLOYED (steps 1–5 of the bring-up)

Eli approved steps 1–5; ran them. First fixed a structural blocker (ADR-0019): two production targets over the
one shared catalog collided on the unsuffixed schema/volume resources → scoped `schemas`+`volumes` to dev+ect
only (verified dmvm resolves 0 of each, same 13 jobs/1 pipeline/4 dashboards). Then:
- **`bundle deploy -t dmvm`** → **22 resources created** (4 Genie agents, 4 dashboards, 13 jobs, 1 pipeline), 0
  schemas/volumes — no collision. All read the shared catalog.
- **`seed_query_history -t dmvm`** → SUCCESS (DMVM-local query history; the local CLI lost DNS mid-poll but the
  job completed server-side — verified via `jobs get-run`).
- **smoke test `--profile DMVM`** → **74/74 pass** (58 Genie snippets + 16 dashboard datasets) against the shared
  catalog from DMVM.
- **`stage_pages` + `stage_source_documents`** → refreshed the **shared** volume to 17 Page files (added the
  formerly-missing `ssd.md` + `document-access-scope.md`; verified from the ECT side too) + 9 source docs.
- **Published all 4 DMVM dashboards.**
DMVM agent IDs: HEDIS `01f1d63eaf1e148aaca3e207c7499c1a`, LOINC Lab `01f1d63eaf311cb38542d9d2a087705c`,
Cohort & Terminology `01f1d63eaf3d182495a64bedeca25f51`, Protocol/MAD `01f1d63eaf6113c5af84aa85fd4a5a3c`.

**Remaining (manual / admin — Eli):** (6) enable **Genie Ontology on DMVM** (confirm OFF on ECT); (7) import the
16 **Pages** via Genie Code → Clinical Domain using `docs/ontology/PAGES_IMPORT_PROMPT.md`; then let the ontology
extract (async) and record DMVM snippet density vs ECT in `capability-matrix.md`.

### 2026-10-31 (latest+2) — Four-in-one: MV-2 lab metric view + AG-3 terminology agent + capability-map dashboard (+ stale-view drop pending)

Eli: "just start doing all of these as one" (the four open threads from the Genie One review + session logs). Built
all four **as code**, then applied the non-destructive batch to ECT (Eli approved "apply batch, hold the drop").
Live: `deploy` → `run measures` (built `gold_lab_result`) → `run semantic` (created `lab_result_metrics`; 9 views) →
`run persist_benchmark` (20 questions, 60 tidy rows). Dashboard datasets live-SQL-tested green on the warehouse.

**Two findings (surfaced; NOT acted on — hand-verification is Eli's per the charter):**
- **`lab_result_metrics` reproduces the class-3 gold exactly:** Patients Tested for the HbA1c Component = **9,709**,
  = the pinned `lab_a1c_any_method` gold. So the **metric-view layer (M0) can now reach class 3** (LOINC multiaxial)
  via this new view — the capability matrix currently records M0 `not_reached` there. Candidate verdict upgrade,
  pending Eli's hand-verification (don't auto-upgrade; closure/MV is not an oracle).
- **`Uncoded (no LOINC Part)` dominates lab volume** (~14.2M obs): expected — `loinc_parts` is a curated subset of
  the measure-relevant analytes, so every other Synthea lab (BMI, PHQ, etc.) falls in the COALESCE bucket. Honest,
  but if lab snippets should exclude it, filter `component IS NOT NULL`.

**Did (committed-ready source; applied to ECT this session except where noted):**
- **MV-2 — LOINC Lab Measures metric view.** New gold fact grain `gold_lab_result` in `src/pipelines/measures.py`
  (silver_observation × loinc_parts, Parts pivoted to Component/System/Method columns via left joins; null Component
  for codes absent from the demo Part subset). New `src/semantic/metric_views/lab_result.metric_view.sql` →
  `care_protocol_semantic.lab_result_metrics` (dims Lab Concept/LOINC Code/Specimen/Method/Units/Year; measures
  Observations, Patients Tested = COUNT(DISTINCT), Avg/Min/Max). This is the charter's "graph > closure WITHIN a
  vocabulary" exemplar (all A1c by Component regardless of method). +12 `gold_lab_result` column comments.
- **AG-3 — Cohort & Terminology Genie agent.** New `resources/terminology.geniespace.json` + `terminology_agent`
  in `genie_spaces.yml`. Self-contained over `care_protocol_terminology.*` (9 tables, sorted by identifier per the
  export gotcha): ICD-10 closure/hier, RxNorm closure/hier/statin, loinc, loinc_parts, protocol_edges,
  value_set_segment. **15 example-SQL snippets** (ICD-10 subsumption, direct children, RxNorm ingredient→drug,
  is-312961-a-statin, LOINC multiaxial Component, eGFR methods, value-set membership + vintage drift, protocol
  edges, eGFR<30 contraindications) + 10 sample questions + instructions. Scoped to definitions, not patient counts
  (→ HEDIS agent), kept separate for Genie accuracy. **Net curated snippets 33 → 48** across three agents.
- **Benchmark leaderboard → capability MAP (persisted).** Closes the "benchmark logs to MLflow only, no results
  table" gap. Versioned the hand-verified matrix as data: `docs/benchmark/capability_matrix.csv` (20 questions ×
  3 arms, mirrors `capability_map.md`). New `src/benchmark/persist_capability_map.py` loads it into
  `care_protocol.benchmark_capability_matrix` (wide) + `benchmark_capability_tidy` (long, for charting), with
  table/column comments; new `persist_benchmark` job (serverless, no warehouse/Genie needed). New AI/BI dashboard
  `resources/benchmark_capability.lvdash.json` (+`dashboards.yml`): scorable coverage by arm, reached-by-class,
  and the full hand-verified matrix table. Framed as a **capability map, not a leaderboard** (ADR-0010).

**Did (continued — AG-2 + a test harness; applied to ECT):**
- **AG-2 — LOINC Lab Measures Genie agent.** New `resources/lab_measures.geniespace.json` + `lab_measures_agent`
  (genie_spaces.yml), over `lab_result_metrics` (+ gold_lab_result, loinc_parts). 10 snippets (A1c-any-method,
  eGFR-by-method, avg result, volume by concept/year/specimen). **Deployed to ECT.** Curated snippets now **58
  across 4 agents.**
- **Snippet smoke test (`scripts/smoke_test_snippets.py`).** Reproducible demo-safety net: executes every Genie
  example-SQL snippet + every dashboard dataset query against the warehouse (via the CLI; no SDK install).
  **Result: 74/74 pass** (58 Genie snippets + 16 dashboard datasets), all 4 agents + all 4 dashboards green.
- Local pytest suite (prior-session A4 RAG tests) not runnable here — no `pytest` in either interpreter (needs a
  dev install); unrelated to this session's assets.

**Didn't (held):**
- **ADR-0013 stale-view drop** (4th thread) — Eli chose "hold the drop." Still pending: drop the 7 old
  `care_protocol.*_compliance_metrics` views now that `care_protocol_semantic.*` resolves. Destructive → explicit
  confirm. (The new `lab_result_metrics` is already in the new schema; no old duplicate to drop for it.)
- **AG-2 (LOINC Lab agent)** now unblocked by MV-2 (would consume `lab_result_metrics`) — fast follow, not built.
- **Terminology & new Genie agents not benchmarked** — `terminology_agent` is deployed but not yet a scored arm.
- **Not committed yet** — the whole four-in-one batch is uncommitted in the working tree.
- **CSV gotcha fixed mid-run:** `persist_capability_map` first failed — two `note` values had unquoted commas
  (pandas: "Expected 10 fields, saw 11"). Quoted them, redeployed (re-syncs the file), re-ran green.

### 2026-10-31 (latest+1) — Genie One review actioned: HEDIS view dimensions + snippet density + source volume

Evaluated Genie One's metric-view / agent recommendations against our goals (serious capability map; snippet
density is demo-critical; persist-everything-as-code). **Status of each rec:**

| # | Recommendation | Verdict | Status |
|---|---|---|---|
| MV-1 | Clinic/Panel/**Gap Reason** on the 5 HEDIS views (KED/BPD need a roster join) | High value — unlocks clinic breakdowns + care-gaps-by-reason | **DONE, live** |
| MV-2 | Lab-results metric view (silver_observation × loinc_parts): patients tested, result count, avg value; by concept/method/code/year | Good — enables the LOINC agent + many lab snippets | **Roadmapped (next)** — needs a backing silver/gold view |
| MV-3 | Measure-drift metric view (qualifying patients × code-list year × matched code) | Good — formalizes `measure_drift_demo.sql` + the drift dashboard | **Roadmapped** |
| MV-4 | Protocol-safety metric view (drug class × has-lab × past-threshold × protocol section) | Good — cardiorenal (metformin↔eGFR) safety story | **Roadmapped** — needs design |
| MV-5 | Metric views in the **dev** schema | Valid gap, but **risky now**: the `dev` target is `mode:development` yet the pipeline writes to the *same* `care_protocol` schema as `ect` (pipelines.yml hardcodes schema), so "dev metric views" without schema isolation would collide with ect | **Roadmapped — needs dev-schema isolation design first; do NOT rush** |
| AG-1 | **Protocol Process & Medication Adherence** agent (Step-3 + MAD + panel + protocol-watch) — the biggest gap; answers "which clinic has the lowest Step-3 adherence?" | Highest agent-coverage gap | **DONE, live** (`protocol_adherence_agent`) |
| AG-2 | LOINC Lab Measures agent | Good | **Roadmapped** — depends on MV-2 |
| AG-3 | Cohort & Terminology agent (ICD-10 hierarchy, cohort, SNOMED eye procs, RxNorm hier, exclusion lists) | Good — self-contained over terminology tables | **Roadmapped (next; buildable as code now)** |
| AG-4 | HEDIS agent certified/clone drift | Our Genie spaces are **DAB-managed from version-controlled `*.geniespace.json`** — that IS the reconciliation: one source of truth, no hand-edited clones. Certify from the DAB-deployed space | **Addressed by design; documented** |
| — | GSD exclusions "later iteration" (hospice/ESRD/frailty) | Known honesty gap | **Roadmapped** |

**Did (committed + live on ECT):**
- **MV-1:** added `.join(_roster())` to `gold_adherence_{ked,bpd,spd,eed}` (gsd/mad/protocol/ssd already had it) and a
  per-measure **`gap_reason`** column to all 5 HEDIS golds (KED is compound: "No eGFR" / "No uACR" / "No eGFR or uACR").
  Added **Clinic / Panel / Gap Reason** dimensions to the 5 compliance metric views + gold column comments. Ran
  measures → semantic. Verified: KED now sliceable by Clinic (was impossible — no clinic col), and care-gaps-by-reason
  works (KED "No uACR test" = 1,135 is the dominant gap; BPD "not controlled" 685 vs "no reading" 49).
- **Snippet density (demo-critical), all as code in the `*.geniespace.json` bodies:**
  - Expanded `care_protocol_agent`: 5→6 measures (added SSD), **6→19** example-SQL snippets (clinic/panel/gap-reason/
    age-band/worst-clinic/compare-all-six), 8→10 sample questions, instructions teach the new dimensions.
  - New `protocol_adherence_agent` (AG-1): protocol_adherence + mad metric views + gold_protocol_adherence +
    gold_adherence_mad + panel_roster + panel_pcp_transition + protocol_watch_findings; **14** example SQLs incl.
    "which clinic has the lowest Step-3 adherence", pre/post-handoff comparison, and the latest protocol-watch drift.
  - Net: curated snippets **6 → 33** across two scoped agents (kept separate for Genie accuracy, per the review).
- **Source-document volume (your PDF question):** the 7 Oct-30 Downloads PDFs had their *facts* mined into
  `source_extracts/` on 10-31, but the raw PDFs were never volume-synced. Added a **second** volume
  `source_documents` + `stage_source_documents` job staging the 9 facts-only Markdown files (extracts + corpus) for
  Genie Code Pages **bulk import**. Licensing guardrail: raw proprietary PDFs (NCQA SSD, HEDIS Toolkit, Johns Hopkins
  GSD) are **not** volume-synced; public-domain PDFs (VA/DoD CPG, CMS QRS) are a documented manual step. See RUNBOOK.

**Gotcha:** Genie `data_sources.tables`/`metric_views` must be **sorted by identifier** in the `.geniespace.json`
or the space API rejects it (`must be sorted by identifier`).

**Deferred / did NOT do (with reasons):** MV-2/3/4, AG-2/3, dev-schema metric views (MV-5) — see the table.
Bulk import itself + raw-PDF upload are manual (RUNBOOK). Nothing destructive done.

### 2026-10-31 (latest) — SSD measure built, deployed, and run on ECT (ADR-0017); live

**Did (committed + applied to ECT — deploy/run authorized by Eli):**
- **Confirmed Synthea has no behavioral-health signal** (25k patients: 0 SMI dx, 0 antipsychotic orders) —
  so SSD's cross-domain cohort is synthesized, not derived.
- **`src/data_generation/ssd_cohort.py`** (new job `ssd_cohort`): seeded/deterministic SSD cohort — SMI dx
  (F20/F25/F31) + antipsychotic dispensing + modeled screening. Screening rate is EMERGENT (per-patient
  logistic of engagement + smooth per-clinic effect), not injected. Antipsychotic dispensing carries a RxNorm
  SCD that subsumes to an ingredient via `rxnorm_closure` (7 SCD children added to `rxnorm_hier.csv`); the
  pre-existing-DM exclusion is real diabetes-cohort overlap. Writes `care_ssd_cohort`.
- **`gold_adherence_ssd`** added to the measures pipeline (computed from the cohort via value sets + closure);
  **`ssd_compliance` metric view activated** (moved out of `pending/`) + gold column comments.
- **Ran the full reflow on ECT:** `setup` (rxnorm_closure 116 rows w/ antipsychotic SCDs; value_set_segment
  54) → `ssd_cohort` → `measures` → `semantic`. Result live: **cohort 846, excluded (pre-existing DM) 96,
  eligible 750, screened 521 → 69.5% SSD rate**; recomputed gold == model truth. Emergent clinic spread
  CLINIC-05 51.5% … CLINIC-08 81.9% (no hard drift). The governed `care_protocol_semantic.ssd_compliance_metrics`
  view re-aggregates correctly via `MEASURE()` by Clinic and Age Band.
- **Fix (ADR-0017 follow-up):** the SSD metric view was `version: 0.1` (only name/expr/window/partition) but
  used 1.1 fields → invalid-definition on apply; bumped to `1.1` to match the other 7 views.

**Gotchas captured:**
- `bundle deploy` updates the Genie space, which validates that every referenced
  `care_protocol_semantic.*_compliance_metrics` view EXISTS — so the first deploy after creating that schema
  fails on the Genie space until `semantic` has created the views. Order: deploy (Genie errors, files still
  upload) → run `semantic` → deploy again (Genie resolves). The ADR-0013 relocation is now effectively applied;
  the old `care_protocol.*_compliance_metrics` views still exist (the confirm-gated drop is still pending).
- Metric-view YAML: `version: 1.1` is required for `comment`/`synonyms`/`display_name` on dimensions/measures.

### 2026-10-31 (later) — A4 Lakebase RAG **applied to ECT**; doc-RLS verified live; RLS grant bug found + fixed (ADR-0016)

**Did (external writes to ECT — confirmed with Eli; preferred Lakebase Search path):**
- **Lakebase Search enabled** on the `care-protocol` project (Eli clicked the irreversible Settings toggle;
  `lakebase_vector` + `lakebase_text` now load — the CLI exposes no flag for this, UI-only, confirmed by probe).
- **Applied `src/retrieval/lakebase/schema.sql`** to `projects/care-protocol/branches/production/endpoints/primary`
  (`databricks_postgres`): `rag` schema, 4 tables, the **`lakebase_bm25` + `lakebase_ann`** indexes (preferred,
  not the pgvector/GIN fallback), roles, RLS. **Loaded the corpus** (`lakebase_rag_corpus.py --emit_demo_roles`):
  **7 docs → 36 chunks**, 13 ACL rows, 3 group memberships; `REINDEX` of the BM25 index. Idempotent, re-runnable.
- **🔒 Live doc-level RLS verified** (`tests/test_rag_rls.py`, +perm tracer): all **4 negative-security tests pass** —
  analyst is denied the care-team-only patient letter `LETTER-EYE-TRC-0003`, clinician gets it, both see the
  population protocol, and RLS holds even when the query doesn't join the ACL tables. Confirmed on **both** the
  BM25 (`search_ext=True`) and lexical-fallback paths; the analyst's eye-exam query returns the letter filtered out.

**Fixed (committed source — bug the live test caught, invisible to the local structure test):**
- **RLS grant contradiction (ADR-0016).** `schema.sql` §8 revoked the reader's SELECT on `document_acl` /
  `group_membership` (so a reader can't enumerate org ACLs/memberships), but the policy `USING` clauses read
  exactly those tables — and Postgres evaluates policy predicates **as the invoking role**, so every read died
  `permission denied for table group_membership`. Fixed by encapsulating the ACL decision in a **`SECURITY
  DEFINER` function `rag.acl_allows(document_id, caller)`** (runs as the owner, reads the control tables, returns
  only a boolean; `EXECUTE` granted to `rag_reader`, direct SELECT still revoked). `current_user` is captured in
  the policy/invoker context and passed in as an argument (inside a definer body it would resolve to the owner).
  Both policies now share the function, so `documents` also honors DENY-precedence (no behavior change on the
  allow-only corpus). Re-applied + re-tested green.
- **`psycopg` dependency was undeclared** — `a4_lakebase.py` imports it but `pyproject.toml` didn't list it.
  Added a `lakebase = ["psycopg[binary]>=3.1"]` optional extra.

**Didn't (held for Eli):**
- **Embeddings not loaded** — `rag.chunks.embedding` is 0/36, so **semantic + hybrid modes return nothing yet**;
  lexical/BM25 (the security story) is complete. Loading them is the optional showcase step (`lakebase_embed.py`
  → gte-large-en model-serving calls + DB writes) — confirm to run.
- **Not committed yet** — the whole 2026-10-31 batch (prior entry) + this session's fixes are still uncommitted.

### 2026-10-31 — A4 Lakebase RAG re-aligned to a document corpus + doc-level RLS; care-protocol PDFs mined; SSD + GSD-GMI drift (ADR-0014, ADR-0015)

**Context:** reviewed Eli's "Lakebase Search Document Level Authorization" design doc and 7 public care-protocol
PDFs; re-aligned the A4 arm and allocated the PDF facts across RAG / Pages / metric views.

**Did (committed as source; NOT yet applied to ECT — external writes are confirm-gated):**
- **Mined 7 public PDFs** → `docs/care_protocol/source_extracts/{hedis_measure_specs,vadod_diabetes_cpg,provider_coding_docs}.md`
  (facts only; public-domain sources attributed; no proprietary text reproduced).
- **RAG corpus (ADR-0014):** new multi-doc corpus `docs/care_protocol/corpus/*.md` (glycemic targets &
  deprescribing, cardiorenal pharmacotherapy, retinal cadence, SSD behavioral-health screening, MY2026 payer
  memo, patient-specific eye-exam letter) with two access scopes.
- **Lakebase RAG component:** `src/retrieval/lakebase/schema.sql` (rag.documents/chunks/document_acl/
  group_membership + Lakebase Search indexes + RLS + roles, pgvector/full-text fallback);
  `scripts/lakebase_rag_corpus.py` (deterministic chunker → load SQL: 7 docs → 36 chunks);
  `A4RagRetriever` in `src/retrieval/a4_lakebase.py` (`search_documents` lexical/semantic/hybrid, cited
  passages, end-user identity / `SET ROLE`); access manifest `context/value_set_manifests/rag_access_manifest.yaml`.
- **Tests:** `tests/test_rag_corpus_build.py` (7 deterministic tests — **pass locally**);
  `tests/test_rag_rls.py` (design-doc §13 negative-security / `+perm`; skips without a live Lakebase).
- **Allocation (ADR-0015):** **SSD** added — `docs/ontology/pages/ssd.md`, value sets in `value_sets_demo.csv`
  (SSD_SMI_COHORT, SSD_ANTIPSYCHOTIC, SSD_GLUCOSE_HBA1C, EXCL_PREEXISTING_DM), `DRUGCLASS-ANTIPSYCHOTIC` +
  ingredients in `rxnorm_hier.csv`, and a **pending** metric view `src/semantic/metric_views/pending/ssd_compliance.metric_view.sql`.
  **GSD-GMI MY2026 drift** encoded as MY2026 rows in `value_sets_demo.csv` (adds LOINC 97506-0).
  New Page `document-access-scope.md`. Benchmark set expanded to 17 questions (`pdf_eval_questions.json`:
  +classes 6-7 RAG, +drift, +security) with per-question expected capability-map winners.

**Didn't (deferred to Eli — confirm-gated external writes / larger work):**
- **Not applied to ECT.** Pending (RUNBOOK "A4 Lakebase RAG"): verify Lakebase Search capability → **enable
  Lakebase Search** (irreversible, restarts computes) → apply `schema.sql` → load corpus → embed `rag.chunks`
  → run the live RLS test. Terminology CSV edits (SSD value sets, antipsychotic class) take effect on the next
  `bundle run setup -t ect` (reflow: setup → epicize → measures → semantic).
- **`gold_adherence_ssd` not built** — SSD needs a behavioral-health cohort (SMI dx + antipsychotic dispensing
  + glucose/HbA1c) in the data-gen + measures pipeline. The pending metric view activates once it lands. (Next.)
- **ai_parse_document/ai_prep_search ingestion** of the real PDFs (design doc §6) scaffolded in docs only — the
  deterministic local chunker is the committed reproducible path; the AI-functions path is a showcase next step.
- **Ontobricks** untouched (Eli-owned, ADR-0005).

### 2026-10-30 — metric views relocated to `care_protocol_semantic` (ADR-0013)

**Did (committed as source, NOT yet applied to ECT):**
- Chose option **B** (relocate as code, over the UI-exclude) to stop the Ontobricks entity scan choking on the
  `*_compliance_metrics` metric views: the 7 metric views now target a new **`care_protocol_semantic`** schema
  (`source:` still `care_protocol.gold_adherence_*`). Reproducible, survives a fresh FEVM rebuild. See ADR-0013.
- Touched: `resources/schemas.yml` (declare schema), `src/semantic/metric_views/*.sql` (view → `{semantic_schema}`),
  `apply_metric_views.py` (+`--semantic_schema`), `resources/jobs.yml` (semantic + seed_query_history params),
  `seed_query_history.py` (metric-view queries → `{sch_sem}`), `care_protocol.geniespace.json`,
  `quality_by_age.lvdash.json`, and the five `docs/ontology/pages/*.md` `related_assets`. `benchmark_questions.json`
  unchanged (scorer substring-matches the unqualified view name). `bundle validate -t ect` passes.

**Didn't (deferred to Eli — external ECT writes, confirm-writes policy):**
- **Not applied to ECT.** Two writes pending approval: (1) `databricks bundle deploy -t ect --profile ECT`
  (creates `care_protocol_semantic` + redeploys Genie space/dashboards), then `bundle run semantic -t ect`
  (creates the views in the new schema); (2) **drop the 7 old metric views** in `care_protocol` after verifying
  the new ones resolve. Until the drop, the stale views remain in the scanned base schema.
- **Ontobricks scope** (Eli-owned, ADR-0005): keep the scan source at `care_protocol.{bronze_*,silver_*,gold_*}`
  + `care_protocol_terminology.*`; do **not** add `care_protocol_semantic`.

### 2026-10-30 — dashboards + semantic metadata (post-M28)

**Did (committed, live on ECT):**
- **Fixed the flagship HEDIS dashboard** (`hedis_quality.lvdash.json`), which was broken on three counts:
  1. published with `embed_credentials: false` → broken for every viewer without direct grants; now
     `embed_credentials: true`, set **declaratively in `resources/dashboards.yml`** (the DAB default is false).
  2. widget query bindings were named `q` → renderer errored "Missing query `main_query`"; renamed all to `main_query`.
  3. redesign — labeled KPI tiles (frame titles), split title/subtitle, aggregated **care-gaps-by-reason**
     leading the gaps section, raw patient list demoted to a labeled worklist.
- **Two new dashboards** (DAB-managed, `embed_credentials: true`, SQL tested on ECT before deploy):
  - **Measure Drift & Ontology Impact** (`measure_drift.lvdash.json`) — terminology drift (KED_EGFR value
    set modernized for MY2026 drops the MDRD code the data uses → eGFR coverage collapses 4,419 → 0 on
    identical data), subsumption closures (ICD-10 cohort, RxNorm statins), and the care-protocol graph.
  - **HEDIS Diabetes Quality by Age Band** (`quality_by_age.lvdash.json`) — **first consumer of the governed
    metric views** (`MEASURE()` grouped by `Age Band`): one definition, shared by BI and Genie.
  - Both committed in `2a4318f` alongside the flagship fixes.

**Did (committed as source, NOT yet applied to ECT):**
- Semantic metadata polish (fills comment/synonym gaps found in review):
  - +12 gold temporal-column comments (`measurement_year`/`period_start`/`period_end` on bpd/eed/spd/ked).
  - +5 ontology tables fully commented in `terminology.comments.sql` (icd10_hier, rxnorm_hier,
    rxnorm_statin, loinc_parts, protocol_edges).
  - `Measurement Year` + `Measure` dimension comments on all 5 `*_compliance.metric_view.sql`.

**Didn't (deferred / open):**
- **Semantic metadata not applied to ECT** — the `semantic` job (apply_comments + apply_metric_views) was
  intentionally held. Live UC still has pre-edit comments/metric-view YAML. Apply with
  `databricks bundle run semantic -t ect --profile ECT`.
- **Benchmark leaderboard dashboard not built** — no results table exists (the `benchmark` job logs to
  MLflow only). Trivial to add once benchmark output is persisted to a UC table.
- **M28 assets not covered** — `gold_adherence_mad` and `gold_protocol_adherence` (+ their metric views)
  were left to the M28 owner; their tables still have ~0 column comments and are absent from dashboards/Genie.
- `protocol_watch` job was created on ECT as a side effect of `bundle deploy` (it is defined in the
  working tree's `jobs.yml`); schedule is **PAUSED** — no runs or notifications.

**Gotchas captured (for next time):**
- AI/BI widget query bindings must be named `main_query`, or widgets error "Missing query `main_query`".
- The DAB `dashboards` resource **does** manage publish state via `embed_credentials` (default false) — set
  it in `resources/dashboards.yml`; never `lakeview publish` out of band (a redeploy would revert it).
- `bundle deploy` ships the **entire** working tree (all resources + file sync), not just the changed one.
