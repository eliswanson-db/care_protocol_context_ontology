# Domain & Platform Context Pack

> **Purpose.** This file is the "stuff a coding agent won't know" — healthcare domain
> facts, licensing landmines, the concrete golden-thread anchors, the benchmark design,
> and Databricks-specific platform knowledge. Feed this to the agent alongside the
> kickoff prompt. The agent should treat this as authoritative context, not as tasks.

---

## 0. The one-paragraph thesis (keep everyone anchored to this)

> The *same* clinical question, answered through retrieval paths of increasing semantic
> richness, produces measurably different answers — and we can prove it. A care protocol
> becomes a guideline, a guideline becomes a HEDIS measure, a measure becomes auditable
> coded data (LOINC says *what was measured*, SNOMED says *what was found*). The value of
> a **context/semantic layer** is that it lets a generic LLM front door (Genie One) reason
> over that chain correctly. We build five retrieval approaches over one Databricks
> lakehouse, trace specific data items end-to-end, benchmark the approaches against a gold
> question set, and show that updating the semantic layer when a measure drifts is a
> config change, not a re-platform.

Everything in this build serves one of three **primary outcomes**:
1. **Value story** — show the impact of ontology, context, and the semantic layer, and
   isolate the contribution of *each* context component (ablation).
2. **Benchmark** — evaluate Genie-ontology vs. unstructured vs. Genie-Agents-via-Genie-One
   vs. custom-agent-via-MCP vs. Ontobricks-MCP, on correctness / faithfulness / latency / cost.
3. **Traceability** — follow specific items through the whole pipeline, visualized in the app,
   plus a measure-drift demo showing how fast the semantic layer updates.

---

## 1. The clinical chain (why any of this exists)

```
Evidence (trials)
  → Clinical guideline (ADA, USPSTF, ACC/AHA)
    → Local protocol / pathway (the health system's own version — usually a PDF)
      → Epic build (order sets, BPAs, Health Maintenance, registries)
        → Coded documentation (orders, results, meds given, flowsheets, billing)
          → Quality measure (HEDIS, CMS eCQM)
```

**Computability levels** (L1 narrative PDF → L2 flowchart → L3 CQL/FHIR PlanDefinition →
L4 the Epic build). HEDIS digital measures and CMS eCQMs are authored in **CQL**. The demo
does *not* need a CQL engine; we model each measure step as config (the "Who → What → When →
Evidence → Exceptions" rule shape).

**Terminology division of labor** — memorize this, it is the heart of the ontology story:
- **LOINC** names the *question/observation* (the lab test, the vital, the survey). `Observation.code` in FHIR.
- **SNOMED CT** gives the *answer / finding / disorder / procedure*. Hierarchical (is-a subsumption).
- **RxNorm** = drugs, **CVX** = vaccines, **CPT/CPT II/HCPCS** = billable services (CPT II is an alternate HEDIS proof route).
- **ICD-10-CM** = diagnoses on claims.

**Why ontology wins (the money demo):** SNOMED is a *hierarchy*. "Patients with diabetes"
should match `Type 2 diabetes mellitus with diabetic nephropathy` via **is-a subsumption**.
A naive keyword/column filter misses it; an ontology-aware path (Ontobricks graph traversal,
or a value-set expansion built from SNOMED descendants) gets it right. Build at least one
golden question that *only* the semantic/ontology paths answer correctly.

---

## 2. The scope decision: Adult Type 2 Diabetes, ambulatory

Diabetes is the right starter — it has public artifacts at every computability level and lines
up with a clean set of HEDIS measures. **Scope the demo to these measures** (from the research's
DM-01…DM-14 template; the HEDIS-linked ones are the benchmarkable core):

| Step  | Measure | Evidence (LOINC / code) | Why it's in the demo |
|-------|---------|-------------------------|----------------------|
| DM-01/02 | **GSD** – Glycemic Status Assessment | HbA1c **4548-4**, 17856-6 | Simplest numerator; the "single lab result" golden thread |
| DM-06 | **BPD** – BP Control <140/90 | Systolic **8480-6**, diastolic **8462-4** | Flowsheet-sourced; shows the "vitals often not LOINC-mapped" data-quality story |
| DM-08 | **KED** – Kidney Health Eval | eGFR **98979-8** (CKD-EPI 2021), uACR **9318-7** | **The hero measure** — "both eGFR AND (uACR OR albumin+creatinine pair ≤4 days apart)". Compound logic + value-set reasoning |
| DM-09 | **EED** – Eye Exam | CPT 92227-92229, CPT II | The "scanned PDF / unstructured" story → unstructured retrieval path |
| DM-07 | **SPD** – Statin Therapy | RxNorm statin class | Shows RxNorm + the "ordered ≠ dispensed (PDC)" nuance |

Keep DM-03/04/05/13/14 (the *protocol-only*, no-HEDIS-measure steps) as **stretch** —
they are where "protocol adherence ≠ HEDIS performance" is most vivid, but they are not
needed for MVP.

**Hero measure = KED.** It is compound (all-of eGFR + any-of uACR variants), time-windowed
(specimen-collection time, not order time), and value-set-driven. It is the best single
vehicle for every point this demo makes.

---

## 3. ⚠️ Licensing & data landmines (the agent MUST obey these)

These are non-obvious and will get the demo killed if violated. State them in the prompt too.

- **NO real PHI. Ever.** 100% synthetic patients. This is a demo asset, not a customer env.
- **NCQA HEDIS value sets and specs are LICENSED.** Do **not** ship NCQA Value Set Directory
  (VSD) or Medication List Directory (MLD) content. For *public* measure logic use the
  **CMS eCQMs** instead: **CMS122** (Diabetes: HbA1c Poor Control) and **CMS165** (Controlling
  High BP). Their value sets live in **NLM VSAC** (free with a UMLS license). Refer to HEDIS
  measures by name/intent (GSD, KED…) for the narrative, but implement value sets from
  VSAC/eCQM public sources. Label clearly: "HEDIS-*aligned*, not NCQA-certified."
- **LOINC** — free from Regenstrief (loinc.org, registration required). Ship a *curated subset*
  (the codes in §2 + a few hundred), not the full release. Include the LOINC license notice.
- **SNOMED CT** — US Edition is free via the **UMLS Metathesaurus / NLM UTS** (UMLS license).
  Ship a *curated subset* (diabetes hierarchy + the disorders/findings/procedures the value
  sets need), not the full 350k-concept release. Include UMLS/SNOMED affiliate-license notice.
- **RxNorm / CVX / ICD-10** — public domain / freely redistributable (NLM / CDC / CMS).
- If any terminology can't be legally bundled, **synthesize a tiny stand-in table with the
  real code values** (the codes themselves are facts, not the licensed artifact) and document
  the substitution. When in doubt, ask Eli before downloading/committing terminology files.
- Put all terminology under a `terminology/` dir with a `LICENSES.md` noting each source + license.

---

## 4. The data model (synthetic, Clarity/Caboodle-shaped)

Medallion in Unity Catalog. Default to catalog/schema the user picks at kickoff
(e.g. `hls_demo.care_protocol`). **Do not invent a catalog — ask.**

**Bronze** — raw Epic-shaped extracts (names mirror real Clarity/Caboodle so the demo
feels authentic; vary by Epic version so label them "typical"):
- `patient` (PAT_ID, BIRTH_DATE, sex, attributed PCP, death date)
- `pat_enc` / `pat_enc_hsp` (encounters; ED/IP/ambulatory setting)
- `problem_list`, `pat_enc_dx` (diagnoses → ICD-10 / SNOMED)
- `order_proc`, `order_results` (labs; carries **local component id**, not LOINC)
- `clarity_component` (the local-component → LOINC crosswalk — *this is the key join*)
- `order_med` (→ RxNorm), `immune` (→ CVX)
- `ip_flwsht_meas` (flowsheet vitals: BP, BMI — **often not LOINC-mapped**; model that gap)
- `coverage` (continuous enrollment / product line — the thing Epic alone can't fully answer)

**Silver** — standardized/conformed: local codes mapped to LOINC/RxNorm/SNOMED/CVX;
timestamps disambiguated (order vs. **specimen-collected** vs. result vs. MAR-admin).
Optionally shape toward OMOP or FHIR, but not required for MVP.

**Gold** — the **adherence event log**: one row per `patient × protocol × step × period`
(schema in research §8.4): `eligible_flag, eligibility_date, due_date, status
(MET/MET_LATE/NOT_MET/PENDING/EXCEPTION/EXCLUDED), evidence_datetime, evidence_source,
evidence_code/code_system, evidence_value, exception_reason, days_to_completion, measure_id,
attributed_pcp, department`. Plus HEDIS-aligned numerator/denominator rollups.

**Seed deliberate data-quality defects** so the paths differ and the story lands:
- A patient whose A1c exists but has a **missing/wrong LOINC mapping** on `clarity_component`
  (→ "care happened but doesn't count"; the Protocol-vs-HEDIS reconciliation quadrant).
- An eye exam that exists **only as a scanned PDF / free text** (→ only the unstructured path finds it).
- A diabetes patient coded as `Type 2 diabetes with diabetic nephropathy` (SNOMED child) to
  prove subsumption (→ only ontology/value-set-expansion paths include them).
- A uACR captured as **separate albumin + creatinine labs 3 days apart** (KED "any-of pair" logic).

**Data generation:** use the `databricks-synthetic-data-gen` / `databricks-data-generation`
skill (Polars + Mimesis / dbldatagen). Target a few thousand patients — big enough to be
believable, small enough to iterate fast.

---

## 5. The five retrieval approaches (outcome #2 — this is the benchmark)

All five answer the **same gold question set**. Genie One is the front door that can route
to several of them; the custom-agent and Ontobricks paths are also callable directly for
head-to-head.

| # | Path | What it is | Databricks building blocks | What it's meant to prove |
|---|------|-----------|----------------------------|--------------------------|
| 1 | **Genie Ontology (rich semantic layer)** | Genie space over Gold + metric views, enriched with UC COMMENTs, synonyms, SQL example instructions, PK/FK constraints | `databricks-data-discovery`, `databricks-genie-agents`, `databricks-metric-views`, UC COMMENT | Structured NL→SQL is *only as good as the semantic layer*. Ablating comments/synonyms/metric-views degrades it measurably. |
| 2 | **Unstructured / Lakebase hybrid search** | Protocol PDFs (ADA, VA/DoD, a synthetic local pathway) parsed, chunked, hybrid (BM25 + vector) search in Lakebase | `databricks-lakebase` (pgvector + tsvector), `ai_parse_document` | Catches what structured data misses (scanned eye exam, protocol narrative), but can't compute a numerator. |
| 3 | **Genie Agents via Genie One (structured components)** | Curated per-domain Genie Agents (e.g. one per measure domain) composed by Genie One | `databricks-genie-agents`, Agent Bricks multi-agent supervisor | Decomposition + curation improves accuracy over one monolithic Genie space. |
| 4 | **Custom agent via MCP** | A custom agent exposing the adherence log + measure-step logic as MCP tools | custom MCP server (host as a Databricks App), `databricks-model-serving` | Deterministic, code-defined retrieval; full control + traceability. |
| 5 | **Ontobricks MCP** | OWL ontology over UC (R2RML to Gold), SNOMED/LOINC as the backbone, published as MCP tools; graph traversal / SPARQL | Ontobricks (databrickslabs) App + its MCP | Graph + subsumption reasoning answers the questions none of the others can. |

**Context-component ablation (outcome #1).** For path 1 especially, make each context
component a **toggle** and measure the delta: (a) table/column COMMENTs on/off, (b) synonyms
on/off, (c) metric views vs. raw tables, (d) curated Genie instructions/SQL-examples on/off,
(e) value-set/ontology expansion on/off. This is the "impact of different context components"
chart and the single most reusable slide out of the whole demo.

---

## 6. Golden threads (outcome #3 — the things we trace)

Pick these specific, concrete anchors and hard-code them as demo exhibits. The app's
lineage tab follows *these exact items*.

1. **Patient `P-001847`, HbA1c = 7.4%** — trace Bronze `order_results` row (local component)
   → `clarity_component` LOINC map (**4548-4**) → Silver conformed observation → Gold event
   (DM-02, status `MET`) → metric view (GSD numerator) → each path's answer to "Is P-001847
   at glycemic goal, and what proves it?"
2. **KED for `P-002233`** — the patient with the split albumin+creatinine labs. Trace how each
   path decides whether KED is met (only logic-aware paths get the "pair within 4 days" right).
3. **Subsumption patient `P-003901`** — coded `Type 2 DM with diabetic nephropathy` (SNOMED
   child). Question: "How many diabetes patients are overdue for KED?" — only ontology /
   value-set-expansion paths include this patient.
4. **The eye-exam-only-as-PDF patient `P-004120`** — only the unstructured path finds the EED evidence.
5. **Measure drift (see §8)** — the eGFR code migration, traced as a before/after.

Give every golden-thread item a stable ID and store the expected answer per path, so the
benchmark and the app agree.

---

## 7. The benchmark harness (how to evaluate)

Build an **MLflow 3 GenAI evaluation** notebook (skill: `databricks-mlflow-evaluation`),
not a bespoke scorer, unless a bespoke MLflow notebook is explicitly wanted (it is — the
user asked for "a custom MLflow notebook"; do both: standard scorers + custom domain scorer).

- **Eval dataset:** ~30–60 gold questions tagged by `measure`, `difficulty`, and
  `requires_ontology`/`requires_unstructured`/`requires_compute` flags, each with a reference
  answer and the expected supporting codes.
- **Scorers:** correctness (LLM judge against reference), faithfulness/groundedness (did it
  cite real evidence), plus a **custom domain scorer** that checks the returned patient set /
  numerator against the Gold table ground truth (exact, not LLM — this is the credible number).
- **Operational metrics:** latency p50/p95, token/$ cost per path (pull from traces).
- **Output:** one MLflow experiment, one results Delta table the app reads, and a summary
  that ranks paths per question-type. Make the ablation runs first-class (tag runs with the
  context-component config).
- Log every path call with **MLflow tracing** so the app's lineage tab can replay a real trace.

---

## 8. The measure-drift demo (outcome #1, the "easy to update" proof)

**Design principle:** measure/value-set definitions are **config, not code**. Store them as
a UC table (or YAML in repo loaded to a table) keyed by `measure_id, step_id, value_set_id`,
with the step shape from research §8.5.

**The scripted drift event:** eGFR code migration — retire the legacy race-based eGFR codes,
adopt **CKD-EPI 2021 `98979-8`**, and (optionally) tighten the KED window. One edit to the
value-set config, then:
1. Re-materialize Gold event log + GSD/KED metric views (a job run).
2. Refresh the Genie semantic layer context (comments/synonyms unaffected; value-set table re-read).
3. Re-sync the Ontobricks graph (R2RML re-materialization).
4. Re-run the benchmark → show the numbers move.

The app's **drift tab** shows a before/after diff: which patients flipped status, how each
path's answer changed, and a timer/stepcount proving "minutes, one config change" vs. the
customer's mental model of "re-engineer the pipeline." This is the competitive-differentiation
money moment — make it a literal button.

---

## 9. Databricks platform facts the agent will get wrong without help

- **Genie One vs Genie Space vs Genie Agent.** Genie One is the unified conversational front
  door / orchestration surface; "Genie Agents" is the current name for what were Genie Spaces
  (curated, per-data NL→SQL agents). Use the `databricks-data-discovery` skill to route data
  Q&A through Genie One, and `databricks-genie-agents` to build/tune the curated agents.
  **Verify current capabilities via the skills — this space moves fast; don't assume from memory.**
- **Agent Bricks** multi-agent supervisor is the supported way to compose multiple agents —
  relevant to path 3 and to wiring Genie One over several Genie Agents + the MCP agents.
- **Metric views** (`databricks-metric-views`) are UC objects defined in YAML (dimensions +
  measures). They are the right home for HEDIS numerators/denominators and they surface to
  Genie. Define GSD/BPD/KED/EED/SPD rates as metric views.
- **The semantic layer in UC** is concretely: table/column **COMMENT**s, **certified** tags,
  **PK/FK constraints**, **synonyms**, business glossary, and metric views. Genie's answer
  quality is a direct function of these. Treat enriching them as a build step, not decoration.
- **Lakebase = managed Postgres** on Databricks. Hybrid search = `pgvector` (semantic) +
  Postgres full-text (`tsvector`/BM25-ish) combined. Use `databricks-lakebase`. (Vector Search
  is the *other* option; the user specifically asked for the Lakebase hybrid path, so use Lakebase
  for path 2. The existing control-tower app uses Vector Search — you may keep that for its
  SOP docs, but the *benchmarked* unstructured path is Lakebase hybrid.)
- **MCP on Databricks:** managed MCP services exist via **Unity Gateway** (`databricks-unity-gateway`);
  Ontobricks publishes its own MCP; a custom MCP server can be hosted as a Databricks App.
  Clarify which hosting model per path.
- **Document parsing:** `ai_parse_document` (AI Functions) for the protocol PDFs → chunks;
  `ai_query` for batch LLM steps. Skill: `databricks-ai-functions`.
- **Packaging:** everything (jobs, pipelines, dashboards, app, metric views) should ship as a
  **DAB** (`databricks-dabs`). The control-tower repo already uses DABs + `variables.yml` /
  `databricks.yml` — extend that, don't reinvent.
- **Auth:** profiles exist in `.databrickscfg` (DEFAULT, E2DEMO, newhls, FEEAST, …).
  **Never auto-select.** Always `--profile <name>` and let Eli choose (`newhls` looks
  HLS-relevant but confirm). Load `databricks-core` first, then the product skill.
- **The two repos:**
  - *Ontobricks* (`databrickslabs/ontobricks`): deploys as a Databricks App; `uv sync --extra lakebase`,
    `.env`, `scripts/start.sh` local; `make deploy` for Apps. Needs SQL Warehouse + Lakebase
    autoscaling DB + UC Volume. Inputs OWL/RDFS, R2RML SQL→RDF mapping, SHACL validation,
    publishes domains as MCP tools. OWL 2 RL reasoning + SWRL. This is path 5 wholesale — don't
    rebuild it, deploy and configure it against our Gold + terminology tables.
  - *Hospital control tower* (`eliswanson-db/hopital_control_tower`): React 18 + Vite + Tailwind
    front end, Flask/gunicorn API, LangGraph agents (Quick/Deep/Autonomous), UC + Vector Search +
    Claude Sonnet 4.5, DAB deploy via `./setup.sh dev`, config in `variables.yml`. **This is the
    app we modify** — add the lineage/benchmark/drift tabs and point the chat at Genie One.

---

## 10. Non-negotiable guardrails (repeat to the agent)

1. **Synthetic data only; no PHI.**
2. **No licensed NCQA/HEDIS or full terminology artifacts committed** — public CMS eCQM / VSAC /
   LOINC-subset / SNOMED-subset only, with `LICENSES.md`. Ask before downloading terminology.
3. **Confirm before any external write** (creating/altering UC objects in a shared catalog,
   deploying apps, posting anywhere). Reading + writing to local repo files is free.
4. **Never auto-select a Databricks profile.**
5. **Route through the Databricks skills**, not hand-rolled REST, unless a skill is missing.
6. Label the whole asset **"HEDIS-aligned demo — not NCQA-certified; synthetic data."**
