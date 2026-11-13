# Architecture Decision Records (ADRs)

Short, dated records of decisions that shape the build. Newest first. These **supersede** any conflicting
statement in the source plans under `docs/sources/`.

---

## ADR-0025 — Knowledge parity: every retrieval approach gets the same facts, so the benchmark measures mechanism
**Date:** 2026-11-13 · **Status:** accepted · **Applies to:** life sciences now; HEDIS gaps to be audited
The benchmark tests *how* each approach retrieves, not whether we fed it different content. **Decision:** one
canonical study knowledge base (KB) in `clinical_study_standards`:
- `kb_concept`: id, scheme, label, definition, release;
- `kb_edge`: subject, predicate, object, source artifact, authority, release. **Direct assertions only.**
- The approved rule registry, also emitted as `kb_edge` rows with `cpl:` predicates.

Each approach gets the KB rendered in its native form:
- **graph (A5):** R2RML over `kb_concept`/`kb_edge` plus the data tables. Direct triples; traversal is the mechanism.
- **closure:** closures derived from `kb_edge` is-a (and typed or composed variants). Materialization is the mechanism.
- **RAG (A4):** a generated **knowledge reference corpus** (one entry per KB concept stating its direct facts in
  sentences, each tagged with the `kb_edge` ids it expresses) alongside the protocol/SAP/amendment documents.
  No transitive facts are pre-written.
- **Genie One / Genie Ontology:** the same KB tables with UC comments, Pages for class definitions and rules, and
  metric views.
- **Documents ↔ registry:** every approved rule's parameters appear both in its document section and in the registry
  that the graph and Genie read.

**Parity is tested.** `tests/test_ls_knowledge_parity.py` asserts that every `kb_edge` is expressed in the RAG reference
corpus and covered by an R2RML mapping. Exceptions go in an explicit allowlist with a reason.

**Reasonable-extent exception:** Pages carry class definitions and rules, not one page per concept (≈thousands). Genie
reaches per-concept facts through the governed KB tables instead.

**Benchmark rule:** a question that only one approach can answer because of extra content is a
**context-availability experiment**. It is labeled and reported separately from mechanism results (prompt §15).

---

## ADR-0024 — Life-sciences data: dbldatagen raw EDC exports → Lakeflow pipeline → SDTM-shaped silver → ADaM-shaped gold
**Date:** 2026-11-12 · **Status:** accepted
Same spine as HEDIS (raw landing → bronze → silver → gold → semantic). A seeded **dbldatagen** generator on serverless
writes EDC-style exports (participants, visits, vitals, exposure, medical history, concomitant meds) to a landing volume.
The 20 named edge-case participants are injected deterministically on top. Scale: Study A ≈4,000 and Study B ≈2,500
participants, ≈10 scheduled visits plus unscheduled ones. A Lakeflow pipeline builds bronze (immutable) → silver
SDTM-shaped DM/VS/EX/MH/CM/SV (validated against COSMoS DSS value lists) → gold ADaM-shaped endpoint tables. The
versioned endpoint engine reads the **approved** rule registry. Candidate assertions extracted from documents never
execute. Hand-authored expected outcomes (not engine output) are the independent oracle. Synthetic protocol/SAP/
amendment PDFs follow the HEDIS `docs/care_protocol` corpus → html → pdf pattern and feed A4 RAG, Pages, and rule
extraction. Labels: "SDTM-shaped" / "ADaM-shaped". Not submission-ready, not validated.

---

## ADR-0023 — Two demos, one app and one catalog: schema isolation, demo_id scoping, ECT only
**Date:** 2026-11-12 · **Status:** accepted
The life-sciences lab gets its own schemas in `eli_test_classic_catalog`: `clinical_study` (medallion),
`clinical_study_semantic` (metric views, ADR-0013 pattern) and `clinical_study_standards` (vendored standards +
closures). They are owned by dev+ect through `&shared_uc` (ADR-0019). HEDIS tables are **not** migrated. The app gets
a global demo switcher. Every backend route resolves its catalog/schema/Genie space/corpus from the active `demo_id`
(`healthcare_hedis` | `life_sciences_clinical`), and cache keys include `demo_id`. Isolation is applied where it
matters: app routes, MCP tools, RAG corpus filter, benchmark and drift runs. **Genie One is shared** (workspace-wide,
not scoped per demo), and rising workspace snippet counts are welcome. **Deploy to ECT only.** DMVM gets no
life-sciences assets unless a concrete need appears.

---

## ADR-0022 — Life-sciences ontology stack: CDISC for data shape, MONDO + MED-RT (+ MeSH bridge) for reasoning
**Date:** 2026-11-12 · **Status:** accepted (richness gate passed — `docs/life_sciences/ONTOLOGY_RICHNESS_GATE.md`)
There is no CDISC Library membership or API key, so only open standards are used. CDISC CT and COSMoS are an
excellent *data-shape* layer (Body Weight BC C81328, WEIGHT DSS with `VSORRESU ∈ {LB,g,kg}`). But CDISC/NCIt is
is-a-only and shallow for metabolic disease and drugs: Obesity sits under "Sign" with 0 roles, and semaglutide has 0
roles. That isn't enough for the graph to beat Genie Ontology or RAG. **Decision:** layer
- **MONDO** (CC BY 4.0) for diseases: 32k terms, 34% with multiple parents, depth 5–12;
- **MED-RT** (VA, via NCI EVS) for drugs: 17 typed relations, ≈100k edges (MoA, PE, may_treat, CI_with);
- **MeSH** (NLM) as the bridge: MED-RT concept UI → descriptor → MONDO xref;
- **RxNorm** (reused from HEDIS);
- **CDISC CT/NCIt** codes as the term backbone;
- **COSMoS** BC/DSS for the concept → SDTM variable layer;
- **USDM**-aligned study-design classes;
- a namespaced `cpl:` extension for rules, amendments, approvals and provenance (never presented as official CDISC).

Only curated subsets are vendored (ADR-0007 pattern), with the manifest at `src/standards/life_sciences/standards_manifest.yaml`.
MedDRA, SNOMED CT and ATC are excluded (licensed). MH is coded with MONDO + ICD-10-CM xrefs, a labeled deviation.
Claude writes the TBox and mapping files; Eli creates the Ontobricks domain and imports them (ADR-0005).
**MED-RT terms (2026-11-13):** only the public NCI EVS release is used. UMLS-distributed content is not, which settles
the documentation's "some proprietary data requires licensing" caveat.

---

## ADR-0021 — The repo becomes a two-demo lab; the ECT-off / DMVM-on Genie Ontology comparison is retired
**Date:** 2026-11-12 · **Status:** accepted · **Supersedes:** ADR-0018's tested variable (its shared-catalog mechanics stand)
The first customer delivery is done. Next: the HEDIS lab again (for a health-system audience) and a new **Clinical Study
Context & Evidence Lab** (CDISC, life sciences). Both live in one app behind a demo switcher. The A1-off/A1-on
contrast (ECT vs DMVM snippet density) is **no longer a goal**. Genie One stays a single benchmark arm, and higher
snippet density is welcome. Customer names are removed from the demo materials. Plan of record for the new lab:
`docs/life_sciences/PLAN.md`.

---

## ADR-0020 — Care-protocol knowledge edges target a ValueSet hub (not ICD codes); add Threshold; fix inDrugClass
**Date:** 2026-11-03 · **Status:** accepted
After ClinicalDomain V1 published cleanly (the metric-view scan-abort was fixed by rev-5), the cross-vocabulary
care-protocol edges — the graph's whole differentiator over a SQL closure — were nearly all broken: `inDrugClass`
returned **0 rows** (no such predicate in `protocol_edges` → the drug→ingredient→class→condition hero path was
severed), and `recommendedFor`/`contraindicatedWith` were **all dangling** (R2RML templated their objects as
`icd/{code}`, but the objects are value-set / cohort / measure ids — COMORBID_CKD, CONTRA_PREGNANCY, ALBUMINURIA,
SPD — not ICD codes). `contraindicatedWhen`/`firstLineFor`/`definedBy` were present in data but unmapped.
**Decision (modeling, Eli-owned per ADR-0005; among three options Claude recommended this one):** introduce a
first-class **`ValueSet`** entity (keyed by segment_id/cohort id) as the target of
`recommendedFor`/`contraindicatedWith`/`firstLineFor`, with a new **`contains`** edge (ValueSet → coded ICD/LOINC/
RxNorm members) so the graph traverses `DrugClass -recommendedFor-> ValueSet -contains-> Condition <-hasDiagnosis-
Patient`. This mirrors how HEDIS/eCQM/VSAC actually model measures (value-set-driven), and is the only option that
shows graph **lift** — expanding to ICD codes (rejected option B) just reproduces `icd10_closure`; per-type splitting
(rejected C) fragments the property. Also added a **`Threshold`** entity (eGFR/uACR/A1c/BP cutoffs with
`thresholdValue`) as the target of `contraindicatedWhen`/`definedBy`/`hasThreshold` — the renal-dosing + glycemic-band
knowledge behind the class-8 defined-class query. `recommendedFor` admits a Measure target for the one measure object
(STATIN recommendedFor **SPD**). **`inDrugClass`** is now sourced from `rxnorm_statin` ⋈ `rxnorm_hier.parent_code`
(statins only — the only enumerated class in the demo subset; ACE/ARB/SGLT2/BIGUANIDE ingredient lists are a data-gen
follow-on), yielding 3 reachable, non-dangling edges that complete the hero path. `monitoredBy BPD→BP` fixed in
`protocol_edges.csv` (→ LP-SBP/LP-DBP; takes effect on next terminology reload). All new maps verified against live
data (every endpoint resolves; nothing dangles). Eli re-imports the OWL + R2RML and republishes (ADR-0005).

---

## ADR-0019 — Shared-UC resources (schemas + volumes) are owned by dev+ect only, never by the dmvm target
**Date:** 2026-11-01 · **Status:** accepted
ADR-0018 adds a second **production** DAB target (`dmvm`) over the **one shared catalog**. Problem: the bundle
manages the `care_protocol*` **schemas** and their **volumes** as resources (`schemas.yml`/`volumes.yml`), and
those are **unsuffixed UC objects** in the shared catalog (unlike jobs/pipelines, which are named
`*_${bundle.target}`, and dashboards/Genie spaces, which are workspace-local). Two production targets managing
the *same* schema objects in *separate* Terraform states collide: `dmvm`'s first deploy would try to **CREATE
schemas that already exist** (ECT owns them) → `already exists` error, and — worse — a future
`databricks bundle destroy -t dmvm` could **DROP the shared schemas and all the data** ECT depends on.
**Decision:** the shared-UC-owning resources are attached to **dev + ect only**, via a `&shared_uc` YAML anchor
in `databricks.yml` (the two `resources/*.yml` files were inlined there and deleted from the `include` glob).
`dmvm` deploys **only** workspace-local / target-suffixed resources (Genie spaces, dashboards, jobs, pipeline
defs); it never owns the shared schemas/volumes. Verified via `bundle validate -o json`: ect resolves 3 schemas
+ 4 volumes; **dmvm resolves 0 of each**; both resolve the same 13 jobs / 1 pipeline / 4 dashboards. This is the
code form of ADR-0018's "catalog-scoped assets build **once**; workspace-local assets deploy to **both**."
**Consequences:** never `bundle destroy -t dmvm` expecting it to leave data intact — it won't touch shared
schemas now (good), but the data lives under ect's ownership, so teardown/rebuild of the catalog is an **ect**
operation. The `measures` pipeline + data jobs still deploy to dmvm (target-suffixed, harmless) but are
**not run** there (ADR-0018). Dev keeps its prefixed `dev_<user>_care_protocol*` schemas (dev-mode naming).

---

## ADR-0018 — Two workspaces, one shared catalog: isolate the native ontology's effect on Genie One
**Date:** 2026-11-01 · **Status:** superseded in part by ADR-0021 (the on/off comparison is retired; shared-catalog mechanics stand)
Genie Ontology is a **workspace-level** capability: once enabled, Genie One (A1) always consults the workspace
ontology (inferred snippets + modeled context). There is **no per-query "ontology off" switch for Genie One**
— the ablation ladder (`ctx_l0…ctx_l5`) only works for Genie **Agents**, which carry their own assets (P7/§11).
So a clean "native ontology vs none" baseline for A1 is impossible inside a single workspace.
**Verified (2026-11-01):** ECT (`fevm-eli-test-classic`) and **DMVM** (`fe-vm-vdm-classic-q6xfh3`) are in the
**same metastore** (`metastore_aws_us_east_1`, us-east-1); `eli_test_classic_catalog` is **one catalog object**
(ISOLATED) bound **READ_WRITE to both** workspaces. DMVM already reads `care_protocol`, `care_protocol_semantic`,
`care_protocol_terminology` with all comments (no rebuild); both have a "Serverless Starter Warehouse"; DMVM's
Genie API is reachable.
**Decision:** run the A1 experiment across **two workspaces over the one shared catalog**, varying only the
native-ontology layer.
- **DMVM = ontology-ON (treatment):** Genie Ontology enabled + Pages + Domains + certified assets + query-history
  seeding → high inferred-snippet density. DMVM is ON because ECT's tag-policy cap blocks new Domains (→ Pages
  blocked), starving inferred snippets (the original DMVM pivot — [[snippet-density-dmvm-pivot]], [[ect-environmental-constraints]]).
- **ECT = ontology-OFF (baseline, effectively):** same catalog, same governed metric-views/comments, but **below
  the inferred-snippet threshold** → Genie One answers from raw governed metadata only.
  **Correction (2026-11-01, verified with Eli — supersedes the "toggle" framing):** There is **no Genie Ontology
  on/off switch** — it is always on. Inferred snippets are only **fetched when the workspace holds more than
  ~1,000 snippets**. Measured: **ECT ≈ 200** (below → effectively no inferred-ontology context = the baseline),
  **DMVM ≈ 1,100** (above → inferred snippets active = the treatment). So the OFF/ON split is a **natural
  density-threshold effect**, not a switch we flip — which is exactly why the DMVM bring-up drives snippet count up
  (Pages, dashboards, Genie agents, query-history, analytics notebooks all mint snippets). Domains are
  **metastore-level** (`Clinical Domain` id `b624f99f-8903-40db-a1d6-61c11e3336e7`, same object on both) and the
  Pages volume is in the shared catalog, so nothing is torn down on ECT; its baseline-ness is purely the
  sub-threshold snippet count. Published **Pages are per-workspace**, so the ON arm (DMVM) still needs its own
  import. **Extraction is slow:** new snippets surface on roughly a **daily** cadence (sometimes hours), **not**
  minutes — plan verification around that. Still **observational, not causal** (snippet density co-varies with
  Pages/Domains/usage) — label it so.
Data **and** modeled metadata are held constant (one catalog); the only variable is the native-ontology layer —
the cleanest contrast the platform allows. **Still observational, not causal** (P12): the ON env also adds
Pages/Domains, which ARE part of the native-ontology mechanism — label it so. The capability map's
`a1_genie_one` column **splits into `a1_off` (ECT) / `a1_on` (DMVM)**.
**DAB:** one bundle; `catalog` var stays `eli_test_classic_catalog` for both; add a **`dmvm` target** beside
`ect`. Catalog-scoped assets build **once** (already live); workspace-local assets (Genie spaces, dashboards,
persist_benchmark) deploy to both; the ontology layer (seed job + Pages/Domains + enabling Genie Ontology) is
**DMVM-only** and partly manual (⚙ RUNBOOK). Query-history usage signal is per-workspace → seed on DMVM.
**Consequences:** Ontobricks (A5, explicit graph) stays a separate arm; the three-way read becomes baseline
(A1-off) vs native inferred ontology (A1-on) vs explicit graph (A5). Keep it reproducible so a fresh DMVM
rebuilds the ON env.

**Addendum (2026-11-04) — observed evidence: the inferred layer fires on BOTH workspaces, and ECT's is the on-topic one.**
Genie One's raw response stream (`/api/2.0/data-rooms/tools/onechat/responses`, what `genie ask --raw` prints) carries the
retrieved snippets in each tool output's metadata (`search_knowledge_snippets` → `knowledge_pages` + `knowledge_snippets`),
so retrieval is now observable, not inferred. Same GSD patient question, run as Eli: **ECT returned 20 inferred snippets, all
about this demo** (mined from the dev Genie spaces and metric views — some from the stale pre-relocation views, now dropped);
**DMVM returned 6, all from other projects in the shared metastore** (epic_emr_demo, pharma_nba, an allergy view). As the
app's service principal, DMVM returned 0 — snippet retrieval is identity-scoped. So "ECT ≈ ontology OFF" does not hold: the
~1,000-snippet fetch threshold is not what separates the arms. The a1_off/a1_on contrast stays parked (2026-11-03); the
Tracer's Genie Ontology click-in shows the live per-question trace so the demo states what was actually retrieved.

**Addendum (2026-11-02) — the ON effect is the INTENT, not yet a verified result.** Probed DMVM directly
(`genie ask --raw`) rather than assuming: `search_knowledge_snippets` fires but the stream exposes no snippet
payload ("Found 4 results"), and Genie One grounds entirely in the **16 curated Pages + catalog assets found via
`search_assets`/`information_schema`** — the *modeled* layer, which **ECT has too**. So we have **no observed
evidence that the inferred/"learned" snippet layer is doing work on DMVM**; the ~1,100 figure is UI-reported
*density*, not evidence of *retrieval*. **This does not change the decision — it sharpens its honesty.** The
plan stands: treat `a1_on` (DMVM) as the **intended** ontology-ON arm and deliberately build the per-workspace
surfaces that mint inferred snippets (analytics notebooks, dashboards, Genie agents, metric views, column
comments, query-history seeding), *assuming* the inferred layer will eventually surface. But **whether Genie One
actually retrieves inferred snippets — vs. always grounding in the shared curated Pages/metric views both arms
share — is itself an open empirical question this demo is designed to answer, not a premise to assert.** The
demo says so out loud. `a1_on` verdicts stay **pending** that surface build + extraction (daily cadence) **and**
a question that only an inferred snippet can answer (design criterion + candidates in
`docs/benchmark/inferred_ontology_discrimination.md`). Lead the benchmark story with the hand-verified **layer**
capability map (M0 < closure < Genie-One-over-modeled; graph-only class 8), which stands on its own.

---

## ADR-0017 — SSD behavioral-health cohort is synthesized (Synthea has no SMI/antipsychotic signal)
**Date:** 2026-10-31 · **Status:** accepted
SSD is cross-domain: it needs serious mental illness (F20/F25/F31) + antipsychotic dispensing + a metabolic
screen. The generated Synthea population (25,000 patients) contains **none** of that — zero F20/F25/F31
diagnoses and zero antipsychotic orders (verified by query). So unlike GSD/KED/BPD/SPD/EED, SSD **cannot** be
derived from bronze; its cohort must be synthesized.
**Decision:** a dedicated generative step `src/data_generation/ssd_cohort.py` (job `ssd_cohort`, after epicize,
before the measures pipeline) — the behavioral-health analogue of `care_behavior.py` (ADR-0012). It is seeded
and deterministic (xxhash), and the screening rate is **emergent** (a per-patient logistic of a latent
engagement factor + a smooth per-clinic effect), never a fixed injected rate. Cross-domain links are kept
*real* so the graph does the work in `measures.py`, not a flag: (1) antipsychotic dispensing carries a RxNorm
clinical-drug (SCD) code that subsumes to an antipsychotic **ingredient** through `rxnorm_closure` — the same
ingredient→drug resolution SPD uses for statins (SCD children added to `rxnorm_hier.csv`); (2) the pre-existing
diabetes **exclusion** is actual overlap with the diabetes cohort (ICD-10 E10/E11/E13 via `icd10_closure`), not
an arbitrary flag. It writes one effective-layer table `care_ssd_cohort`; `measures.py` builds
`gold_adherence_ssd` from it via the value sets + closure, and the previously-pending `ssd_compliance` metric
view is activated. Everything is labeled synthetic / HEDIS-aligned (SSD-proxied) / not NCQA-certified. Honesty
note: the added SCD codes are representative demo clinical drugs (names tagged "demo SCD"), consistent with the
hand-curated demo value sets (ADR-0002) — not an authoritative RxNorm release.

---

## ADR-0016 — Document-RLS ACL check goes through a SECURITY DEFINER function
**Date:** 2026-10-31 · **Status:** accepted
Design doc §8 wants two things that collide under Postgres RLS: (a) the reader role must **not** be able to
directly `SELECT` `rag.document_acl` / `rag.group_membership` (so it cannot enumerate the org's ACLs or
memberships), yet (b) the row-visibility policy must consult exactly those tables. Postgres evaluates a policy
`USING` predicate **as the invoking role**, so a plain inline predicate requires the reader to hold SELECT on
the control tables — directly contradicting (a). (The committed inline-predicate version passed the offline
structure test but failed the first live read with `permission denied for table group_membership`; caught only
by running `tests/test_rag_rls.py` against a live Lakebase.)
**Decision:** encapsulate the allow-with-deny-precedence decision in **`rag.acl_allows(document_id, caller)`**,
a `SECURITY DEFINER` SQL function owned by the schema owner. It runs with the owner's privileges (can read the
control tables) and returns only a boolean; `rag_reader` is granted `EXECUTE` but keeps **no** direct SELECT on
the control tables. The caller identity is captured as `current_user` in the policy (invoker) context and passed
as an argument, because inside a `SECURITY DEFINER` body `current_user` resolves to the function owner, not the
caller. `search_path` is pinned (`SET search_path = rag, pg_temp`) against search-path injection. Both the
`chunks` and `documents` policies share the one function, so `documents` now also honors DENY-precedence (no
behavior change on an allow-only corpus). This is the standard Postgres pattern for RLS that must consult
tables the querying role cannot see. Verified live on ECT: 4/4 negative-security tests pass on both the
Lakebase Search (BM25) and pgvector/full-text fallback paths.

---

## ADR-0015 — Allocation of care-protocol source material across RAG / Pages / metric views; add SSD + a GSD-GMI drift
**Date:** 2026-10-31 · **Status:** accepted
Seven public reference PDFs (VA/DoD Diabetes CPG, CMS QRS 2027 technical specs, HEDIS toolkit, an adult
diabetes clinical practice model, a provider GSD page, the HEDIS SSD measure, and ICD-10 diabetes coding
guidance) were mined for facts (extracts in `docs/care_protocol/source_extracts/`). **No proprietary text is
reproduced** — facts are paraphrased into synthetic documents; public-domain sources (VA/DoD, CMS QRS) are
attributed. Content was allocated by the rule *"which surface is the right home for this kind of fact?"*:

| Fact type | Home | Why |
|---|---|---|
| Prose clinical guidance a structured arm should *refuse* (A1c targets by comorbidity, metformin eGFR 45/30, SGLT2/GLP-1 cardiorenal even at A1c goal, ACE/ARB uACR gate, retinal 6-mo/biennial cadence, elderly de-intensification, pregnancy contraindications) | **RAG corpus** (`docs/care_protocol/corpus/*.md`) | Narrative, not computable from coded data; this is exactly what the A4 document-RAG arm should win on in the capability map (classes 6-7). |
| Short authoritative *definitions* (measure defs incl. new SSD, ICD-10 diabetes subsumption, document access scope) | **Genie Pages** (`docs/ontology/pages/*.md`) | Highest-authority ontology snippets; a Page states "KED = eGFR AND uACR", the corpus explains the clinical *why*. |
| Computable numerator/denominator/rate over gold tables | **Metric views** | Governed KPI layer shared by BI + Genie. |

**HEDIS measures added/changed for metric views:**
- **SSD** (Diabetes Screening for People With Schizophrenia/Bipolar on Antipsychotics) — a cross-domain
  measure (SMI dx + antipsychotic RxNorm + glucose/HbA1c LOINC). Page + value sets + a **pending** metric view
  (`src/semantic/metric_views/pending/ssd_compliance.metric_view.sql`) are committed; it activates once the
  data pipeline produces `gold_adherence_ssd` (a behavioral-health cohort — the flagged data-gen next step).
- **GSD + GMI (MY2026)** — a *second* controlled drift scenario alongside the existing race-based-eGFR KED
  drift: MY2026 GSD accepts a CGM-derived Glucose Management Indicator (LOINC `97506-0`) as equivalent to a
  lab HbA1c. Encoded as MY2026 rows in `value_sets_demo.csv`; a CGM-only patient flips from gap→compliant on
  identical data purely from the value-set version.

## ADR-0014 — A4 Lakebase re-aligned to a document-RAG corpus with Lakebase Search + document-level RLS
**Date:** 2026-10-31 · **Status:** accepted (code committed; external apply confirm-gated)
A4 previously retrieved over a thin corpus of one row per Genie Ontology Page (ADR-0009). That is not a
document-RAG story and under-sells the arm in the capability map. Re-aligned per the "Lakebase Search Document
Level Authorization" design doc (Eli's, co-authored with Glean):

- **Corpus = the care-protocol clinical documents** — a multi-document corpus (`docs/care_protocol/corpus/`:
  glycemic targets & deprescribing, cardiorenal pharmacotherapy, retinal cadence, SSD behavioral-health
  screening, a MY2026 payer memo, a patient-specific outside eye-exam letter) plus the existing HTML protocol
  anchor. Chunked **deterministically** with section/page provenance by `scripts/lakebase_rag_corpus.py`
  (reproducible-by-code; the benchmark tracers stay byte-stable). For arbitrary real PDFs the Databricks-native
  path is `READ_FILES → ai_parse_document → ai_prep_search` (design doc §6) — documented as the production
  ingestion; the local chunker is the demo's reproducible path over the synthetic corpus.
- **Serving schema** `rag.documents / rag.chunks / rag.document_acl / rag.group_membership`
  (`src/retrieval/lakebase/schema.sql`), with **Lakebase Search** indexes (`lakebase_ann`, `lakebase_bm25`) and
  a **pgvector + full-text fallback** so the demo runs whether or not Lakebase Search is enabled. Embedding dim
  **1024** (`databricks-gte-large-en`).
- **Document-level authorization via Postgres RLS** on `rag.chunks`/`rag.documents` (ALLOW/DENY ACL +
  group_membership, deny-precedence), evaluated with `lakebase_ann.prefilter = on` so unauthorized rows are
  never scored by the index. Two clinical scopes — `quality_analytics` (population/spec docs) and `care_team`
  (also patient-specific records) — **realize the `+perm` security tracer at the RAG layer** (roadmap §7).
  The retriever connects with the **end-user identity**; `A4RagRetriever` (`src/retrieval/a4_lakebase.py`)
  adds `search_documents` (lexical/semantic/hybrid) returning cited passages, and `tests/test_rag_rls.py`
  encodes the design doc §13 negative-security tests.
- **Enabling Lakebase Search is irreversible and restarts computes** → a one-time ⚙ confirm-gated RUNBOOK step,
  as is loading the corpus. Not a DAB resource (ADR-0009 still holds): schema + corpus build are committed code
  applied via RUNBOOK.
- **Scope note:** this is a demo-grade realization of the design doc's production pattern (ACLs, group
  membership, deny semantics, OBO identity, prefilter). The doc's full reconciliation/observability/revocation
  hardening (design doc §11-13) is deliberately out of scope for the demo and listed as future work.

## ADR-0013 — Metric views relocated to a dedicated `care_protocol_semantic` schema
**Date:** 2026-10-30 · **Status:** accepted
The Ontobricks entity scan over `care_protocol` kept auto-binding ABox-less OWL classes to the governed
`*_compliance_metrics` **metric views** and failing with `METRIC_VIEW_MISSING_MEASURE_FUNCTION` (a metric
view can't be probed with a plain `SELECT` — it needs `MEASURE()`), which aborted the scan (see
`src/ontology/README.md` rev 3/4). Two fixes were on the table:
- **(A) UI exclude** — deselect the 7 `*_metrics` views (or allow-list only `bronze_*/silver_*/gold_*` +
  `care_protocol_terminology.*`) in the Ontobricks data-source config. Fast, zero repo change, but it lives
  only in UI state and is easy to forget on a fresh workspace.
- **(B, chosen) Relocate as code** — move the metric views out of the scanned base schema into a dedicated
  **`care_protocol_semantic`** schema. The views' `source:` still points at `care_protocol.gold_adherence_*`;
  only the view objects move. A scan scoped to the base schema then cannot see them at all.
Chose **B**: it is reproducible-by-code (DAB), survives a fresh FEVM rebuild, and cleanly separates the
BI/Genie/SQL **consumption** layer from base data. The per-view UI exclude (A) stays as belt-and-suspenders.
- **Touched (as code):** `resources/schemas.yml` (declare the schema); `src/semantic/metric_views/*.sql`
  (view target → `{semantic_schema}`, `source:` stays `{schema}`); `apply_metric_views.py` (+`--semantic_schema`);
  `resources/jobs.yml` (semantic + seed_query_history params); `seed_query_history.py` (metric-view queries →
  `{sch_sem}`); `care_protocol.geniespace.json` + `quality_by_age.lvdash.json` (repointed); the five
  `docs/ontology/pages/*.md` `related_assets`. `benchmark_questions.json` needs no change (scorer substring-matches
  the unqualified view name).
- **Ontobricks scope caveat (ADR-0005, Eli-owned):** the mapping source scope must remain
  `care_protocol.{bronze_*,silver_*,gold_*}` + `care_protocol_terminology.*` and must **NOT** include
  `care_protocol_semantic`.
- **Migration:** metric views hold no data — relocation = recreate in the new schema + drop the 7 originals in
  `care_protocol`. External ECT writes (`bundle deploy` + the drops) are gated on Eli's confirmation.

## ADR-0012 — Realistic variation via a generative care-behavior model (not point injection)
**Date:** 2026-10-30 · **Status:** accepted
Raw Synthea is stationary and uniform: protocol follow-up, MAD and glycemic control are all flat, so the watch
has nothing to detect, MAD saturates at PDC=1.0, and nobody is in poor control. The **rejected** fix is
"tracers" — slamming a few patients to extremes or cliff-dropping one unit in Q3; an analyst spots that as
fake and it pre-wires the answer. Instead, `src/data_generation/care_behavior.py` is a **seeded generative
behavioral model** (runs AFTER `epicize`, BEFORE `measures`): every cohort patient gets latent engagement, a
**real** complexity measure (distinct ICD-10 codes), a provider/panel random effect, mild seasonality, and a
patient→panel(PCP)→clinic structure; follow-up, medication fills, and glycemic control then **emerge** from
thousands of deterministic (seeded xxhash) Bernoulli draws. One clinic (**CLINIC-08**, the highest-complexity
site) gets a **mid-year PCP handoff** that adds a gradual, decaying coverage-gap term — not a cliff — and is
**confounded** with that clinic's higher case-mix (so a naive read blames complexity, not the handoff).
- Outputs: `panel_roster`, `panel_pcp_transition`, and an **effective event layer** `care_order_results` /
  `care_order_med` that `measures.py` reads. Deterministic → reproducible golds. `--intensity` scales the
  disruption; the bronze layer stays pristine.
- **Clean separation so recomputed golds == model truth:** protocol triggers are the RECORDED bronze highs
  (values untouched); a followed trigger emits a MARKED recheck (excluded from triggers); glycemic control is a
  patient ATTRIBUTE (`glycemic_poor`/`modeled_a1c`) GSD reads — it never edits the observation stream.
- **Nothing is wired to an answer.** `clinic_id`/`panel_id`/`glycemic_poor`/the transition are plain
  dimensions; the cause of any drift is recoverable only by joining drift × clinic × transition × case-mix ×
  time — exactly the multi-hop reasoning the capability-map benchmark compares.
- Validated distributions (25k, seed 20261029): overall follow-up 57%, CLINIC-08 Q3 47% vs its own 78% prior;
  MAD 47.8% adherent (continuous PDC); poor control 24%; confound complexity 4.55 vs 4.12. The `protocol_watch`
  (ADR-0011) scans CLINIC × trailing-3-month vs each clinic's own prior baseline and fires **HIGH on CLINIC-08**.
This also upgrades gap #6 ("planted tracers") to a serious, reproducible substrate and is a down-payment on
gap #4 (panel/PCP/transition dimensions).

## ADR-0011 — Weekly Protocol Watch = Genie One scheduled task (front door) + a pre-computed findings job
**Date:** 2026-10-30 · **Status:** accepted
The story's hook ("nobody asked; Genie noticed") is a **proactive, scheduled** drift-watch. Built two
mutually-reinforcing pieces (corrected after I wrongly claimed Genie One can't be scheduled — it can):
- **Genie One scheduled task** is the demo front door — the actual "A Monday with Genie" watch. Set up in
  the UI (Genie One → Schedules → Create manually, or natural language); **no API**, so it lives in the
  RUNBOOK as a manual step like Pages bulk import / Ontobricks. Runs on a schedule, posts to a chat thread,
  emails the owner results + PDF.
- **`protocol_watch` job** (`src/watch/protocol_watch.py`, bundle-managed, serverless) pre-computes an
  auditable **`protocol_watch_findings`** table so the scheduled task answers fast and grounded, and leaves a
  lineage record Genie One reasons over. Drift detection is **serious**: right-censoring aware (score a
  trigger month only once its 90-day follow-up window is fully observed), small-N gated, pooled baseline
  across fully-observed months — not a toy threshold. **Append-only** (each run = an as-of snapshot).
- The job's **schedule is PAUSED** and **no external notification** recipient is wired — notifications are an
  external write (confirm a destination first; then add a SQL Alert or job notification). This is *not* the
  value-set-vintage drift demo (that stays); this is operational process-adherence monitoring.

## ADR-0010 — Serious benchmark: capability map, not a leaderboard (see BENCHMARK_CHARTER.md)
**Date:** 2026-10-30 · **Status:** accepted
The first-cut benchmark was trivial: single-KPI questions answerable by a metric view, with latency as the
headline (a hardcoded tool beats an LLM by construction — not a retrieval-quality finding). Replaced by a
**capability map** (see `docs/BENCHMARK_CHARTER.md`): for realistic hard questions, *which context/retrieval
approach is sufficient / adds unique value / is necessary*, and **why**. Key corrections (from Eli):
- **A closure table is NOT an oracle.** It precomputes one relation (is-a): it equals a graph for single-relation
  rollups (ICD cohort, RxNorm statin) but cannot do typed multi-edge traversal, variable-length mixed paths,
  inference, or qualifier-constrained traversal. It is a **competing arm**, not the answer key.
- **No pre-wiring.** Every arm (incl. governed-MCP) must **reason**; ground truth is hand-verified per question,
  independent of any arm.
- **Primary metric = accuracy on hard questions**; latency/cost secondary. **Lineage** (bronze patient → care-
  protocol PDF + encounters + prescriptions → retrieved context → answer) is the spine.
- **Graph = LOINC (multiaxial Parts) + ICD-10 (is-a, closure-complete) + RxNorm (typed rels) + protocol edges,
  linked** — license-clean (LOINC license, no SNOMED). LOINC is the "graph > closure within a vocab" exemplar.
  **Correction (refined in ground_truth.yaml):** classes 2-6 (incl. cross-domain protocol multi-hop) are
  fixed-shape SQL over materialized closure/edge tables, so **none strictly require Ontobricks**. Ontobricks is
  genuinely necessary only for **class 8** (path/explanation queries + OWL-defined classes; variable-shape /
  inference). Resolution placement (build-time metric view -> Genie Ontology; query-time closure; live graph)
  is the real variable.
- **Scale = 25k patients**; add a **care-protocol PDF** as the unstructured anchor. **Genie One** is the front
  door; components (RAG/closure/graph/Pages) plug in via MCP and are visualized in the app.

**Addendum 2026-11-05 — retrieval tiers; arms retrieve, they don't run the answer key.** Until today the
`metric_view` arm injected a hand-picked `MEASURE()` result per question, and `closure_sql` injected the
**gold answer-key query's own result**. Both are the pre-wiring this ADR forbids. Now `metric_view` retrieves the
YAML definitions of the 3 most relevant certified metric views, and `closure_sql` retrieves the terminology table
cards plus the rows the question's linked entities hit. It uses the same entity linker as the graph, so
closure vs graph differs only in the store. Each cell is scored in **tiers** from the same retrieved context:
(1) every gold fact is explicitly in the context, judged per fact; (2) the agent writes ONE SQL query using only
names in the context, we run it, and its rows are judged per fact; (3) neither. 3 runs per cell, majority
reported. Class 8 now has a question built for the graph (`graph_contra_conflict`: a patient's own diagnosis vs
the protocol's contraindication rule), which replaces the rationale-path question that prose could answer.
Information-wise the graph adds nothing over `protocol_edges` + `value_set_segment` + closures (it is built from
them); what differs is that patient facts, hierarchies and rules sit in one traversable store. First run: only
the graph's context held the patient's records and the rule together (tier 1, 2 of 3 runs), while Genie One solved
it end-to-end from the relational tables.

**Addendum 2026-11-06 — closure redesigned as a retrieval approach, not the answer key.** After the
"Closure-Table Retrieval on Databricks" technical review. Before: the closure arm first injected the gold query's
result, then table cards plus entity-matched rows for the agent to write free SQL against. Now it follows the
review's pattern: the direct edges (`icd10_hier`, `rxnorm_hier`) are the source of truth and the closures are
derived. Retrieval runs through four parameterized tools (`closure_context` in `src/app/server/context_retrieval.py`):
`resolve_nodes` (node-name match + alias table), ancestors, descendants, and `patients_under` (the content join:
patients with a diagnosis / medication order in the subtree). The agent writes no SQL. One relationship (is-a) only;
protocol rules are a different relationship and are deliberately left out, so cross-relationship multi-hop is the
graph's job. `scripts/validate_closure.py` checks the review's acceptance criteria (self rows, unique keys, direct
edges at depth 1, no missing nodes, no cycles, equal to a recursive traversal): all pass.
Not adopted: scope_id/tenancy, AI Search filtering by closure ids, UC-function registration of the tools, and the
DAG min-depth contract (our hierarchies are trees). Gap found: `rxnorm_closure` mixes two relationships
(class -> ingredient and ingredient -> product), which the review says to keep separate.
Demo set is now 5 questions (one story each). First run: metric view alone answers the clinic Step-3 question;
closure alone answers "diabetes with kidney complications" (1,881) because it resolves the concept by name, while
the graph and Genie Ontology both misread it as diabetes AND CKD (1,791) -- the graph carries no code names; the
graph alone answers the statin-contraindication cohort (198), the only cross-relationship question.
Also: the ECT `(Clone) [dev]` Genie space was migrated to current names (`scripts/migrate_genie_space_names.py`;
before-state in `docs/benchmark/genie_space_migrations/`). Genie Ontology snippets still carry the old names until
Genie re-mines it.

**Addendum 2026-11-06 (b) — one native query per approach, quote-checked judging, typed and multi-parent closures.**
(1) The one-shot step now uses each approach's own interface: SQL for metric views, Genie Ontology and RAG; one
closure-tool call (resolve / ancestors / descendants / is_under / patients_under); one graph-runner call
(`src/app/server/graph_runner.py`: find_nodes / neighbors / routes / paths / match over the published graph's node
and edge layer, in memory, ~194k edges, no extra dependency). One `match` call answers the statin-contraindication
cohort (198) deterministically. (2) Judging: each gold fact is judged against the retrieved context, and only if one
is missing, against the query result. The judge must return a verbatim quote, which code checks in the text (one
retry if it paraphrased), so every verdict shows the exact span or the exact gap. The quote must state the fact on
its own; an inference doesn't count. Each cell gets a one-line reason generated from that evidence. (3) Data: the RxNorm
edges are typed (`rxnorm_hier.relationship` = class_member / ingredient_of), with a closure per relationship;
`rxnorm_closure` is their explicit composition (identical rows, plus `relationship_path`), so no downstream job
changed. `icd10_hier` is a DAG: E11.22 is under E11.2 and N18. `build_closure.py` now uses the review's deduplicated
frontier (one row per pair at the shortest distance) and validates before publishing; `validate_closure.py` passes
for all four closures. (4) The Ontobricks mapping gains labels and every drug class's membership, but the published
graph (v3) predates it: the graph misses the E11.22 -> N18 route until it is republished. Demo set: 6 questions.

## ADR-0009 — A4 Lakebase = Autoscaling project; hybrid retrieval over the ontology corpus
**Date:** 2026-10-30 · **Status:** accepted
A4 (Lakebase hybrid retrieval) uses a **Lakebase Autoscaling** project, not the retired **Provisioned**
tier (`databricks database` is legacy; use `databricks postgres`). Project **`care-protocol`** (production
branch, primary endpoint, db `databricks_postgres`, PG 17, scale-to-zero). The retrieval **corpus** is one
row per Genie Ontology Page, derived from `docs/ontology/pages/*.md` by `scripts/lakebase_corpus.py`
(reproducible-by-code), with a `tsvector` GIN index. Retrieval is **hybrid**: Postgres full-text **lexical** ranking (OR-of-terms tsquery) + **pgvector** (0.8.0)
**semantic** cosine over gte-large-en (1024-dim) embeddings, fused with **Reciprocal Rank Fusion**
(`src/retrieval/a4_lakebase.py`: `search` / `search_semantic` / `search_hybrid`). Embeddings loaded by
`scripts/lakebase_embed.py` (governed endpoint, HNSW cosine index). Verified: semantic retrieves gsd/hba1c
for "poorly managed sugar levels" with no exact lexical match.
**Not a DAB resource:** the DAB `synced_database_tables` resource is deprecated and `postgres_*` DAB support
is not yet usable (per the databricks-lakebase skill), so the project is created via CLI and captured as a
RUNBOOK step; the corpus build + retrieval are committed code. Connectivity: OAuth token via
`databricks postgres generate-database-credential` (SDK `w.postgres.generate_database_credential`), ~1h TTL.

## ADR-0008 — Persistence mechanism per ontology artifact (metric views, comments, domains, Pages)
**Date:** 2026-10-29 · **Status:** accepted
Verified against the DAB schema (CLI 1.17.0), the live ECT API, and the docs how each Genie-Ontology
artifact can be created, and chose the most code-reproducible mechanism for each:

| Artifact | DAB resource? | API/CLI | **Mechanism chosen** |
|---|---|---|---|
| **Metric views** | no dedicated type | DDL runs on SQL warehouse **or** DBR 17.3+ compute | **Serverless task** `apply_metric_views.py` runs committed `src/semantic/metric_views/*.metric_view.sql` (`{catalog}`/`{schema}` substituted). Confirmed working on serverless — no warehouse dependency; consistent with load_terminology/epicize. |
| **UC comments** | n/a | SQL `COMMENT ON` | **Serverless task** `apply_comments.py` runs committed `src/semantic/comments/*.comments.sql`. Works on materialized views too. |
| **Business domains / subdomains** | ❌ none (only Terraform `databricks_domain`) | ✅ `databricks domains` (Beta) + `databricks tag-policies` | **Committed idempotent script** `scripts/create_domains.py` + RUNBOOK run step. A domain is **built on a governed tag** (`create-domain TAG_KEY` is required/positional; the domain's display name IS its tag_key); subdomain = governed tag `Parent/Child` + `--parent-domain-id`. Section polish is UI-only. **ECT:** account at governed-tag-policy cap → cannot mint new tags; resolved by reusing the free existing tag `Clinical Domain` (one domain, no subdomains — `--root-tag`). See RUNBOOK. |
| **Pages** | ❌ none | ❌ no public API/CLI/Terraform (internal `createPage` audit events only) | **Content-as-code** (`docs/ontology/pages/*.md`, one per term: domain, synonyms, body) + **RUNBOOK** Genie Code bulk-import step. Pages require a domain to exist first. |
| **Genie Agents (A2)** | ✅ `genie_spaces` | — | **DAB resource** `resources/genie_spaces.yml`. |

Governing rule (ADR precedent / memory `persist-everything-as-code`): everything is code where an API
exists, step-by-step RUNBOOK only for the one irreducible manual action (Pages bulk-import). Of the ~1000
ontology snippets (roadmap §7a), the fully-codeable sources (metric views, comments, dashboards,
query-history seeding, Genie agents) carry the bulk; Pages are content-as-code + a manual import click.

## ADR-0007 — Vendor curated terminology subsets in-repo (no Drive/runtime dependency)
**Date:** 2026-10-29 · **Status:** accepted
Terminology the demo references is **vendored in the repo** at `src/terminology/` as small **curated
subsets** — not pulled from Google Drive at runtime and not the full licensed releases. Rationale:
reproducible from the repo alone; code values are facts; subsets stay minimal and attributed. Files:
`icd10cm_subset.csv` (public), `loinc_subset.csv` (LOINC License, attributed), `rxnorm_statins.csv` (NLM),
`value_sets_demo.csv` (demo value sets — not NCQA/VSAC), loaded by `load_terminology.py`.
`icd10cm_subset.csv` is the adjacency that `closure_tables.sql` builds `icd10_closure` from. **Supersedes
the "staged from Drive / never commit" mechanism in ADR-0002** (the terminology *choice* in ADR-0002
stands; only the sourcing changes). Full raw releases, if ever staged, stay gitignored under
`context/terminology/data/`. Demo scope — validate codes against official sources before non-demo use.

## ADR-0006 — Add closure + segment tables as a third hierarchy-encoding differentiator
**Date:** 2026-10-29 · **Status:** accepted
Include a **closure table** (`icd10_closure`, optional `loinc_part_closure`) + **segment table**
(`value_set_segment`) as a distinct, purely relational way to encode hierarchy/semantics — a **third
differentiator** alongside Genie Ontology (LLM writes SQL from context) and Ontobricks (OWL graph via MCP).
"Whole subtree at any depth" collapses to one equality (`WHERE ancestor_code = X`), which answers the **T3
subsumption tracer** (`E11.21` ⊏ `E11`) deterministically; the segment table captures cross-branch value
sets/cohorts no subtree equals (each with a named owner). It is also the **"Genie + closure view"** benchmark
arm (Genie reaches graph parity once a closure view + metadata exist). Plugs in at **P2** (build, recursive
CTE at write time), **P4** (register as governed UC tables/views), **P12** (closure vs adjacency encoding +
the Genie-with-closure ablation point), **P13** (a "Hierarchy Encodings" app exhibit: six patterns + paired
queries). Costs: closure grows with depth×nodes and rebuilds on restructure (drift); segments need owners.
Spec: `src/semantic/hierarchy_encodings.md` + `src/semantic/closure_tables.sql`.

## ADR-0005 — All six retrieval arms in scope; Ontobricks set up manually by Eli
**Date:** 2026-10-29 · **Status:** accepted
Scaffold for all arms A1–A6 (Genie One, Genie Agents, ablation ladder, Lakebase, Ontobricks, supervisor).
**Ontobricks (A5) is set up by Eli using his own detailed instructions — do NOT automate its deploy.** The
build provides only the integration contract (what the ontology consumes from Gold + terminology; R2RML
targets). An `ontobricks_wh` already exists on ECT.

## ADR-0004 — Benchmark seeds from the vendored Genie GenAI Evals notebook (A2 only)
**Date:** 2026-10-29 · **Status:** accepted
`src/benchmark/Genie GenAI Evals.dbc` (Eli's, FEVM-proven) is the P12 starting point. It evaluates a
**Genie Agent (space)** in chat + Research modes — this is **arm A2 only**. It does **not** evaluate
**Genie One (A1)**; A1 needs a separate `predict_fn` reusing the scorer/tracing pattern. Extend `predict_fn`
+ scorer registry for A4/A5/A6. `sql_result_match` applies only to arms returning result rows; never
penalize a correct refusal. See `src/benchmark/README.md`.

## ADR-0003 — App: reuse-vs-net-new still open (leaning net-new)
**Date:** 2026-10-29 · **Status:** open
The Hospital Control Tower is leverage-or-rebuild. Net-new is likely cleaner (its date-shifting/startup
mutation would break measurement-year reproducibility; string-based SQL "security" must be replaced).
Decide at P13. Tabs are the same either way.

## ADR-0002 — Terminology without SNOMED/UMLS/VSAC
**Date:** 2026-10-29 · **Status:** accepted
No SNOMED CT / UMLS / VSAC license is available or will be requested. Terminology uses **free code systems
only**:
- **LOINC 2.83** (standard release, staged from Eli's Drive) — labs/observations + the Part hierarchy.
- **ICD-10-CM** (public domain) — diagnoses, cohort, exclusions, **and the subsumption demo** via its code
  hierarchy (e.g. `E11.21` ⊏ `E11.*`), replacing SNOMED is-a. The T3 tracer uses ICD-10-CM.
- **RxNorm** (free NLM) — medications (statins/SPD).
- **Hand-curated demo value sets** (from LOINC/ICD-10-CM/RxNorm), labeled *demo — not NCQA/VSAC*.

Synthea's SNOMED-coded conditions are crosswalked to ICD-10-CM (code values in synthetic data are fine; we
do not ship licensed SNOMED hierarchy tables). The **LOINC SNOMED Extension** in Drive is optional input for
the Ontobricks track only, if SNOMED is ever licensed. Honor `LoincLicense_5.8`; load terminology from a UC
Volume, never commit it, never write back to Drive. *Supersedes VSAC/SNOMED assumptions in `docs/sources/`.*

## ADR-0001 — Target workspace = ECT (serverless)
**Date:** 2026-10-29 · **Status:** accepted
Build on the **ECT** profile (`fevm-eli-test-classic.cloud.databricks.com`). A FEVM "classic" workspace
includes **both serverless and classic** compute; ECT has serverless, Lakebase (Public Preview), embedding
endpoints (`gte/bge/qwen3`), Claude/GPT/Gemini model serving, and an existing `ontobricks_wh`. ECT has
**Default Storage**, which blocks ad-hoc SQL catalog creation, so demo assets live in the workspace's
managed catalog **`eli_test_classic_catalog`** — schemas `care_protocol` (medallion/semantic) and
`care_protocol_terminology` (terminology + closure). Never auto-select a profile — always `--profile ECT`.
(To use a dedicated `care_protocol_ontology` catalog instead, create it once in Catalog Explorer with
Default Storage and set `--var catalog=care_protocol_ontology`.)
