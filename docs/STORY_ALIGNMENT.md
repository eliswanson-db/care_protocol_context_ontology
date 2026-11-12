# Story alignment — "A Monday with Genie" (diabetes storyboard)

The north-star narrative we build toward (Databricks ideation storyboard, Oct 2026). We align **conceptually**,
not slide-for-slide: our demo deliberately goes **beyond** (benchmarks, formal graph) and is a reusable
substrate, not a customer-specific deck. Check builds against this doc.

## The story in one breath
Value-based care: quality *is* revenue (Medicare Advantage Star Ratings). Diabetes protocols **drift quietly**;
today you find out after the measurement year closes (BI = 6–10 week handoffs, nothing feeds back). "A Monday
with Genie": a scheduled **Weekly Protocol Watch** over governed **Metric Views + the protocol PDF** *notices a
protocol STEP slipping*, Genie explains the **root cause** (a PCP handoff dropped the follow-up order set,
citing doc+data), **sizes** it on certified Star measures (two 3× diabetes measures), drafts a **ranked fix**,
**widens the watch**, supports a **P&T guideline-diff** decision, publishes a **row-filtered Page**, and next
Monday **checks the fix**. Foundation = *"one layer that knows your organization"*: Genie Ontology (**Learned** members/
encounters/orders + **Modeled** protocol→step→expected-event + certified Star Metric Views), a **shared Member**
joining care-delivery ↔ health-plan, surfaced via Genie One / scheduled tasks / Agents / Pages, governed by
Unity Catalog, evaluated with MLflow.

The story's 5 diabetes Star measures: **Blood Sugar Controlled** (GSD, 3×), **Medication Adherence for Diabetes
Meds** (3×), **Kidney Health Evaluation** (KED, 1×), **Statin Use** (SPD, 1×), **Eye Exam** (EED, 1×).

## Scorecard

### Strongly aligned — our substrate IS the story's foundation
- Domain + measures: diabetes; GSD / KED / SPD / EED built and verified at 25k.
- Protocol PDF governed in a **UC Volume**, read alongside the data (`documents` volume).
- **Certified Metric Views** as the single set of definitions.
- The story's **"key move" — protocol spine ↔ quality spine linked through the shared Member** — is exactly our
  knowledge-graph / `protocol_edges` / ontology design. Our strongest alignment.
- Pages + UC governance + lineage + "cite the work"; MLflow agent eval; synthetic data (Synthea, 25k).

### Beyond the story (our technical deepening — valuable, keep as a labeled "appendix")
- **Capability-map benchmark** (RAG vs metric view vs closure vs graph). The story *assumes* the ontology works;
  we prove *when/why each layer earns its place*. Don't let it become the demo's spine.
- **Formal OWL / Ontobricks graph.** The story's "ontology" is the Databricks-native Learned+Modeled layer
  (metric views + protocol model + shared Member), not necessarily a formal graph.

### Gaps vs the narrative spine (the plot mechanism we're missing)
| # | Gap | Why it matters | Status |
|---|-----|----------------|--------|
| 1 | **Protocol-STEP adherence** (temporal: expected event within a window after a trigger) | The story's *hero object* — "which STEP slipped," not just the Star rate | ✅ **DONE** — `gold_protocol_adherence` (now carries `clinic_id`/`panel_id`) + `protocol_adherence_metrics` (Clinic/Panel dims). Overall Step-3 adherence **57%**; the care-behavior model (ADR-0012) drops **CLINIC-08** mid-Q3 (own prior **78% → 47%**). Masked in the annual ranking, visible temporally — the real hero signal. |
| 2 | **Medication Adherence / refill gaps (PDC)** | A 3× Star measure + the pharmacist-outreach beat | ✅ **DONE** — `gold_adherence_mad` + `mad_compliance_metrics`. The care-behavior model (ADR-0012) models fills per 30-day cycle → a **continuous PDC** (p10 0.49 / p50 0.74 / p90 0.90), **47.8% adherent** (was a degenerate 100%). |
| 6 | **Realistic care-process variation** (was "planted tracers") | Make protocol-drift / MAD / poor-control show variation without faking it | ✅ **DONE** — replaced point-injection "tracers" with a **seeded generative care-behavior model** (ADR-0012): emergent, continuous, confounded variation from per-patient Bernoulli draws. Lights up protocol drift + MAD + **poor control (24%)** at once; nothing wired to an answer. |
| 3 | **Proactive scheduled drift-watch + alerting** ("nobody asked; Genie noticed") | The story's hook; operational process-monitoring | ✅ **DONE (watch)** — `protocol_watch` scans **CLINIC × trailing-3-month vs each clinic's OWN prior baseline** (censoring-aware, small-N gated) → fires **HIGH on CLINIC-08 2025-09** (78%→47%, Δ0.31); appends `protocol_watch_findings`. + **Genie One scheduled task** (manual, runbook) reads that table. Schedule **PAUSED**; remaining: a live notification destination (external write — await Eli). |
| 4 | **Plan-side + panel/PCP data** (panels, PCP attribution, panel transitions, claims/enrollment) | Enables the root-cause beat ("which panel's PCP changed") and the care↔plan crossing | 🟡 **PARTIAL** — the care-behavior model adds `panel_id`/`pcp_id`/`clinic_id` + a `panel_pcp_transition` (a clinical-side down-payment on the root-cause beat). Full plan-side claims/enrollment still TODO (Synthea is clinical only). |
| 5 | Per-reader **row-filtered Pages**; **guideline-diff + scenario** decision support; **risk adjustment**; **action→feedback** loop | Governance-in-Pages, P&T decision support, fair comparisons, closing the loop | TODO |

### Note on BPD
We built **BPD** (blood-pressure control); it is **not** one of the story's diabetes-5. Keep it (valid,
adjacent) but the canonical set to foreground is GSD / Medication Adherence / KED / SPD / EED.

## Bottom line
We have the **stage and cast** (domain, measures, protocol PDF, certified metric views, shared-Member
ontology, Pages, governance, MLflow). We're adding the **plot mechanism** — step-level protocol adherence +
medication adherence now; proactive drift-watch and plan-side/panel data next.
