HEDIS Context Layer Demo — Coding-Agent Prompt & Build Roadmap
Using Epic-shaped data, SNOMED CT and LOINC to show what each semantic and retrieval layer adds on Databricks
Executive summary
Build one synthetic Epic-shaped (Clarity-like) diabetes population. Run it through a medallion pipeline into a HEDIS-aligned adherence event log. Then layer context onto it step by step: UC metadata → metric views → domains/Pages/certification → domain Genie Agents → inferred Genie Ontology. Around that core, run three other retrieval approaches: ontology as data (SNOMED/LOINC closure tables), Lakebase hybrid search over unstructured documents, and an Ontobricks OWL knowledge graph served over MCP. Genie One is the front door. One MLflow harness scores every approach against ground truth that is known by construction. A modified Hospital Control Tower app follows 5–6 planted "tracer" facts through every layer and every approach, and includes a Drift Lab that shows a HEDIS spec change being absorbed by editing one governed definition.
The story to land: semantics answer most questions once they live in governed, certified definitions in one place. Each other approach earns its keep on a specific question type (unstructured evidence, hierarchy reasoning, multi-hop relationships). You can measure all of that on one platform.
1. Things the coding agent won't know (read first)
Product state (as of late Oct 2026; check each in the target workspace)
Genie Ontology is the context layer behind Genie One and Genie Code. It combines modeled UC semantics (metric views, domains, Pages, certification) with inferred snippets. Those snippets are pulled from metric views, dashboards, Genie Agents and query history, and each is scored for authority, usage and freshness. Docs call it Public Preview. Internal tickets say it has been on by default since June and available to everyone since Aug 13. Check that it's actually enabled. One field team found it switched off in a production workspace.
No standalone ontology graph UI ships today. The ontology shows up only as citations and "Ontology References" in Genie One answers. An "Ontology Home" is still at PRD stage. Your app has to supply that visual.
Precedence, per field guidance: certified Pages outrank inferred snippets. When answering, the ontology checks Genie Agents and dashboards first, then metric views, then UC metadata. Domains add weight for users assigned to them.
Standalone Genie Agents did not use the ontology as of July 2026; Genie One does. This difference between benchmark arms is real. Re-check it before you present.
Genie One MCP went GA around Sep 22. It's the right programmatic front door for benchmarking. The Genie Agent MCP is read-only and keeps no conversation history. Use the Conversation API for multi-turn.
Pages: Beta. The public CRUD API was expected in October 2026. Until it ships, bulk-create Pages with Genie Code bulk import (upload a CSV/markdown glossary; it proposes drafts for you to review). Known gap: bulk import drops page-to-page relationships, so add "related pages" by hand.
Domains: REST API in Beta, plus the Terraform resource databricks_domain. Assets are assigned to domains through governed tags.
Genie Agent config can be exported and imported as JSON via Declarative Automation Bundles (DABs).
Lakebase Search: lakebase_vector (pgvector-compatible, lakebase_ann index) plus lakebase_text (BM25, lakebase_bm25 index). Build the BM25 index after loading data, because corpus statistics are computed at build time, not incrementally. Synced tables can map a UC column to vector(n) or tsvector.
Ontobricks is a Databricks Labs project with no SLA (the RSA series used v0.8.1). It deploys two Apps (ontobricks UI/API and mcp-ontobricks) with make deploy and make bootstrap-lakebase. It needs Lakebase (registry), a SQL warehouse and a Model Serving LLM. In the UI, run Settings → Registry → Initialize. Only Published domains are exposed over MCP. MCP tools: list_domains, select_domain, describe_ontology, list_entity_types, describe_entity, get_graphql_schema, query_graphql, get_entity_context, invoke_entity_action, compute_virtual_attributes.
Genie cannot natively query a knowledge graph. Ontobricks results reach users only through a custom agent calling MCP.
A useful internal result to reproduce: an RSA comparison found Genie scored 4/8 on relationship-traversal questions versus Ontobricks at 8/8. After adding a precomputed closure view, column metadata and example SQL, Genie also reached 8/8. The relationship meaning didn't go away; it moved from OWL into views and metadata. Your SNOMED closure table is the healthcare version of that experiment.
Evaluating Genie One is non-deterministic. Results depend on the ontology state and the caller's permissions. Run each question 3–5 times, use a fixed service principal per arm, and report variance. Genie Agent benchmarks score SQL correctness, not the natural-language answer.
Healthcare/terminology realities
Epic Clarity schemas are proprietary. Generate Clarity-like tables using the public names in the research doc (PATIENT, PAT_ENC, ORDER_PROC, ORDER_RESULTS, CLARITY_COMPONENT, IP_FLWSHT_MEAS, IMMUNE, PROBLEM_LIST…). Label them "Clarity-shaped, synthetic." Never imply real Epic data.
Synthea generates realistic synthetic patients (FHIR R4 and CSV) already coded in SNOMED (conditions/procedures), LOINC (observations), RxNorm and CVX. Use it as the clinical engine, then "Epic-ize" the output: add local IDs, partial LOINC mapping, flowsheet rows and Care Everywhere results.
Licensing (manual): SNOMED CT US Edition needs a free UMLS license (NLM, takes 1–3 business days). LOINC is a free download from Regenstrief (needs an account); it includes the Part file and the multiaxial hierarchy. NCQA HEDIS VSD is licensed. For the demo, use the free VSAC eCQM value sets as proxies: CMS122 (A1c >9%), CMS165 (BP control), CMS131 (eye exam), CMS951 (kidney health evaluation), plus a VSAC API key. Label everything "HEDIS-aligned (eCQM-proxied value sets)."
LOINC ↔ SNOMED: LOINC names the question and SNOMED the answer/finding/procedure. LOINC's six parts (Component, Property, Time, System, Scale, Method) are the natural "LOINC component" ontology axis. Regenstrief and SNOMED International also publish a joint LOINC–SNOMED ontology/extension. Check its current release and license before relying on it; the Part file plus multiaxial hierarchy is the safe fallback.
Don't invent codes. Every SNOMED/LOINC code in the build must come from the loaded release files or VSAC. The agent should look codes up, never hard-code them from memory. The well-known anchors from the research doc (4548-4, 17856-6, 98979-8, 9318-7, 8480-6, 8462-4, 44261-6) should still be validated against the files.
Real measure drift to use: HEDIS renamed HBD → GSD (Glycemic Status Assessment) and added GMI. eGFR moved toward race-free CKD-EPI 2021 (98979-8). NCQA is moving to ECDS/digital-only (the "-E" measures). These make realistic drift scenarios.
2. Target architecture
Layer
Databricks components
Purpose in demo
Sources
Synthea → Clarity-like Parquet in UC Volume; synthetic PDFs/notes; LOINC, SNOMED, VSAC files
Realistic, PHI-free, ground truth by construction
Bronze/Silver/Gold
Lakeflow Declarative Pipelines; expectations; ai_parse_document/ai_extract for PDFs
Code mapping, gaps, abstraction
Terminology-as-data
terminology.snomed_concept, snomed_isa_closure, loinc_parts, value_set, value_set_version
Ontology as governed relational data (native approach)
Gold facts
adherence_event_log (patient × protocol × step × period), hedis_member_measure, protocol_vs_hedis_recon
One row per measurable fact
Semantic layer
UC comments/tags/PK-FK (dbxmetagen), metric views (YAML in Git), certification
Governed measures
Modeled ontology
Domains/subdomains, Pages (glossary + measure specs), certified assets
Authority for Genie One
Agents
Domain Genie Agents (Quality Measures, Clinical Terminology, Protocol Adherence)
Curated structured retrieval
Front door
Genie One (UI and MCP)
Unified, ontology-grounded answers
Unstructured
Lakebase Search (BM25 + vector + RRF hybrid) over specs, protocols, notes, scanned letters
Evidence structured data can't see
Knowledge graph
Ontobricks (OWL + R2RML + SHACL + triplestore) + mcp-ontobricks
Formal ontology / multi-hop
Orchestration
Custom supervisor agent (Model Serving or App) using MCP tools
Combined approach
Evaluation
MLflow 3 GenAI eval, UC eval datasets, Delta results
Benchmark and ablation
Experience
Modified Hospital Control Tower App (FastAPI + React, OBO auth, Lakebase app state)
Tracers, arena, scorecard, drift
Suggested domains (keep it small): Clinical Quality (subdomains: HEDIS Measures, Protocol Adherence), Clinical Terminology (LOINC, SNOMED, Value Sets), Patient & Encounter (Clinical Operations). One Genie Agent per subdomain that people actually ask about. One owner per kind of knowledge.
3. Scope: measures and protocol
HEDIS measures: GSD, KED, EED, BPD, SPD. These map to protocol steps DM-01/02, DM-08, DM-09, DM-06 and DM-07.
Protocol-only steps to show what HEDIS misses: DM-03 therapeutic inertia and DM-05 cardiorenal therapy.
Exclusions: hospice, palliative care, ESRD/dialysis (KED), bilateral enucleation (EED), frailty plus advanced illness 66+.
Population: ~5–10k Synthea patients (adults with diabetes enriched), measurement years MY2025–MY2026 (MY2026 for drift).
4. Tracer facts (planted, with expected behavior per approach)
Put every tracer in demo.tracer_registry: tracer_id, narrative, patient MRN (TRC-000x), and the expected value at each layer (bronze row ID → silver mapping → gold status → metric impact → expected answer per approach).
ID
Planted fact
What it proves
Expected winner(s)
T1 Send-out A1c
A1c 7.2% from a reference lab under a local COMPONENT_ID with no LOINC mapping
Protocol MET, HEDIS GSD NOT MET (data/coding gap). Adding one mapping row closes the gap
Genie One/Agent via recon table; RAG can't compute it
T2 Scanned eye exam
Retinal exam documented only in an outside-provider PDF letter
Structured approaches miss it. Lakebase hybrid finds it. ai_extract turns it into a supplemental record and EED flips to MET
Lakebase / supervisor
T3 SNOMED descendant
Diabetes coded only with a specific child concept (e.g., a type 2 DM with renal complication concept chosen from the SNOMED file) that isn't in a naive flat code list
The closure table / OWL hierarchy puts the patient in the denominator; naive lists miss them
Ontology-as-data, Ontobricks, Genie with closure view
T4 Legacy eGFR
eGFR coded with an older, race-based LOINC instead of 98979-8
A value set version change alters KED status → drift demo
Metric view + versioned value set
T5 ED blood pressure
Last BP 128/78 recorded in the ED; last outpatient BP 148/92
BPD rule excludes ED readings, so NOT MET. Tests whether context encodes the rule
Genie One w/ Page + metric view; RAG often wrong
T6 Hospice exclusion
Patient with all gaps but a hospice encounter
Denominator exclusion, not a failure
Structured approaches
Use synthetic names like "Alex Tracer" and record IDs, so live searches are easy and obviously fake.
5. Benchmark design (outcome 2)
Recommendation: build a reusable harness package (hedis_eval/). A Databricks Job runs it and writes results to Delta. A notebook drives it for the live demo. The app reads the results table. That covers both the holistic benchmark and the custom notebook in one design.
Arms
Arm
Path
Notes
A1 Genie One
Genie One MCP
Full ontology; front door
A2 Domain Genie Agent
Genie Agent MCP / Conversation API
Curated instructions, example SQL, trusted functions
A3 Context ablation ladder
Same Genie Agent on duplicated schemas: L0 raw → L1 comments/tags → L2 PK/FK + closure views → L3 metric views → L4 Pages/domains/certification → L5 instructions/examples
Shows how much each context component adds
A4 Lakebase RAG
Custom agent: BM25 only / vector only / hybrid RRF
Unstructured sub-ablation
A5 Ontobricks
Custom agent + mcp-ontobricks
Formal KG
A6 Supervisor
Custom agent with Genie One MCP + Lakebase + Ontobricks MCP + UC terminology functions
"Best of all" composite
To run A3, clone schemas (ctx_l0 … ctx_l5) so each level is isolated. Note that Genie One draws on the workspace-wide ontology, so the ablation applies only to Genie Agents. Say so on stage.
Question set (~60–80, ground truth computed by SQL from gold)
Aggregate measure ("GSD rate for MY2025 by PCP")
Definitional/rule ("Do ED BP readings count toward BPD?")
Hierarchy/terminology ("How many patients have any descendant of diabetes mellitus but aren't on the problem list as diabetes?")
Multi-hop relationship ("Patients with CKD on no SGLT-2/GLP-1 whose PCP is in clinic X")
Unstructured evidence ("Is there evidence of a retinal exam for TRC-0002?")
Patient trace (each tracer)
Version/drift ("KED rate under MY2025 vs MY2026 value sets")
Scorers (MLflow mlflow.genai.evaluate)
Deterministic: numeric tolerance match, set match for patient lists, correct exclusion handling
Routing: did the arm use the certified asset / correct Genie Agent / correct tool (read from trace spans)
Groundedness and citation presence (LLM judge, guidelines-based)
Tracer recall: did the answer surface the planted fact
Ops: latency p50/p95, tokens, estimated cost, error rate
Run 3–5 repeats per question and report mean and variance. Store results in eval.results(arm, level, question_id, category, run_id, score_*, latency_ms, trace_id).
6. Drift Lab (show how easy updates are)
Three scripted scenarios, each done as one Git PR → DAB deploy → instant effect:
Value set update (T4): add the MY2026 value_set_version that drops the legacy eGFR code. The metric view filters by measurement_year's active version. KED rate changes, and Genie One answers change with no prompt edits.
Rename/alias: HBD → GSD. Update the Page synonyms and the metric view comment. "What's our HBD rate?" still resolves correctly.
Threshold variant: add an ADA protocol BP <130/80 measure next to HEDIS BPD <140/90 in the same metric view, so "HEDIS vs protocol" becomes one question.
The contrast to show: the Lakebase corpus still holds the MY2025 spec PDF. Without version metadata filters, RAG returns the stale rule. A governed semantic layer updates in one place; document corpora have to be re-curated.
The app's Drift tab shows the YAML diff, the rates before and after, a re-run of the drift benchmark subset, and lineage.
7. App (outcome 3): modify Hospital Control Tower
Tabs:
Quality Control Tower: HEDIS rates, gap lists, and the protocol-vs-HEDIS 2×2 (aligned / data gap / measure too narrow / true gap) with drill-down to patients
Tracer Journey: pick a tracer to see a step graph Bronze row → Silver mapping (LOINC/SNOMED) → terminology closure → gold event → metric view → Page/domain/Genie Agent → each arm's answer with its MLflow trace spans. Data comes from tracer_registry, system.access.table_lineage/column_lineage, and MLflow search_traces
Retrieval Arena: one question, all arms live side by side, showing answer, citations/tools used and latency
Benchmark Scorecard: accuracy by arm × category, an ablation ladder chart (L0→L5) and cost/latency
Drift Lab: as above
Ontology Explorer: SNOMED/LOINC subgraph for a tracer (from the closure tables), with a link to Ontobricks' own explorer
Use OBO auth so UC permissions apply. Store app state and pinned questions in Lakebase.
8. Roadmap (≈6 weeks; 👤 = manual, 🤖 = coding agent)
Phase
Wk
Work
Owner
Gate
0 Setup
1
Enable previews (Genie Ontology, Managed MCP, Lakebase Search, Domains, Pages); UMLS license; LOINC + VSAC accounts; catalog hedis_demo; service principals per arm; clone/inspect control tower repo
👤
Licenses in hand; previews verified
1 Data
1–2
Synthea run w/ seed; Epic-ize to Clarity-like tables; plant tracers; synthetic PDFs/notes; tracer_registry
🤖
Tracers visible in bronze
2 Pipeline + terminology
2
Lakeflow DP bronze→silver→gold; load LOINC/SNOMED/VSAC; closure table; adherence event log; recon
🤖
Gold rates reproduce tracer expectations (unit tests)
3 Semantic layer
3
dbxmetagen comments/tags, PK/FK; metric views (YAML in repo); dashboards
🤖 + 👤 review
Metric views match gold SQL
4 Modeled ontology
3
Domains (API/Terraform); Pages (Genie Code bulk import from repo markdown); related-page links; certification
👤 (🤖 drafts content)
Pages published + certified
5 Genie Agents
3–4
3 domain agents (instructions, example SQL, trusted UC functions, benchmarks) via DAB JSON; ablation copies
🤖 + 👤 tune
Native benchmark ≥85%
6 Seed inferred ontology
4
Run realistic query history and dashboard usage; wait for extraction; confirm citations in Genie One
👤
Genie One cites Pages/metric views
7 Lakebase
4
Chunk/parse docs, embed, sync to Lakebase; BM25 + ANN indexes; hybrid RRF function; version metadata
🤖
T2 retrieved top-3
8 Ontobricks
4–5
Deploy; design OWL (Patient, Encounter, Condition⊑SNOMED, Observation⊑LOINC, Measure, ValueSet, ProtocolStep); R2RML auto-map, review; SHACL; build; Publish
👤 UI + 🤖 deploy/scripts
MCP describe_entity(TRC-0003) returns hierarchy
9 Agents + harness
5
Lakebase agent, Ontobricks agent, supervisor; hedis_eval package; question set; job
🤖
All arms run end to end
10 App
5–6
Fork control tower; 6 tabs; deploy via DAB
🤖
Tracer Journey works for all 6
11 Drift + rehearsal
6
Drift PRs; dry runs; screenshot fallbacks; talk track
👤 + 🤖
2 clean rehearsals
9. Risks and mitigations
Ontology extraction lag or no citations: seed usage early (week 4) and keep screenshots as a fallback.
Preview APIs (Pages, Domains) change: keep the content as markdown/YAML in Git, so the source of truth is portable either way.
Ontobricks version churn: pin a release tag, and record the deploy config in the repo.
Genie One variance: use repeats, a fixed principal, and report confidence intervals instead of single numbers.
Licensing: never redistribute SNOMED/LOINC/VSAC content in the public repo. Load it at runtime from a UC Volume.
Overclaiming: label every feature GA/Preview/Labs in the deck. Ontobricks is not a supported product.
10. The coding-agent prompt
Use the master prompt below once. Then run each phase in its own session with "Execute Phase N per AGENTS.md". Smaller, gated sessions beat one giant run.
# ROLE
You are a senior Databricks solutions engineer and healthcare data engineer. You write production-quality, idempotent, tested code deployed with Declarative Automation Bundles (DABs). You are careful with clinical terminology and never fabricate codes or APIs.

# OBJECTIVE
Build a demo on Databricks that shows the value of semantics, ontology and context for HEDIS diabetes measures computed from synthetic Epic-Clarity-shaped data, and benchmarks multiple retrieval approaches:
(A1) Genie One via Genie One MCP, (A2) domain Genie Agents via Genie Agent MCP/Conversation API,
(A3) a context ablation ladder L0–L5, (A4) Lakebase hybrid search RAG agent (BM25/vector/hybrid),
(A5) Ontobricks MCP agent, (A6) a supervisor agent combining A1+A4+A5 + UC terminology functions.
Deliver: pipeline, terminology layer, semantic layer, Genie assets, Lakebase index, Ontobricks integration, MLflow eval harness, and a modified Hospital Control Tower app (repo: github.com/eliswanson-db/hopital_control_tower) with tabs: Quality Control Tower, Tracer Journey, Retrieval Arena, Benchmark Scorecard, Drift Lab, Ontology Explorer.

# NON-GOALS
- No real PHI. No claims of real Epic schema fidelity ("Clarity-shaped, synthetic").
- No NCQA-licensed content. Use VSAC eCQM value sets (CMS122, CMS165, CMS131, CMS951) as HEDIS-aligned proxies.
- Do not redistribute SNOMED/LOINC/VSAC files in git; load from UC Volume paths in config.

# ENVIRONMENT (fill in)
WORKSPACE_HOST=...  CATALOG=hedis_demo  WAREHOUSE_ID=...  LAKEBASE_PROJECT=...
LLM_ENDPOINT=...  EMBEDDING_ENDPOINT=...  TERMINOLOGY_VOLUME=/Volumes/hedis_demo/raw/terminology
SP_PER_ARM={a1:...,a2:...,...}  ONTOBRICKS_MCP_URL=...  GENIE_ONE_MCP_URL=...  GENIE_AGENT_IDS={...}

# GROUND RULES
1. Before using any Databricks API/SDK/SQL feature, verify it exists in current docs or the installed SDK. If a preview API is unavailable (e.g., Pages CRUD), write a MANUAL step in docs/RUNBOOK.md with exact UI instructions plus the generated content, and continue.
2. Never hard-code clinical codes from memory. Resolve all SNOMED/LOINC/RxNorm/CVX codes from loaded release files or VSAC; write a validation test that every code referenced in config exists in the loaded terminology tables.
3. Everything idempotent (CREATE OR REPLACE / MERGE), parameterized by catalog/schema, deployable via `databricks bundle deploy`.
4. Maintain AGENTS.md (decisions, conventions, open questions) and docs/RUNBOOK.md (manual steps, ordered). Update both at the end of every phase.
5. At each PHASE GATE: run tests, print a summary of what was built, list manual steps for the human, then STOP and wait for confirmation.
6. Prefer native primitives: Lakeflow Declarative Pipelines, UC metric views (YAML in repo), UC functions, Lakebase, MLflow 3 GenAI eval, Databricks Apps (FastAPI + React, OBO auth).
7. Ground truth must be computable by SQL from gold tables. Every tracer's expected value at every layer lives in demo.tracer_registry.

# DOMAIN KNOWLEDGE YOU MUST APPLY
- Protocol step model: Who → What → When → Evidence → Exceptions. Gold table adherence_event_log has one row per patient × protocol × step × period with columns: patient_id, protocol_id, step_id, period_start, period_end, eligible_flag, eligibility_date, due_date, status (MET, MET_LATE, NOT_MET, PENDING, EXCEPTION, EXCLUDED), evidence_datetime, evidence_source, evidence_code, code_system, evidence_value, exception_reason, days_to_completion, measure_id, attributed_pcp, department.
- Measures: GSD (most recent A1c/GMI in MY: <8% and >9% inverse), KED (eGFR AND uACR in MY; uACR can be a quantitative albumin + creatinine pair within 4 days; age 18–85; exclude ESRD/dialysis), EED, BPD (<140/90 most recent; exclude acute inpatient/ED readings and same-day procedure readings), SPD (ages 40–75, statin received; PDC ≥80%). Protocol-only: DM-03 therapeutic inertia (intensification within 3 months of above-target A1c), DM-05 SGLT-2/GLP-1 for ASCVD/HF/CKD.
- Use specimen collection / result time, never order time, for lab evidence.
- Exclusions are not failures: model hospice, palliative care, frailty+advanced illness (66+), death as EXCLUDED.
- Protocol vs HEDIS reconciliation 2×2: aligned / data-coding gap / measure too narrow / true care gap.
- Terminology: build snomed_isa_closure (ancestor_id, descendant_id, depth) from the SNOMED RF2 relationship file (typeId = 116680003 'is a', active=1). Load LOINC parts (Component, Property, Time, System, Scale, Method) and the multiaxial hierarchy. value_set(value_set_id, code, code_system, version, measurement_year, effective_from, effective_to).

# PHASES
P1 Data: Run Synthea (fixed seed, ~5–10k pts, enrich adult T2DM). Transform to Clarity-shaped tables (PATIENT, PAT_ENC, PAT_ENC_HSP, PAT_ENC_DX, PROBLEM_LIST, ORDER_PROC, ORDER_RESULTS, CLARITY_COMPONENT [local COMPONENT_ID with LOINC mapping, ~8% intentionally unmapped], ORDER_MED, IP_FLWSHT_MEAS [flowsheet rows partially LOINC-mapped], IMMUNE, COVERAGE, CLARITY_SER, CLARITY_DEP, external/Care Everywhere results). Generate synthetic unstructured docs: outside eye-exam letters (PDF), progress notes, a local diabetes protocol PDF, MY2025 and MY2026 measure-spec summaries, payer policy memo. Plant tracers T1–T6 (see TRACERS). Write tracer_registry.
P2 Pipeline + terminology: Lakeflow DP bronze→silver (code mapping, expectations quarantining unmapped codes rather than dropping) → gold (adherence_event_log, hedis_member_measure, protocol_vs_hedis_recon). ai_parse_document + ai_extract over PDFs → silver.supplemental_evidence (with source doc id, confidence). Tests: each tracer's gold status matches registry.
P3 Semantic layer: table/column comments (use dbxmetagen if available, else generate and human-review), governed tags (domain, code_system, phi=false), PK/FK constraints. Metric views in /semantic/metric_views/*.yaml: hedis_measures (numerator/denominator/rate per measure, by MY, PCP, dept, payer), protocol_adherence, recon. Value-set version resolved via measurement_year. One AI/BI dashboard using the metric views.
P4 Modeled ontology content: generate /semantic/pages/*.md (GSD, KED, EED, BPD, SPD, Care Gap, Data/Coding Gap, Measurement Year, Value Set, LOINC, SNOMED CT, Exclusion vs Exception, HBD→GSD alias) each with definition, synonyms, related assets, related pages. Domain/subdomain spec as Terraform or REST script. If Pages API unavailable → RUNBOOK step for Genie Code bulk import + manual related-page linking + certification.
P5 Genie Agents: 3 agents (Quality Measures, Clinical Terminology, Protocol Adherence) as DAB JSON: instructions, ≥10 example SQL each, trusted UC functions (e.g., terminology.descendants_of(concept_id), measure_status(patient, measure, my)), benchmark questions. Create ablation schemas ctx_l0..ctx_l5 and matching agents.
P6 (human) Seed usage + verify Genie One citations. Provide a script that runs realistic queries to populate query history.
P7 Lakebase: chunk (structure-aware, ~500–800 tokens, overlap), embed via EMBEDDING_ENDPOINT, store with metadata (doc_type, measure_id, measurement_year, version, patient_id nullable). Sync table to Lakebase; create lakebase_ann + lakebase_bm25 (BM25 AFTER load). SQL function hybrid_search(q, k, filters) with reciprocal rank fusion. Also index terminology descriptions (concept search).
P8 Ontobricks: deploy pinned release (make deploy / make bootstrap-lakebase); scripts + RUNBOOK for UI steps: design OWL (Patient, Encounter, Condition, Observation, Medication, Measure, ValueSet, ProtocolStep, Provider; Condition/Observation linked to SNOMED/LOINC classes), R2RML auto-map review, SHACL shapes (e.g., KED numerator requires eGFR AND uACR), build, PUBLISH domain. Smoke test via MCP tools.
P9 Agents + eval: implement arms A4, A5, A6 (tool-calling agent, MLflow-traced, deployable to Model Serving). hedis_eval package: question set (60–80 Q, 7 categories: aggregate, definitional, hierarchy, multi-hop, unstructured, patient-trace, drift), ground truth via SQL, scorers (numeric tolerance, set match, exclusion correctness, routing/tool-use from spans, groundedness judge, tracer recall, latency, tokens/cost), 3–5 repeats, results to eval.results. Job definition in bundle.
P10 App: fork the control tower repo — READ IT FIRST and adapt its existing structure; do not rewrite from scratch. Add the 6 tabs. Tracer Journey reads tracer_registry + system.access.table_lineage/column_lineage + MLflow traces. Retrieval Arena calls each arm live. Use OBO; Lakebase for app state.
P11 Drift: three PR-sized changes (MY2026 value set version dropping legacy eGFR; HBD→GSD alias; ADA <130/80 protocol BP measure beside HEDIS BPD). Drift Lab shows YAML diff, before/after rates, drift-benchmark rerun, and stale-RAG contrast (with and without version filter).

# TRACERS
T1 send-out A1c 7.2% unmapped local component → protocol MET, GSD NOT MET (data gap); fix = add mapping row.
T2 retinal exam only in outside PDF → only unstructured retrieval finds it; ai_extract → supplemental evidence → EED MET.
T3 diabetes coded only as a SNOMED descendant concept absent from a naive flat list → included via closure/ontology.
T4 eGFR with legacy race-based LOINC → KED status changes between MY2025 and MY2026 value set versions.
T5 last BP 128/78 in ED, last outpatient 148/92 → BPD NOT MET.
T6 hospice encounter → EXCLUDED, not a gap.
Names/MRNs: "<First> Tracer", TRC-0001..0006.

# DEFINITION OF DONE
- `databricks bundle deploy` + one orchestrating job builds everything except RUNBOOK manual steps.
- Tests green: code validity, tracer expectations at every layer, metric view parity with gold SQL.
- eval.results populated for all arms; scorecard renders; each tracer traceable end to end in the app.
- README with architecture diagram, demo script (20 and 45 min), and GA/Preview/Labs labels for each feature.

# START
First: read the control tower repo and Ontobricks README, then output a concise plan (repo layout, bundle resources, open questions, required manual steps). Do not write code until I approve the plan.
11. Prompting notes for running the agent
Have the agent keep AGENTS.md current so decisions survive across sessions.
Plan-then-approve each phase. Phase gates stop the agent from "helpfully" faking preview APIs.
Give it the research doc as docs/domain_research.md, so its clinical rules come from your source rather than its own recall.
Ask for tests before features in P2 (tracer expectations as tests). This is how you get ground truth you can trust.
When it fails on a preview feature, the right outcome is a RUNBOOK entry, not a workaround.
