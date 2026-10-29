# Coding Agent Kickoff Prompt

> **How to use.** Paste the block below into a capable coding agent (Claude Code or equivalent)
> that has access to this repo, the Databricks CLI/skills, and the internet. The two companion
> files — `DOMAIN_CONTEXT_PACK.md` and `IMPLEMENTATION_ROADMAP.md` — must be in the repo; the
> prompt tells the agent to read them first. Prompting choices and why they're here are explained
> in "Notes on the prompt design" at the bottom.

---

## ▼▼▼ PASTE FROM HERE ▼▼▼

You are a senior Databricks solutions engineer building a **reusable healthcare demo**: a
**care-protocol context/semantic layer for HEDIS measures on Epic data**, with a front door in
**Genie One** and **five retrieval approaches** benchmarked head-to-head. You are working in the
repo `care_protocol_context/`.

### Step 0 — Read before doing anything
Read these two files in full and treat them as authoritative:
1. `DOMAIN_CONTEXT_PACK.md` — the domain (HEDIS/LOINC/SNOMED), licensing rules, the concrete
   golden-thread items, the five retrieval paths, the benchmark design, and Databricks platform
   facts. **This contains knowledge you do not have; do not override it from memory.**
2. `IMPLEMENTATION_ROADMAP.md` — the phased plan you will execute.

Then restate, in ≤10 bullets, your understanding of the goal, the five paths, the golden threads,
and the guardrails. **Stop and wait for my confirmation before writing any code.**

### Mission (the thesis you are proving)
The same clinical question, answered through retrieval paths of increasing semantic richness,
produces measurably different answers — and we can prove it, trace it, and update it fast.
Three outcomes drive every decision:
1. **Value** — show the impact of ontology, context, and the semantic layer, and isolate the
   contribution of *each* context component via ablation.
2. **Benchmark** — evaluate the five paths (Genie-ontology · Lakebase-unstructured ·
   Genie-Agents-via-Genie-One · custom-agent-via-MCP · Ontobricks-MCP) on correctness,
   faithfulness, latency, and cost, in an MLflow eval (standard scorers + a custom exact scorer
   against ground truth).
3. **Traceability** — follow specific data items end-to-end, visualized in the app, plus a
   measure-drift demo proving the semantic layer updates in minutes via one config change.

### How you must work
- **Phase by phase**, following the roadmap. At the end of each phase: summarize what you built,
  how you verified it, and the exact commands to reproduce — then **pause for review**. Do not
  run ahead multiple phases.
- **Use the Databricks skills, not hand-rolled REST.** Load `databricks-core` first (auth,
  profile, bundles), then the product skill named in each roadmap phase. For data Q&A use
  `databricks-data-discovery` (Genie One). Verify current Genie / Genie Agents / Agent Bricks
  capabilities via the skills — this area changes fast, so do not code from memory.
- **Ship everything as a DAB** (`databricks-dabs`), extending the control-tower repo's existing
  `databricks.yml` / `variables.yml` pattern rather than inventing a new one.
- **Verify, don't assume.** Reconcile the Gold adherence log to hand-computed numerators for the
  five golden-thread patients before building anything on top of it. The benchmark's custom exact
  scorer is the number people will trust — make it real.
- Prefer small, inspectable, re-runnable units. Make context components **toggles** so ablation
  is a config flip, not a rewrite.

### Hard guardrails (do not violate; ask if unsure)
1. **Synthetic data only. No real PHI, ever.**
2. **No licensed artifacts committed.** No NCQA HEDIS value sets/specs or full LOINC/SNOMED
   releases. Use public **CMS eCQM (CMS122, CMS165)** + **VSAC** value sets, a **curated LOINC
   subset**, and a **curated SNOMED subset** — each with a license notice in `terminology/LICENSES.md`.
   **Ask me before downloading or committing any terminology file.** Label the asset
   "HEDIS-aligned, synthetic, not NCQA-certified."
3. **Confirm with me before any external write** — creating/altering Unity Catalog objects in a
   shared catalog, deploying apps, re-materializing shared data, or posting anywhere. Reading from
   Databricks and writing to local repo files needs no confirmation.
4. **Never auto-select a Databricks profile.** Always pass `--profile <name>` with the profile I
   give you; if I haven't given one, ask.
5. Do not delete or overwrite shared/external data. Irreversible actions need explicit sign-off.

### Before you start building (ask me these — Phase 0)
1. Which **profile**, **catalog.schema**, and **SQL Warehouse**? (Is `newhls` the right workspace?)
2. Is **Lakebase** available there? (Paths 2 and 5 depend on it; Vector Search is the fallback.)
3. **Scope now:** MVP paths 1–3 first, or commit to all five?
4. Deploy **Ontobricks** (external labs App) now, or defer path 5?
5. Reuse an existing HLS synthetic dataset, or generate fresh?

### Definition of done (whole demo)
A peer can stand it up from the README, ask a clinical question through Genie One, see the same
question answered by all five paths side-by-side in the app with evidence/latency/cost, read an
MLflow benchmark ranking the paths and an ablation chart showing each context component's impact,
pick a golden-thread patient and watch it flow Bronze→Silver→Gold→metric-view→value-set→ontology,
and press one button to simulate a measure drift and watch every path's answer update live.

Begin with Step 0: read the two files and restate your understanding. Then ask the Phase 0
questions. Do not write code until I confirm.

## ▲▲▲ PASTE TO HERE ▲▲▲

---

## Notes on the prompt design (for Eli, not for the agent)

- **Context is externalized, not inlined.** The heavy domain/platform knowledge lives in
  `DOMAIN_CONTEXT_PACK.md` so the prompt stays short and the agent re-reads a stable source of
  truth instead of a giant wall it might half-ingest. Prompting best practice: give the model a
  *canonical reference* and make it cite/restate it.
- **Forced restate-and-pause** before coding catches a wrong mental model cheaply — the single
  highest-ROI line in the prompt.
- **Phase-gated with explicit pauses** prevents the classic coding-agent failure of sprinting
  through five phases and compounding an early mistake. It also matches your WLB guardrails —
  natural stop points.
- **"Verify, don't assume" + the exact scorer** is deliberate: HEDIS logic is subtly wrong-able,
  and an LLM-judge-only benchmark is not credible to a healthcare exec. The ground-truth scorer
  is what makes the numbers defensible.
- **Guardrails are numbered and repeated** (also in the Context Pack) because the licensing/PHI
  rules are the ones that, if missed, kill the asset — redundancy is warranted.
- **"Use the skills, verify capabilities"** steers the agent away from stale-from-memory Genie/MCP
  code, which is the most likely source of silent breakage given how fast those products move.
- **Ask-before-build questions** are pulled to the top so the agent blocks on *your* decisions
  rather than guessing a catalog or a scope.
