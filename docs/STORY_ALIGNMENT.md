# Story alignment — "A Monday with Genie" (KP diabetes storyboard)

The north-star narrative we build toward (Databricks ideation storyboard, Oct 2026). We align **conceptually**,
not slide-for-slide: our demo deliberately goes **beyond** (benchmarks, formal graph) and is a reusable
substrate, not a KP-specific deck. Check builds against this doc.

## The story in one breath
Value-based care: quality *is* revenue (Medicare Advantage Star Ratings). Diabetes protocols **drift quietly**;
today you find out after the measurement year closes (BI = 6–10 week handoffs, nothing feeds back). "A Monday
with Genie": a scheduled **Weekly Protocol Watch** over governed **Metric Views + the protocol PDF** *notices a
protocol STEP slipping*, Genie explains the **root cause** (a PCP handoff dropped the follow-up order set,
citing doc+data), **sizes** it on certified Star measures (two 3× diabetes measures), drafts a **ranked fix**,
**widens the watch**, supports a **P&T guideline-diff** decision, publishes a **row-filtered Page**, and next
Monday **checks the fix**. Foundation = *"one layer that knows KP"*: Genie Ontology (**Learned** members/
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
| 1 | **Protocol-STEP adherence** (temporal: expected event within a window after a trigger) | The story's *hero object* — "which STEP slipped," not just the Star rate | ✅ **DONE** — `gold_protocol_adherence` + `protocol_adherence_metrics`. Step 3 adherence = **12.2%** (392 A1c≥7 triggers / 48 followed in 90d). Real drift signal. (Trigger =7 not 9: Synthea is well-controlled; flip `A1C_TRIGGER` on real data.) |
| 2 | **Medication Adherence / refill gaps (PDC)** | A 3× Star measure + the pharmacist-outreach beat | ⚠️ **built but degenerate** — `gold_adherence_mad` + `mad_compliance_metrics`. PDC saturates at 1.0 → 100% adherent, because **Synthea prescribes metformin continuously (no modeled non-adherence)**. Logic is correct; needs **planted refill-gap tracers** (gap #6) to show variation. |
| 6 | **Planted tracers** (poor-control A1c, refill gaps, data-mapping gaps) | Make MAD/poor-control show variation; the story's "1 in 5 has a refill gap" | TODO — Synthea is "too healthy/adherent"; inject non-adherence + poor control into a subset (ties to the original T1–T6 tracer idea) |
| 3 | **Proactive scheduled drift-watch + alerting** ("nobody asked; Genie noticed") | The story's hook; our drift demo is value-set vintage, not operational monitoring | TODO |
| 4 | **Plan-side + panel/PCP data** (panels, PCP attribution, panel transitions, claims/enrollment) | Enables the root-cause beat ("9 panels whose PCP changed") and the care↔plan crossing | TODO (Synthea gives clinical only) |
| 5 | Per-reader **row-filtered Pages**; **guideline-diff + scenario** decision support; **risk adjustment**; **action→feedback** loop | Governance-in-Pages, P&T decision support, fair comparisons, closing the loop | TODO |

### Note on BPD
We built **BPD** (blood-pressure control); it is **not** one of the story's diabetes-5. Keep it (valid,
adjacent) but the canonical set to foreground is GSD / Medication Adherence / KED / SPD / EED.

## Bottom line
We have the **stage and cast** (domain, measures, protocol PDF, certified metric views, shared-Member
ontology, Pages, governance, MLflow). We're adding the **plot mechanism** — step-level protocol adherence +
medication adherence now; proactive drift-watch and plan-side/panel data next.
