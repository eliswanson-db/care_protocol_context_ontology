# RUNBOOK — manual (⚙) and async-wait (⏳) steps

Ordered operational steps that are **not** automated by the bundle. Keep this current as phases land.

## DMVM bring-up — ontology-ON arm (ADR-0018)
Goal: make **DMVM** the high-snippet-density, Genie-Ontology-**ON** workspace so A1-on can be compared against
A1-off on ECT, both over the **one shared catalog** `eli_test_classic_catalog`. The original problem — "not
enough snippets on the new workspace" — is because a fresh workspace has **none of the workspace-local snippet
sources** yet (no dashboards, no Genie agents, no query history, no published Pages); only the shared catalog
metadata is visible. This section populates all of them.

**Already shared — no action (verified 2026-11-01):** all UC tables, metric views + comments; the Pages and
source-document **volumes**; the **`Clinical Domain`** domain (same id on both). DMVM needs **no data rebuild and
no domain creation.**

**Workspace-local — deploy/run on DMVM (🤖 reproducible):**
1. `databricks bundle validate -t dmvm --profile DMVM` → `databricks bundle deploy -t dmvm --profile DMVM`.
   Deploys the 4 Genie agents + 4 AI/BI dashboards + all job definitions (unchanged — shared catalog, so no
   identifier find/replace; `warehouse_id` name lookup resolves on DMVM).
2. **Do NOT re-run the data pipelines** (`generate_synthea`, `epicize`, `care_behavior`, `ssd_cohort`,
   `measures`, `semantic`, `stage_care_protocol`) — their outputs are in the shared catalog already. Running
   them on DMVM would recompute/overwrite shared data for no benefit.
3. `databricks bundle run seed_query_history -t dmvm --profile DMVM` — **DMVM-local** query history (the usage
   signal is per-workspace; this is a primary inferred-snippet source).
4. `python scripts/smoke_test_snippets.py --profile DMVM` — executes every Genie snippet + dashboard dataset
   against DMVM's warehouse (validates the deploy **and** adds more query history).
5. `databricks lakeview publish <dashboard_id> --warehouse-id <wh> --profile DMVM` for each dashboard.
6. `stage_pages` / `stage_source_documents` only needed if the shared volume is stale (it was, pre-2026-11-01);
   one run from either profile refreshes the shared volume for both.

**Manual / admin (⚙):**
7. ⚙ **No Genie Ontology toggle exists — it is always on.** Inferred snippets are only *fetched* once a
   workspace holds **> ~1,000 snippets** (measured 2026-11-01: ECT ≈ 200 = sub-threshold baseline; DMVM ≈ 1,100 =
   above = treatment). So the lever is **snippet count**, not a switch: keep minting snippets on DMVM (Pages,
   dashboards, Genie agents, query-history, analytics notebooks). Nothing to toggle on ECT — its baseline-ness is
   just its sub-threshold count.
8. ⚙ **Import Pages on DMVM** via Genie Code using `docs/ontology/PAGES_IMPORT_PROMPT.md` (16 Pages → Clinical
   Domain). Published Pages are per-workspace, so this is required on DMVM even though the sources are shared.
9. ⚙⏳ **Extraction is slow — roughly DAILY, sometimes hours, NOT minutes.** Don't expect snippets right after
   import. Once surfaced, verify Genie One on DMVM **cites** Pages/metric views under "Ontology References", and
   record snippet density in `capability-matrix.md`.

## P0 — setup
1. ⚙ **Auth** — `databricks auth login https://fevm-eli-test-classic.cloud.databricks.com --profile ECT` (already valid).
2. ⚙ **Capability gate** — confirm on ECT and record in `capability-matrix.md`: **Genie Ontology** (always on;
   inferred snippets gated by workspace snippet count > ~1,000 — ADR-0018), **Apps enabled**, MLflow 3, Lakebase,
   Model Serving + embedding endpoint, Genie Agent API.
3. 🤖 **Schemas + volume are declarative** (the `&shared_uc` block in `databricks.yml`, owned by **dev + ect
   only** — ADR-0019) — created by `databricks bundle deploy -t ect --profile ECT`. The catalog pre-exists
   (ECT Default Storage blocks SQL catalog creation — ADR-0001). The `dmvm` target intentionally does **not**
   manage these shared UC objects.
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
  **`/Volumes/${var.catalog}/care_protocol/ontology_pages`** (**16 Page sources + README = 17 files**) so Genie
  Code can read them from a governed Volume. Re-runnable (overwrites). The volume is in the **shared catalog**,
  so one run serves both ECT and DMVM. (A 2026-10-30 staging was stale — missing `ssd.md` and
  `document-access-scope.md`, with measure links pointing at `care_protocol` not `care_protocol_semantic`;
  re-staging from source fixes all of it.)
- ⚙ **Genie Code bulk import** (the one irreducible manual step): use the ready prompt in
  **`docs/ontology/PAGES_IMPORT_PROMPT.md`** — Discover → Pages → Bulk import → Genie Code → paste the prompt →
  it proposes **one Page per `.md`, skipping README → 16 Pages** → review the table → assign to **Clinical
  Domain** → publish. Pages require the domain first (shared, already present on both workspaces). Pages are Beta.
  Re-run per workspace where Genie Ontology is ON (the published-Page set is per-workspace even though the
  domain/catalog/volume are shared).

## Source-document volume — build MORE Pages via bulk import (second volume)
Purpose: a staging ground of **Pages-ready SOURCE material** (facts-only mined extracts + the synthesized
corpus), kept separate from the finished `ontology_pages`, so you can generate additional Pages with Genie
Code without mixing sources and outputs.
- 🤖 `bundle run stage_source_documents -t ect` copies the 9 version-controlled facts-only Markdown files
  (`docs/care_protocol/source_extracts/*.md` + `docs/care_protocol/corpus/*.md`) into the second volume
  **`/Volumes/${var.catalog}/care_protocol/source_documents`** (flat, named `<group>__<file>.md`). Re-runnable.
- ⚙ **Genie Code bulk import** (manual, same as Pages above): Discover → Pages → Bulk import → point at
  `/Volumes/<catalog>/care_protocol/source_documents` → review → assign to the **Clinical Domain** → publish.
- ⚙ **Raw source PDFs (the Oct-30 Downloads) — manual, licensing-gated.** Only their *facts* are in the repo
  (paraphrased, synthetic; ADR-0002/0015). Do **NOT** bulk-upload the proprietary PDFs to a Volume:
    - ❌ Proprietary — do not redistribute: `Diabetes Screening ... Antipsychotic Medications.pdf` (NCQA SSD),
      `HEDIS Quality Measure Toolkit.pdf` (NCQA), `GSD ... Johns Hopkins Medicine.pdf`, and treat
      `coding-spot-diabetes.pdf` / `Diabetes CPM - Adult.pdf` as unknown-license → do not upload.
    - ✅ Public domain — OK to upload if you want the raw lineage anchor:
      `VADOD-Diabetes-CPG_Final_508.pdf`, `2027qrsmeasuretechnicalspecifications508.pdf`. If you choose to:
      `databricks fs cp "<local.pdf>" dbfs:/Volumes/${var.catalog}/care_protocol/source_documents/<name>.pdf --profile ECT`
      (the stage job only clears `*.md`, so uploaded PDFs survive re-runs). Then parse with `ai_parse_document`
      if you want them chunked for RAG (see the A4 sections).

## AI/BI dashboard + Genie Agents (bundle-managed)
- 🤖 `resources/dashboards.yml` + `hedis_quality.lvdash.json` and `resources/genie_spaces.yml` +
  the two space bodies (`care_protocol.geniespace.json` = HEDIS outcomes incl. SSD; `protocol_adherence.geniespace.json`
  = Protocol Step-3 + MAD + protocol-watch) deploy with `bundle deploy` (no separate run). Each Genie agent
  resolves its warehouse via the `warehouse_id` name lookup.
- ✅ **These `*.geniespace.json` bodies are the single source of truth** — edit snippets/examples here and
  `bundle deploy`; do not hand-edit a space in the UI (a redeploy would overwrite it). This is how we keep the
  "certified vs clone" drift Genie One flagged from recurring. To certify, certify the DAB-deployed space.
- ⚠️ **Genie export rule:** `data_sources.tables` and `data_sources.metric_views` in each `.geniespace.json`
  must be **sorted by identifier**, or the deploy fails with `must be sorted by identifier`.
- ✅ **DMVM deploys the agents unchanged (shared catalog).** The `.geniespace.json` identifiers are hardcoded to
  `eli_test_classic_catalog` — and DMVM is in the **same metastore and shares that exact catalog** (ADR-0018), so
  **no find/replace is needed**. DMVM also has a "Serverless Starter Warehouse", so the `warehouse_id` name lookup
  resolves there too. Just `databricks bundle deploy -t dmvm --profile DMVM`. (This supersedes the earlier
  "hardcoded identifiers → find/replace for DMVM" note, which assumed separate catalogs.)
- ⚙ **Publish the dashboard** (makes the `/published` URL live; redeploy updates only the draft):
  `databricks lakeview publish <dashboard_id> --warehouse-id <wh> --profile ECT`.
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
- 🤖 **Embed** the chunks (gte-large-en, 1024-dim) and rebuild the ANN index — `scripts/lakebase_embed_chunks.py`
  reads `rag.chunks.content`, embeds via the governed endpoint, writes `embedding` back (idempotent: only NULLs
  unless `--all`), then `REINDEX CONCURRENTLY` the ANN index with `--reindex`. `--dry_run` embeds + reports, writes
  nothing. (Semantic/hybrid retrieval and `lakebase_ann.prefilter` need embeddings; lexical/BM25 works without.)
  ⏳ Build the **BM25** index *after* load (corpus stats at build time); after a large reload,
  `REINDEX INDEX CONCURRENTLY rag.chunks_body_bm25`.
- 🔒 **Verify authorization** (the `+perm` tracer, design doc §13). Needs the Postgres client:
  `pip install -e '.[lakebase]'` (psycopg). Host is the `primary` endpoint
  (`ep-...database.us-east-1.cloud.databricks.com` from `databricks postgres get-endpoint <EP>`):
  ```
  export LAKEBASE_HOST=<host> LAKEBASE_USER="<you>" DATABRICKS_CONFIG_PROFILE=ECT
  python3 -I tests/test_rag_rls.py    # analyst cannot see LETTER-EYE-TRC-0003; clinician can
  ```
- ✅ **DMVM parity (2026-11-01):** the same project exists on DMVM (endpoint
  `ep-divine-wildflower-d2l62zpy.database.us-east-1.cloud.databricks.com`, profile `DMVM`), Lakebase Search
  enabled, `schema.sql` + corpus loaded → **7 docs / 36 chunks / 13 ACLs / 3 members** (identical to ECT), RLS
  **4/4** green. Each workspace has its OWN Lakebase project (Postgres is per-workspace, unlike the shared UC
  catalog); re-run these steps per workspace with that workspace's host + `--profile`.
- ✅ **Embeddings populated — A4 is HYBRID (2026-11-02):** `scripts/lakebase_embed_chunks.py --reindex` embedded
  all **36/36 chunks** (gte-large-en, 1024-dim) and rebuilt `chunks_embedding_ann` on **both** ECT and DMVM in
  lockstep. `SELECT count(embedding) FROM rag.chunks` = 36 on both. Hybrid (RRF of BM25 + pgvector/ANN) and
  `lakebase_ann.prefilter` are live. The P13 app's A4 panel auto-detects the embedded count and serves hybrid.
  Re-run the script per workspace after any corpus reload (idempotent on NULLs; `--all` to re-embed everything).
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

## Databricks App (P13) — deploy + post-deploy grants
- 🤖 **Bundle-managed** (`resources/apps.yml`, `src/app/`). Build the SPA first, then deploy + start:
  ```
  (cd src/app/frontend && npm run build)         # dist is force-synced via databricks.yml sync.include
  databricks bundle deploy -t dmvm --profile DMVM
  databricks bundle run   care_protocol_app -t dmvm --profile DMVM   # deploys code to the app + starts it
  ```
  URL: `databricks apps get care-protocol-context-dmvm --profile DMVM` → `.url`. It's behind workspace OAuth.
- ⚙ **A Databricks App is a STATIC deploy** — it does not track local edits/commits; re-run the two commands
  above to update it. Data is live (warehouse queries per request); the build/code is frozen at deploy time.
- 🔒 **Post-deploy grants to the app service principal** (created at deploy; find it via `apps get` →
  `service_principal_client_id`, here `2cea0a9c-5125-4205-957e-6e864d7217dd`). Re-run per fresh deploy:
  ```
  -- read-only UC access for the warehouse-backed tabs
  GRANT USE CATALOG ON CATALOG eli_test_classic_catalog TO `<sp_client_id>`;
  GRANT USE SCHEMA, SELECT ON SCHEMA eli_test_classic_catalog.care_protocol            TO `<sp_client_id>`;
  GRANT USE SCHEMA, SELECT ON SCHEMA eli_test_classic_catalog.care_protocol_semantic   TO `<sp_client_id>`;
  GRANT USE SCHEMA, SELECT ON SCHEMA eli_test_classic_catalog.care_protocol_terminology TO `<sp_client_id>`;
  ```
  ```
  # Genie hop (deployed): the app SP calls the governed Genie SPACE (A2 Agent) via the SDK — grant CAN_RUN:
  PATCH /api/2.0/permissions/genie/<CARE_GENIE_SPACE_ID>
      {"access_control_list":[{"service_principal_name":"<sp_client_id>","permission_level":"CAN_RUN"}]}
  ```
- **Dual-mode AI** (`IS_DATABRICKS_APP`): local uses **Genie One (A1)** via the CLI (exposes the inferred-
  snippet signal); deployed uses the **Genie space (A2)** via SDK (no inferred signal — labeled `surface`).
- ✅ **A4 RAG remote is WIRED (2026-11-02):** the app SP is a normal authorized reader (RLS stays ON, no
  bypass). One-time per deploy: (1) provision the SP as a Lakebase Postgres role —
  `databricks postgres create-role projects/care-protocol/branches/production --role-id care-protocol-app
  --json '{"spec":{"identity_type":"SERVICE_PRINCIPAL","postgres_role":"<SP_CLIENT_ID>","auth_method":"LAKEBASE_OAUTH_V1"}}'`;
  (2) `python3 -I scripts/lakebase_grant_app_reader.py --sp <SP_CLIENT_ID> --profile DMVM` grants `rag_reader`
  + puts the SP in group `care_app_service` + ALLOW-READs that group on all docs (acl_allows verified true 7/7).
  The app connects as `DATABRICKS_CLIENT_ID` (= the postgres_role) so `current_user` matches the ACL. Verified
  the SP sees all 7 docs / 36 chunks; embeddings present → hybrid.

## Genie Ontology seeding (P7 / §7a)
- Build Pages + metric views + Genie Agents + dashboards (over-build — see roadmap §7a), assign Domains,
  certify. Run the query-history seeding job on a schedule. Trigger early; build other arms while it extracts.


## Clinical Study Lab (life_sciences_clinical): manual steps (⚙) and waits (⏳)

Automated (bundle, ECT only): `ls_bootstrap` (generate data + everything) and `ls_context` (no data regeneration):
standards + rule registry → closures → pipeline → gold oracle check → documents / RAG corpus / Pages staging →
graph views (`clinical_study_graph`) + semantic validation (`clinical_study.dq_semantic_validation_summary`).

1. ⚙ **Ontobricks (Eli, ADR-0005).** Follow `docs/life_sciences/ONTOBRICKS_IMPORT.md`:
   - create a **new** project (not `clinicaldomain`);
   - import `src/ontology/life_sciences/clinical_study.owl.ttl`, then `clinical_study.r2rml.ttl`;
   - set source scope to `eli_test_classic_catalog.clinical_study_graph` only;
   - publish, then send Claude the triplestore table name for verification.
   ⏳ Publishing builds the triplestore; check that it completed before verifying.
2. ⚙ **Pages.** Genie Code bulk import with `docs/life_sciences/PAGES_IMPORT_PROMPT.md` (15 Pages → `Clinical
   Domain`). ⏳ Genie extracts new snippets on a roughly **daily** cadence; Genie One evaluation waits for it.
3. ⚙ **Domain (blocked, no action now).** The account is at its 1,000-domain cap, so `Clinical Study Lab` can't be
   created. Its governed tags exist. If a slot frees up: `python scripts/create_domains.py --profile ECT --tree
   life_sciences`.
