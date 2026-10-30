# Critical Analysis & Diff — Three Approaches to the HEDIS Context-Layer Demo

**Date:** 2026-10-29 · **Author:** critical review for Eli
**Inputs compared** (all archived in `sources/`):
- **[A] Claude / this-session** — `sources/DOMAIN_CONTEXT_PACK.md` + `sources/IMPLEMENTATION_ROADMAP.md` + `sources/CODING_AGENT_PROMPT.md`
- **[B] Genie One** — `sources/PROMPT_AND_ROADMAP_FROM_GENIE_ONE.md`
- **[C] Perplexity** — `sources/PROMPT_AND_ROADMAP_FROM_PERPLEXITY.md`

> **Scope of this analysis:** product/design/engineering quality only. Delivery scheduling and
> work-life-balance are deliberately out of scope — they are project-management concerns, not
> measures of whether the design is good.
>
> **Bottom line up front.** On pure design merit the ranking is **C > B > A**. **[C] Perplexity** is
> the strongest engineering design (correctness model, provenance, architecture soundness); **[B] Genie
> One** has the best *data strategy* (Synthea) and the most accurate *Databricks product-state* detail,
> and is the most demo-ready; **[A] mine** is the weakest on design depth — its genuine edges are
> narrower (modular packaging, readability, and an MVP-sequencing instinct), not deeper design. None is
> best alone: the right move is a **synthesis** (§6) — Synthea data engine (B) + deterministic
> measure-engine-vs-context separation and provenance model (C) + the A1–A6 benchmark arms with B's
> concreteness hardened by C's isolation caveats. **Two things to verify before building:** **B says the
> Control Tower backend is "FastAPI"; the repo is Flask** (minor, but it misdirects an agent), and **B's
> insider product-state claims (preview dates, the "4/8 vs 8/8" RSA anecdote) are unverifiable here and
> some may be internal-only** — treat as "verify in-workspace," don't present as fact.

---

## 1. One-line characterization

| | Optimizes for | Reads like | Biggest single strength | Biggest single weakness |
|---|---|---|---|---|
| **A — Claude** | Being actionable quickly | A build plan | Modular, readable, correctly externalizes "what the agent won't know" | Shallowest design — light on benchmark rigor, correctness epistemics, and product-state specifics; **missed Synthea** |
| **B — Genie One** | Product-state realism + demo-readiness | A Databricks insider's run-book | Synthea data engine; concrete arms/tracers; preview-state knowledge; agent-session discipline (AGENTS.md, phase gates) | Insider claims unverifiable/possibly stale; a factual slip (FastAPI); thin on correctness epistemics |
| **C — Perplexity** | Being *right* and not overclaiming | A principal engineer's design review | Measure-engine ≠ context; UNKNOWN≠NOT_MET; evidence≠acceptance; anti-circular arch; provenance model; honest observability | Very long (60 KB) — risk the agent/human under-absorbs it; weakest on crisp "showable" demo beats |

---

## 2. Scorecard (1–5; design/engineering merit only)

| Dimension | A | B | C | Notes |
|---|:--:|:--:|:--:|---|
| Clinical/HEDIS correctness rigor | 3 | 3 | **5** | C alone handles UNKNOWN-vs-NOT_MET, enrollment denominators, order≠result, evidence≠acceptance as *first-class* |
| Databricks product-state accuracy | 3 | **5** | 4 | B names GA/preview states, MCP tool lists, index names; C cites docs with URLs; A defers to skills |
| Data strategy | 3 | **5** | 3 | B's Synthea→"Epic-ize" is the best idea in any of the three; A & C hand-roll synthetic data |
| Benchmark / eval design | 2 | 4 | **5** | B concrete (A1–A6, repeats, variance); C adds isolation caveats, leave-one-out, question-type scoring, "not observable ≠ zero" |
| Golden-thread / tracer design | 3 | 4 | **5** | B's "expected winner per tracer" is demo-gold; C adds epistemic design + a permissions variant |
| Architecture soundness | 3 | 3 | **5** | C uniquely flags circular Genie↔agent recursion, tool-vs-agent-via-MCP, synced-table auth boundary |
| Licensing / compliance caution | 4 | 4 | **5** | All good; C most lawyerly (and correct that "demo" ≠ license relief) |
| Agent-prompt engineering | 3 | **5** | 4 | B: master + per-phase sessions + AGENTS.md + RUNBOOK + gates. C: discovery-first + doctor/preflight + vertical-slice. A: short/restate-and-pause |
| Usability (can a human act on it?) | **5** | 4 | 3 | A modular & short; B dense but navigable; C exhausting in one pass |
| Repo/app-specific findings | 2 | 3 | **5** | C caught the Control-Tower **date-shifting/startup-mutation** behavior that breaks MY reproducibility — nobody else did |
| **Design-merit average** | **3.1** | **4.0** | **4.5** | Ranking **C > B > A** |

*Delivery note (not scored — out of design scope):* A is the only one that sequences an MVP / critical
path and flags what to cut first. That is a project-planning attribute, not a design-quality one, so it
does not factor into the ranking above. It's still useful when you get to execution planning.

---

## 3. Deep pros / cons

### A — Claude (this session)
**Pros**
- **Usable immediately** — modular (context pack separate from the prompt → better token ergonomics for
  the agent and a stable reference it re-reads, vs. C's 60 KB single prompt), readable, decision-oriented.
- Correctly externalizes "stuff the agent won't know" and forces a **restate-and-pause** before coding.
- Clean MVP/critical-path sequencing *if/when* you want a delivery order (a planning aid, not a design virtue).

**Cons (the honest list — this is the weakest design of the three)**
- **Missed Synthea** — hand-rolling Epic-shaped data with SNOMED/LOINC/RxNorm/CVX is strictly worse than
  generating pre-coded patients and "Epic-izing" them. Biggest miss.
- **Benchmark is underspecified** — no explicit repeats/variance for nondeterministic Genie, no leave-one-out,
  no question-type scoring, no "native ontology can't be cleanly toggled" caveat.
- **No epistemic model** — doesn't distinguish UNKNOWN from NOT_MET, evidence from acceptance, or
  measure-logic from context. In HEDIS that's not pedantry; enrollment gaps and order≠result are where real
  implementations break.
- **Softest on "don't fake preview APIs"** — says "verify capabilities via skills" but lacks B/C's hard rule:
  unavailable preview API → write a RUNBOOK manual step, don't hallucinate a payload.
- Didn't catch the Control-Tower date-shift behavior or the circular-architecture risk.

### B — Genie One
**Pros**
- **Synthea as the clinical engine** — the single best design decision across all three. Pre-coded
  SNOMED/LOINC/RxNorm/CVX, deterministic seed, then add local IDs + partial LOINC mapping + flowsheets.
- **Richest Databricks product-state detail**: Genie One MCP GA timing, Genie Agent MCP is read-only/no
  history (use Conversation API), Lakebase `lakebase_ann`/`lakebase_bm25` (build BM25 *after* load),
  Ontobricks two-App deploy + `make bootstrap-lakebase` + the MCP tool list, Domains Terraform resource,
  Pages bulk-import gap (drops page-to-page links). This saves the agent days.
- **Demo-ready tracers** — T1–T6 each with a planted fact *and the expected winning approach*. Basically a storyboard.
- **Best agent-operations discipline** — one master prompt, then "Execute Phase N per AGENTS.md" in gated
  sessions; RUNBOOK for manual steps; per-arm service principals; idempotent `CREATE OR REPLACE`.
- The **SNOMED-closure insight** ("relationship meaning moved from OWL into views+metadata; Genie reached
  8/8") is the sharpest articulation of *why the semantic layer matters* in any of the three.

**Cons**
- **Unverifiable / possibly sensitive insider claims.** "Internal tickets say on by default since June /
  available since Aug 13," "one field team found it switched off," the **"RSA 4/8 vs 8/8" anecdote** — high
  value *if true*, but unverifiable here, some may be **internal-only** (don't belong in a potentially
  shareable artifact), and preview dates go stale fast. Treat as "verify in the target workspace"; strip
  internal-ticket specifics from anything customer-facing.
- **A factual slip:** the architecture table calls the Control Tower app **"FastAPI + React"**; the repo is
  **Flask + gunicorn + React/Vite** (confirmed by README; C agrees). The kind of thing that sends an agent
  down the wrong path.
- **Thin on correctness epistemics** — inherits HEDIS rules fairly literally; doesn't foreground UNKNOWN,
  enrollment-denominator honesty, or evidence≠acceptance the way C does.

### C — Perplexity
**Pros**
- **The correctness conscience.** Separates the three "semantic layers" (terminology vs. analytical/business
  vs. formal ontology) — a distinction the original question conflated, and the key to telling the story
  honestly. Separates **measure engine from context** ("a Page can explain a measure; it must not be the only
  place that implements it"). Distinguishes **UNKNOWN / NOT_ELIGIBLE / PENDING_REVIEW** from NOT_MET, and
  **evidence found → extracted → reviewed → accepted → recomputed** as four distinct events.
- **Architecture catches nobody else made:** anti-circular recursion guard (Genie One → custom agent → Genie
  One); **tool-through-MCP ≠ agent-through-MCP** (different orchestration budgets — don't benchmark as equal);
  synced-table **auth boundary** (a Lakebase copy may not reproduce source authorization); and the
  **Control-Tower date-shifting behavior** that would silently move results across a measurement-year
  boundary and destroy reproducibility. That last one is a genuinely excellent, specific find.
- **Honest observability** — classify every trace detail as OBSERVED / DECLARED / UNAVAILABLE; "do not
  fabricate internal Genie retrieval spans"; "record not-observable, not zero." Exactly right, and what keeps
  the benchmark credible to a skeptical audience.
- **Best eval epistemics** — question-type scoring (a doc-retriever *should* refuse a population count),
  leave-one-out vs. incremental ladder, "a prompt saying 'use only this approach' is not proof native context
  was excluded."
- Strong **context-package** concept with a release manifest (versioned terminology/value-set/mapping/metric/
  ontology lifecycles kept separate). Correct and reusable.
- Citations carry **URLs** (checkable), incl. the LOINC Ontology (the "LOINC component" instinct) with a
  concrete version.

**Cons**
- **Length is a real cost.** 60 KB, much of it caveats. Risk: the coding agent skims and loses signal, or the
  human never finishes it. The discipline is excellent but needs *distilling* into a checklist + shorter prompt.
- **Weakest on "showable."** Heavy on what not to claim, lighter on the crisp demo beats that make an exec lean
  in (its demo sequence is good but buried at the end).
- Occasionally **over-engineers for a demo** (full provenance-edge tables, multi-timestamp model, acceptance-
  policy entities). All *correct*; some is beyond a first demo — apply C's rigor selectively.
- A few cited facts (LOINC Ontology v2.83 "released Oct 21 2026," CMS951/CMS131 value sets) still need
  in-workspace/VSAC verification; citations reduce but don't remove the risk.

---

## 4. Factual-accuracy & risk audit (verify before building)

> The Control Tower app is **optional** (leverage-or-rebuild — see §5a), so items #1 and #4 are
> "if you reuse it" caveats, not hard blockers.

| # | Claim | Source | Verdict | Action |
|---|---|---|---|---|
| 1 | Control Tower app backend is **FastAPI** | B (arch table) | **Likely wrong** — repo is Flask/gunicorn + React/Vite (README; C agrees) | If reusing: read the repo first, don't scaffold FastAPI |
| 2 | Genie Ontology "on by default since June / available Aug 13"; "field team found it off" | B | **Unverifiable here; possibly internal-only** | Verify in target workspace; strip internal-ticket phrasing from shareable artifacts |
| 3 | "RSA comparison: Genie 4/8 → 8/8 after closure view + metadata" | B | **Unverifiable; likely internal** | Great *illustration*; don't present as a cited benchmark externally |
| 4 | Control Tower **shifts dates / mutates on startup** | C | **Specific, plausible, high-impact** | If reusing: disable date-shift for quality data (breaks MY reproducibility). A reason net-new may be cleaner |
| 5 | Ontobricks exposes a generic `query_sparql`/SPARQL MCP tool | (implied risk) | **C correctly warns against assuming it** | Discover actual deployed MCP tools; B's tool list is a hypothesis, not gospel |
| 6 | LOINC Ontology v2.83, SNOMED US Edition via UMLS, VSAC proxies (CMS122/165/131/951) | B & C | **Plausible; cite-backed in C** | Verify current releases + licenses at build time; load from UC Volume, never commit |
| 7 | Ontobricks pinned version (B: v0.8.1; C: commit `97b27c7…`) | B & C | **Both reasonable anchors; they differ** | Pick one tag, record it, don't assume it matches the workspace |
| 8 | Genie Agents (standalone) don't use the ontology; Genie One does | B | **Plausible and important if true** — it defines what the benchmark arms measure | Re-confirm before presenting; it's the crux of A1 vs A2 |

**Cross-cutting risk all three share:** the demo leans on **preview/Labs features** (Genie Ontology, Pages,
Domains APIs, Lakebase Search, Ontobricks). B and C both handle this correctly (verify → RUNBOOK manual step →
keep content as Git markdown/YAML so it's portable). A is too soft here — adopt B/C's rule.

---

## 5. Recommended synthesis (take this, not any single doc)

### 5a. The app: leverage or rebuild — decide deliberately
The Control Tower is **not load-bearing**. Its reusable value is its **DAB structure, dashboard, and
LangGraph agent/tool patterns**. Against that, it carries **date-shifting/startup mutation** (breaks
measurement-year reproducibility) and **string/regex-based SQL "security"** (C) that you'd have to rip out.
**Recommendation:** reuse it only if its scaffolding clearly saves time; otherwise a **net-new thin app**
(FastAPI or Flask + React, OBO auth, Lakebase app state) is likely cleaner and avoids inheriting its
baggage. Either way the tabs are the same (§5b).

### 5b. The merged design
**Data (from B):** Synthea with a fixed seed → "Epic-ize" into Clarity-shaped tables. Pre-coded terminology
is a major head start and makes ground-truth-by-construction honest.

**Clinical model & correctness (from C):** deterministic **measure engine** separate from context; preserve
multiple timestamps; **UNKNOWN / NOT_ELIGIBLE / PENDING_REVIEW ≠ NOT_MET**; **evidence found ≠ accepted**;
record-level **provenance tables** (trimmed to what the demo needs); keep protocol-step status separate from
HEDIS status. Adopt the **anti-circular / tool-vs-agent-via-MCP** distinctions and the **synced-table auth** check.

**Context packaging (from C, lightly):** a versioned **context package** with a release manifest
(terminology/value-set/mapping/metric/ontology on separate lifecycles). Don't gold-plate the provenance graph.

**Semantic layer & Genie (A+B+C):** UC comments/tags/PK-FK + metric views (YAML in Git) + Domains + Pages +
certification; 3 curated Genie Agents; Genie One as front door. Use B's concrete product mechanics (bulk-import
Pages, DAB JSON for agents).

**Benchmark (B's arms, C's discipline):** arms **A1 Genie One · A2 Genie Agent · A3 ablation ladder L0–L5 ·
A4 Lakebase RAG (BM25/vector/hybrid) · A5 Ontobricks · A6 supervisor**, PLUS C's hardening: deterministic SQL
**oracle** for ground truth, **question-type scoring** (reward correct refusals), **leave-one-out**, 3–5 repeats
with **variance**, per-arm service principals, and **OBSERVED/DECLARED/UNAVAILABLE** honesty. State plainly that
native ontology isn't cleanly toggleable.

**Tracers (B's demo-readiness + C's epistemics):** 6 threads, each with a planted fact **and an expected winner**
(B), designed around the honest distinctions (C), **+ one permissions variant** (C).

**Agent operations (B+C):** master prompt once, then **gated per-phase sessions** with **AGENTS.md** +
**RUNBOOK** (B); **discovery-first** with a read-only **doctor/preflight** capability matrix and
**vertical-slice-first** (C). Hard rule: unavailable preview API → RUNBOOK manual step, never a hallucinated payload.

**Front door & labeling (unanimous):** Genie One front door; every surface labeled
**"Synthetic · HEDIS-aligned (eCQM-proxied value sets) · Not NCQA-certified · Not for clinical use."**

---

## 6. Coverage diff — who has what

| Capability / idea | A | B | C |
|---|:--:|:--:|:--:|
| Synthea data engine | – | ✅ | – |
| Deterministic measure engine ≠ context separation | partial | partial | ✅ |
| UNKNOWN ≠ NOT_MET / enrollment honesty | – | – | ✅ |
| Evidence found ≠ reviewed ≠ accepted | partial | partial | ✅ |
| Record-level provenance tables | – | partial (tracer_registry) | ✅ |
| Anti-circular arch / tool-vs-agent-via-MCP | – | – | ✅ |
| Control-Tower date-shift behavior caught | – | – | ✅ |
| Product-state specifics (MCP GA, index names, Pages gaps) | – | ✅ | partial |
| Benchmark arms A1–A6 spelled out | partial | ✅ | ✅ |
| Benchmark isolation caveats / leave-one-out / refusal scoring | – | partial | ✅ |
| Repeats + variance for nondeterministic Genie | – | ✅ | ✅ |
| Tracers with "expected winning approach" | partial | ✅ | partial |
| Permissions/security tracer variant | – | – | ✅ |
| AGENTS.md + gated per-phase sessions | – | ✅ | partial |
| doctor/preflight capability matrix | – | – | ✅ |
| Vertical-slice-first execution | partial | – | ✅ |
| Modular context pack (token ergonomics) | ✅ | – | – |
| SNOMED-closure "meaning moved into views" insight | – | ✅ | partial |
| Context-package release manifest | – | partial | ✅ |
| Citations with checkable URLs | – | – | ✅ |

---

## 7. Decision points for Eli

1. **Adopt the synthesis (§5), not any single doc.** The merged build kit would be: a distilled master prompt
   (B's structure + C's non-negotiables), a trimmed context pack (B's product facts + C's epistemics), and one
   roadmap built on B's phases.
2. **Decide app reuse vs. net-new (§5a)** — net-new is plausibly cleaner given the Control Tower's date-shift
   and string-based-SQL baggage; reuse only if its scaffolding clearly pays for itself.
3. **Verify the §4 items before building** — especially the preview-feature availability and (if reusing) the
   date-shift behavior. A short `databricks:doctor` + repo read settles most.
4. **Strip B's internal-ticket specifics** from anything that might go customer-facing; keep them as
   "verify in-workspace" notes only.
