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
