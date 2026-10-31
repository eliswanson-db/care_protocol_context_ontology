# RUNBOOK — manual (⚙) and async-wait (⏳) steps

Ordered operational steps that are **not** automated by the bundle. Keep this current as phases land.

## P0 — setup
1. ⚙ **Auth** — `databricks auth login https://fevm-eli-test-classic.cloud.databricks.com --profile ECT` (already valid).
2. ⚙ **Capability gate** — confirm on ECT and record in `capability-matrix.md`: **Genie Ontology ON**,
   **Apps enabled**, MLflow 3, Lakebase, Model Serving + embedding endpoint, Genie Agent API.
3. 🤖 **Schemas + volume are declarative** (`resources/schemas.yml`, `resources/volumes.yml`) — created by
   `databricks bundle deploy -t ect --profile ECT`. The catalog pre-exists (ECT Default Storage blocks SQL
   catalog creation — ADR-0001).
4. 🤖 **Run the setup jobs (all bundle-managed — no ad-hoc SQL):**
   - `bundle run setup -t ect` → `load_terminology` (vendored CSVs → UC tables, no Drive, ADR-0007) → `build_closure` (iterative BFS → `icd10_closure`).
   - `bundle run generate_synthea -t ect` → classic job: stage pinned Synthea JAR to the Volume → run Synthea → `raw_synthea_*` tables.
   - `bundle run epicize -t ect` → SNOMED→ICD-10 crosswalk → `bronze_*` Clarity-shaped tables.
   - `bundle run care_behavior -t ect` → seeded generative care-behavior model (ADR-0012): patient→panel(PCP)→clinic
     structure + a mid-year clinic PCP handoff; writes `panel_roster`, `panel_pcp_transition`, and the **effective
     event layer** `care_order_results`/`care_order_med` that `measures` reads. Runs AFTER `epicize`, BEFORE `measures`.
     Deterministic (seed) + idempotent. Without it, `measures` won't find `care_order_*`.
   - `bundle run ssd_cohort -t ect` → seeded synthesis of the SSD behavioral-health cohort (ADR-0017): SMI dx
     (F20/F25/F31) + antipsychotic dispensing (RxNorm SCD that subsumes to an ingredient via `rxnorm_closure`,
     like SPD) + emergent glucose/HbA1c screening; pre-existing-DM exclusion is real diabetes-cohort overlap.
     Writes `care_ssd_cohort`, which `measures` reads to build `gold_adherence_ssd`. Runs AFTER `epicize`,
     BEFORE `measures`; independent of `care_behavior` (reads bronze only). Needs `setup` first (antipsychotic
     SCDs live in `rxnorm_hier.csv` → `rxnorm_closure`). Deterministic (seed) + idempotent.
   - ⚠️ **Reflow ordering:** if any `src/terminology/*.csv` changed, rerun **`setup` first** (reloads `icd10_hier`
     etc. and rebuilds the closures) before `epicize → measures → semantic`. A closure built before a new node
     was added won't subsume it (e.g. neuropathy E11.4 was missed until `setup` reran).
   - `bundle run measures -t ect` → Lakeflow pipeline: `silver_*` + `gold_adherence_{gsd,ked,bpd,spd,eed,mad,ssd}` + `gold_protocol_adherence`.
   - `bundle run semantic -t ect` → `apply_comments` (column comments) → `apply_metric_views` (8 metric views, incl. `ssd_compliance`). Ontology fuel; must run after `measures`.
     ⚠️ After this schema (`care_protocol_semantic`) is first created, the next `bundle deploy` validates the Genie
     space against these views, so deploy once to upload, run `semantic` to create the views, then deploy again.
   - `bundle run seed_query_history -t ect` → runs ~27 analyst queries on the warehouse → `system.query.history` (ontology usage signal). After `semantic`; safe to re-run / schedule.

## Terminology — NO license wait (ADR-0002)
- No SNOMED/UMLS/VSAC. Curated LOINC + ICD-10-CM + RxNorm subsets **vendored in `src/terminology/`** (no Drive) + hand-curated demo value sets.

## Ontobricks (A5) — Eli-owned, do NOT automate (ADR-0005)
- ⚙ Eli deploys/configures Ontobricks (UI + `mcp-ontobricks`) with his own instructions; `ontobricks_wh` exists.
- 🤖 The build only supplies the **integration contract**: the Gold + terminology tables the ontology maps
  (R2RML targets), and the MCP tools the benchmark/app call. Capture this when Eli is ready.

## ⏳ Async waits (verify, don't assume)
| Wait | When | Verify by |
|---|---|---|
| Lakebase / Model Serving provisioning | P8/P11 | endpoint/instance READY |
| DLT pipeline first run | P2/P3 | run success; row counts |
| **Genie Ontology extraction** | P7 | Genie One answers **cite** Pages/metric views ("Ontology References") |
| Lakebase BM25 index build | P8 | index status; test query |

## Domains + subdomains (ADR-0008) — scripted, not DAB
- 🤖 Fresh workspace: `python scripts/create_domains.py --profile ECT` — creates governed tag policies +
  `Care Protocol` root domain + 3 subdomains via `databricks tag-policies` + `databricks domains` (Beta).
- 🤖 **On ECT (resolved 2026-10-29):** `python scripts/create_domains.py --profile ECT --root-tag "Clinical Domain"`
  — the account is at its **governed tag-policy cap** (~3074, shared across demos), so new tags can't be minted.
  We reuse the free existing tag **`Clinical Domain`** (chosen by Eli) for the root domain; subdomains are skipped
  (their `X/...` tags can't be created). Created domain: tag_key `Clinical Domain`, id `b624f99f-8903-40db-a1d6-61c11e3336e7`,
  published, carrying our Care Protocol subtitle/description. One domain; structure the detail via Pages.
- ⚙ Section polish (rich domain sections) is **UI-only** — optional.
- Note: the cap is an ECT environmental constraint (like Default Storage, ADR-0001). A workspace not at the
  cap gets the full `Care Protocol` tree from the default script invocation.

## Pages (ADR-0008) — content-as-code + manual bulk-import (no API)
- 🤖 Page source lives in `docs/ontology/pages/*.md` (one per term: domain, synonyms, description, body).
- 🤖 `bundle run stage_pages -t ect` copies the Page sources into the UC Volume
  **`/Volumes/${var.catalog}/care_protocol/ontology_pages`** (14 files) so Genie Code can read them from a
  governed Volume. Re-runnable.
- ⚙ **Genie Code bulk import** (the one irreducible manual step): Discover → Pages → Bulk import → point Genie
  Code at the Volume `/Volumes/<catalog>/care_protocol/ontology_pages` (or the `docs/ontology/pages/` files) →
  review the proposed Pages → assign to the **Clinical Domain** domain → publish. Pages require a domain
  first (run the domains script above). Pages are Beta.

## AI/BI dashboard + Genie Agent (bundle-managed)
- 🤖 `resources/dashboards.yml` + `hedis_quality.lvdash.json` and `resources/genie_spaces.yml` +
  `care_protocol.geniespace.json` deploy with `bundle deploy` (no separate run). The Genie agent resolves its
  warehouse via the `warehouse_id` name lookup.
- ⚙ **Publish the dashboard** (makes the `/published` URL live; redeploy updates only the draft):
  `databricks lakeview publish <dashboard_id> --warehouse-id <wh> --profile ECT`.

## Care-protocol PDF (lineage anchor; BENCHMARK_CHARTER.md)
- 🤖 Source: `docs/care_protocol/html/diabetes_care_protocol.html` (version-controlled). Ground-truth PDF
  questions: `docs/care_protocol/pdf_eval_questions.json`.
- 🤖 `bundle run stage_care_protocol -t ect` renders it to PDF in
  **`/Volumes/${var.catalog}/care_protocol/documents/pdf/`** (xhtml2pdf, serverless). Feeds RAG / Pages / graph
  edges and `ai_parse_document`. Re-runnable.

## A4 — Lakebase hybrid retrieval (ADR-0009)
- 🤖 **Create the Autoscaling project** (once; Provisioned is retired — use `postgres`, not `database`):
  `databricks postgres create-project care-protocol --json '{"spec": {"display_name": "Care Protocol Retrieval (A4 Lakebase hybrid)"}}' --profile ECT`
  → production branch, primary endpoint, db `databricks_postgres`. Current endpoint host:
  `ep-spring-paper-d2objaly.database.us-east-1.cloud.databricks.com`.
- 🤖 **Load the retrieval corpus** (one row per Page, tsvector index):
  ```
  EP=projects/care-protocol/branches/production/endpoints/primary
  TOKEN=$(databricks postgres generate-database-credential $EP --profile ECT -o json | python3 -c "import json,sys;print(json.load(sys.stdin)['token'])")
  python scripts/lakebase_corpus.py --src_dir docs/ontology/pages | \
    PGPASSWORD="$TOKEN" psql "host=<endpoint-host> user=eli.swanson@databricks.com dbname=databricks_postgres sslmode=require"
  ```
- 🤖 **Add the semantic half** (pgvector embeddings; after the corpus load):
  `python scripts/lakebase_embed.py --src_dir docs/ontology/pages --profile ECT | PGPASSWORD="$TOKEN" psql "..."`
- 🤖 **Retrieve:** `src/retrieval/a4_lakebase.py` — `search` (lexical ts_rank), `search_semantic` (pgvector
  cosine), `search_hybrid` (RRF fusion). 14 docs embedded (gte-large-en, HNSW cosine index). Needs `psycopg`.

## A4 Lakebase RAG — document corpus + Lakebase Search + document-level RLS (ADR-0014)
Upgrades A4 from a Pages-row corpus to a real care-protocol **document** corpus with document-level
authorization. Everything below is **committed code**; the external applies are confirm-gated (sync-in /
confirm-writes). All steps re-run on a fresh workspace.

- ⚙ **Capability gate (verify first, don't assume):** confirm the `care-protocol` Lakebase project supports
  **Lakebase Search**. If yes, continue with the preferred path; if not, use the pgvector + full-text
  **fallback** (uncomment the fallback lines in `src/retrieval/lakebase/schema.sql`, set `search_ext=False`
  on `A4RagRetriever`).
- ⚙⏳ **Enable Lakebase Search (IRREVERSIBLE; restarts all computes, drops active connections):** Lakebase
  project → **Settings → Enable Lakebase Search**. One-time, confirmed. (No-op if already enabled.)
- 🤖 **Apply the serving schema** (extensions, tables, indexes, roles, RLS policies):
  ```
  EP=projects/care-protocol/branches/production/endpoints/primary
  TOKEN=$(databricks postgres generate-database-credential $EP --profile ECT -o json | python3 -c "import json,sys;print(json.load(sys.stdin)['token'])")
  PGPASSWORD="$TOKEN" psql "host=<host> user=<you> dbname=databricks_postgres sslmode=require" -f src/retrieval/lakebase/schema.sql
  ```
- 🤖 **Build + load the corpus** (deterministic; `--emit_demo_roles` seeds the two demo identities so the RLS
  test can `SET ROLE`):
  ```
  python3 -I scripts/lakebase_rag_corpus.py --emit_demo_roles | \
    PGPASSWORD="$TOKEN" psql "host=<host> user=<you> dbname=databricks_postgres sslmode=require"
  ```
- 🤖 **Embed** the chunks (gte-large-en, 1024-dim) and build the ANN index — reuse the `scripts/lakebase_embed.py`
  pattern pointed at `rag.chunks` (semantic/hybrid retrieval and `lakebase_ann.prefilter` need embeddings;
  lexical/BM25 works without). ⏳ Build the **BM25** index *after* load (corpus stats at build time); after a
  large reload, `REINDEX INDEX CONCURRENTLY rag.chunks_body_bm25`.
- 🔒 **Verify authorization** (the `+perm` tracer, design doc §13). Needs the Postgres client:
  `pip install -e '.[lakebase]'` (psycopg). Host is the `primary` endpoint
  (`ep-...database.us-east-1.cloud.databricks.com` from `databricks postgres list-endpoints`):
  ```
  export LAKEBASE_HOST=<host> LAKEBASE_USER="<you>" DATABRICKS_CONFIG_PROFILE=ECT
  python3 -I tests/test_rag_rls.py    # analyst cannot see LETTER-EYE-TRC-0003; clinician can
  ```
  The RLS policy consults the ACL/membership tables through the `SECURITY DEFINER` function
  `rag.acl_allows()` (ADR-0016) — the reader has `EXECUTE` on it but no direct SELECT on those tables.
- Deterministic structure test (no workspace): `python3 -I tests/test_rag_corpus_build.py`.

## Weekly Protocol Watch (story hook: "nobody asked; Genie noticed")
Two mutually-reinforcing pieces. The **Genie One scheduled task** is the demo front door (the actual
"A Monday with Genie" watch); the **job** pre-computes an auditable findings table so the scheduled task
answers fast and grounded, and leaves a lineage record Genie One can reason over.

- 🤖 **Findings job (code path, bundle-managed):** `bundle run protocol_watch -t ect` →
  `src/watch/protocol_watch.py` scans `gold_protocol_adherence` by **CLINIC × trailing-3-month window vs each
  clinic's OWN prior baseline** (detects a *change*, not merely a low performer) and appends to
  **`${var.catalog}.care_protocol.protocol_watch_findings`**. Serious, not a toy threshold: right-censoring
  aware (a window is scored only once its 90-day follow-up is fully observed), small-N gated. On the current
  data it fires **HIGH on CLINIC-08 (2025-09)** — the clinic with the mid-year PCP handoff (own prior 78% →
  47%), which is **masked in the global/annual view**. Append-only — each run is an as-of snapshot (the watch
  log). Re-runnable. Schedule is **PAUSED** in `resources/jobs.yml` (weekly, Mon 07:00 PT); unpause to run unattended.
  - ⚠️ No external notification recipient is wired. If you want the job itself to email/Slack, that is an
    external write — tell me the destination and I'll add a SQL Alert or job notification (DAB), confirmed first.
- ⚙ **Genie One scheduled task (the irreducible manual step — no API, like Pages bulk import):**
  1. Open **Genie One → New chat**. In the sidebar click **Schedules → the drop-down next to `+ Create in chat` → Create manually** (or just type the request in natural language and let chat create it).
  2. Fill the dialog:
     - **Title:** `Weekly Protocol Watch`
     - **Instructions:** *"Check `eli_test_classic_catalog.care_protocol.protocol_watch_findings` for the latest run (max `as_of`). If there are `STEP_DRIFT` rows, summarize each: the month, the adherence rate vs baseline, the severity, and the narrative — ranked by `delta` (worst first). If the only row is `NO_DRIFT`, say the protocol step held steady this week. Then, for the worst drift month, use `protocol_adherence_metrics` and the diabetes care-protocol PDF to explain which step likely slipped and cite your sources."*
     - **Connections:** none required (all data is in UC). Add the care-protocol document source if you want the PDF cited.
     - **Schedule:** Weekly, **Monday 07:00**; **Timezone:** your local.
  3. Click **Create**, then **Run now** to preview the exact email. Each run posts to a chat thread and
     emails the task owner (you) the results + a PDF attachment. Pause/resume/edit/delete from **Schedules**.
  - Note: delivery to recipients beyond the owner needs a workspace **notification destination** (admin
    setup) or the email tool/connector — same gating as dashboard subscriptions.
- The two line up: the job writes `protocol_watch_findings`; the scheduled task reads it. Faster + auditable
  than asking Genie One to recompute drift from raw rows every Monday.

## Genie Ontology seeding (P7 / §7a)
- Build Pages + metric views + Genie Agents + dashboards (over-build — see roadmap §7a), assign Domains,
  certify. Run the query-history seeding job on a schedule. Trigger early; build other arms while it extracts.
