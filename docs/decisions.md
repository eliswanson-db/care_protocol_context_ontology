# Architecture Decision Records (ADRs)

Short, dated records of decisions that shape the build. Newest first. These **supersede** any conflicting
statement in the source plans under `docs/sources/`.

---

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
