# Plan — one spine, five lenses (consistent trace + benchmark)

**Owner thread:** Eli + Claude · started 2026-11-03
**Serves:** the Kaiser Permanente "A Monday with Genie" deck (`~/Downloads/index (2).html`) — the business case.
**Framing rule:** this is demo engineering. No promo-signal / WLB / project-management framing (see memory `no-project-management-framing`).

## The goal (4 things, one design)

1. Everything frames to the KP deck (diabetes / Star Ratings; hero concept = **Step 3: intensify + recheck A1c within 90 days of a result >9%**).
2. Explain Genie Ontology + other Databricks graph/semantic options by benchmarking **FIVE retrieval approaches consistently**: `metric_view · closure · genie_ontology · rag · graph(ontobricks)`.
3. **Trace journeys**: each hero concept/patient realized in every layer — `PDF/raw → bronze → silver → gold → semantic (metric view · Genie agent · Page) → retrieval (metric view · closure · RAG · Genie Ontology · graph)`. Same spine every hero.
4. **Benchmark**: what each approach gets **right / wrong** (`docs/benchmark/ground_truth.yaml` 9 classes → Retrieval Arena).

**Unifying idea:** one hero → identical medallion trace → the *same* end-question fanned to all five approaches → each scored right/wrong with one shared rubric. This ties goal 3 (trace) and goal 4 (benchmark) into one apples-to-apples exhibit.

**Scope decision (2026-11-03):** park the `a1_off`/`a1_on` two-workspace split (unverified Genie-Ontology *variant*; collapse Genie Ontology to one arm). Keep chasing the live Ontobricks graph arm. Do not cut any of the five.

## Hero set (pinned to the deck) — TASK A

Each must resolve at **every** layer (bronze → silver → closure → cohort → gold → metric → semantic/page → each of the 5 retrieval lenses).

Hero clinic = **CLINIC-08** ("Bayview"): HIGH Step-3 drift (−31pp, Sep 2025) + the mid-year PCP departure+locum (2025-07-15, 150d recovery). H1/H2/H3 all live there.

| Hero | patient_id | Deck anchor | Benchmark role | Resolves end-to-end? |
|---|---|---|---|---|
| H1 Step-3 drift | `639ccd3e-c295-f093-0fa7-697eac8ef74e` (CLINIC-08, PANEL-21, Step-3 NOT_MET) | the Monday headline | class 9 operational/temporal | ✅ all layers incl. step3 |
| H2 E11.21 nephropathy | `01ee58df-f106-7b32-0098-c8d818248a70` (CLINIC-08, GSD NOT_MET "no A1c test", age 53) | ontology matches encounter→step | class 2 subsumption (closure == graph) | ✅ bronze→gold, 2 closure hits |
| H3 Statin / SPD gap | `003cd897-f3af-4e97-eeef-faca23acd3d1` (CLINIC-08, SPD NOT_MET, age 68; also E11.21 + GSD MET) | Statin Use measure | class 5 cross-vocab RxNorm (closure necessary) | ✅ bronze→gold |
| H4 Cardiorenal | `06fbf629-094d-aecf-08ca-4e1bea7b2e35` (DM+CKD(N18)+HF(I50), GSD+KED eligible) | kidney + new GLP-1/SGLT2 guideline | class 8 graph-native (path/defined-class) | ✅ bronze→gold (GSD+KED) |

> **⚠ FLAG — deck vs implementation threshold mismatch.** The deck narrates Step-3 as "recheck within 90 days of a result **above 9%**." The implemented `gold_protocol_adherence` triggers at the **7% A1c target** (`trigger_a1c` range 7.0–10.0; only 4 of 392 rows are >9). H1 (`639ccd3e`) has `trigger_a1c` 7.6. **Decision needed:** either raise the implementation trigger to >9 to match the deck's line, or re-narrate the deck/demo as "above the 7% target." Does not block the build; affects what we say on stage.

## Build — the consistent five-card row — TASK B

**Backend** `GET /api/patient/{id}/retrieval` — the three *deterministic* lenses for the hero, uniform shape
`{id,label,resolves_at,question,answer,provenance,good_at,blind_to,latency_s}`:
- `metric_view` — governed clinic rate row (reuse `get_measure_rate` logic / `gsd_compliance_metrics`).
- `closure` — subsumption rows that put this patient in the cohort (reuse `subsumption_expand` / `icd10_closure`).
- `graph` — the property path the graph would traverse for this patient, from governed edge tables (`protocol_edges` + closures); labeled "modeled; Ontobricks import = `src/ontology`". (Live Ontobricks = separate chase.)
- `genie_ontology`, `rag` — descriptors only here; filled on demand by existing `/genie` and `/rag` endpoints (slow live calls stay lazy).

**Frontend** — collapse Tracer sections 02/04/05 into ONE consistent **five-card row** (evolve `RetrievalModes.tsx`): all five cards same shape; metric_view/closure/graph populate on patient-select; genie_ontology/rag show "Ask ▸" then fill. Each card shows the native answer + provenance + a one-line good-at / blind-to (the benchmark dimension).

## Task list / status

- [x] A1. Auth ECT; pin H1–H4 patient_ids via SQL. (ids in the hero table above)
- [x] A2. Layer-resolution check per hero (bronze→…→gold); all four resolve. **Flagged the deck-vs-impl A1c threshold mismatch.**
- [x] A3. Retrieval-source check: closure hits > 0 for all; `protocol_edges` path present for the graph lens.
- [x] B1. Backend `GET /api/patient/{id}/retrieval` (metric_view + closure + graph lenses) — `routes/retrieval.py`, registered in `app.py`; smoke-tested + HTTP-tested (200; 404 guard) on H2/H3/H4.
- [x] B2. Frontend five-card consistent row — `components/RetrievalRow.tsx`; Genie/RAG folded inline (lazy "Ask ▸"); `TracerJourney` rewired (old sections 02/04/05 collapsed into one row); claim IDs aligned to the shared vocab; `vite build` clean.
- [x] B3. Verified in the live browser (devloop at :5180 → :8011). Fixed a **stale-backend bug** (a pre-session uvicorn on 8011 without the `/retrieval` route made the proxy 404 → SPA-HTML fallback → empty graph card). Kill the port before starting.
- [x] B6. **Polish pass** (Eli review): live Genie/RAG cards verified (RAG is now **hybrid** — embeddings backfilled — returning cited passages; Genie returns a correct cited answer); fixed Genie card rendering **markdown as raw text** → a small no-dep markdown renderer (headings/bold/links, drops embedded query-table dumps) in `RetrievalRow`; **light-mode pass** (tokens swap correctly, tier/lens/status colors read on white); Gold measure chip now uses **status color** (red NOT_MET / green MET), not the gold tier; consistent **demo-grade headers + legibility** across Benchmark/Drift/Ontology, and the Benchmark **ablation-ladder bars carry the per-approach identity colors**. Build clean, no console errors.
- [x] B5. **Demo-flow pass** (Eli review): medallion regrouped into **phase columns** (Source → Bronze → Silver → Gold → Serving; multiple sub-steps in a phase stack vertically, cards hug content); cut per-card description text (moves to the click-in `NodeDetail`); **collapsible sections** (`TracerJourney` `Section`) default **01 open, 02/03 collapsed** for a reveal-as-you-narrate flow; **collapsible left sidebar** (`TracerPicker` → thin rail). Build clean, no console errors.
- [x] B4. **Design pass for demo** (attractive, large text, viz best-practices): design tokens + type scale + brighter ink (`index.css`); medallion rebuilt as a single horizontal **journey band with bronze/silver/gold tier identity** (`FlowDiagram.tsx`); **hero patient banner** + larger section headers (`TracerJourney.tsx`); five-card row gets **per-approach categorical color identity** + a **stat tile** (big % + bar) for the metric-view rate + consistent heights (`RetrievalRow.tsx`); larger modeled-answer (`AnswerPanel.tsx`). Validated categorical slots from the dataviz skill; no console errors; `vite build` clean.
- [x] B7. **Benchmark restructure to the five approaches** (Eli, devloop): the matrix CSV (`src/app/server/benchmark_data/` + `docs/benchmark/`) is now the single source of truth for all five — renamed `metric_view`/`closure`, collapsed Genie off/on into one authoritative `genie_ontology` column (the ON/OFF experiment stays as the separate observational section), and added `rag` + `graph` columns derived from the ground-truth hypotheses (one shared rubric). Backend `ARMS` → the five; `capability_map` simplified (dropped the a1_on derivation). **Benchmark Scorecard** ladder + matrix now render 5 approaches with per-approach identity colors (metric 6/20 · closure 15/17 · Genie 17/20 · RAG 5/20 · graph 15/15). **Retrieval Arena** rebuilt around the five (verdict cards + the Genie recorded-run ECT/DMVM detail). Shared `GenieMarkdown` renderer used in both the Tracer card and the Arena. Build clean, no console errors.
- [x] (DONE) **Live Ontobricks arm**: the app lens AND the Benchmark `graph` column are now live. The app traverses the triplestore per-patient (`routes/ontobricks.py`); the Benchmark column is **live-measured** (scored eval, not hypothesis) — see round 4 below.
- [ ] (polish) Graph lens: order edges so cross-vocab `recommendedFor`/`contraindicatedWith` (the lift) surface above `hasThreshold`.

## Shared lens-ID vocabulary (now consistent across tracer + row)
`metric_view · closure · genie_ontology · rag · graph`  — used by `/retrieval`, `RetrievalRow`, and tracer claim `modes`. (The Arena still uses `m0_metric_view`/`closure_sql` — unify in the later Arena task.)

## Review changes (2026-11-03, local devloop — not yet redeployed)

- **Retrieval Arena** detail is now **Genie + Ontology (left) vs Ontobricks graph (right)**; dropped the A1 off/on two-up. Both sections (`Five approaches`, `Genie vs graph`) are collapsible. Ontobricks panel references the **`clinicaldomain`** ontology, labeled modeled (`protocol_edges` + closures), live traversal flagged as next.
- **`patientcare2` → `clinicaldomain`** in the `infer_defined_class` note (`capability_matrix.csv`, bundled + docs) — shows in the Arena + Benchmark matrix. ⚠ The recorded Genie answer snapshot for that question (`a1_runs/A1_off_*.json`) still says "patientcare2" (a dated recording from when that was the only domain) — left as-is; scrub or re-record on request.
- **Tracer build steps** each gained a one-line detail (`DETAIL` map in `FlowDiagram`).
- **Collapsible sections** added via a shared `components/Collapsible.tsx` — Benchmark (ladder/matrix open, ON/OFF collapsed) and Arena. Tracer already had them.
- **Removed Drift Lab + Ontology Explorer** from the nav/render (`App.tsx`); the tab files remain on disk, unreferenced. Build clean, no console errors.

## Review changes — round 2 (2026-11-03, local devloop — not yet redeployed)

- **Medallion rephased** (`FlowDiagram` + `tracer.py` new `ontobricks` stage): metric view moved into **Gold · serving** (it's the governed serving view over gold); the final **Ontology** phase now surfaces **Genie Ontology + Ontobricks graph** (clinicaldomain). Gold card note says the verdict is **persisted**.
- **`NOT_MET` confirmed persisted in gold** — `gold_adherence_gsd.status` (1,971 MET / 471 NOT_MET MY2025), written by the deterministic measure engine, read by the agent. Correctly stays in gold.
- **Arena + Benchmark now show the actual questions** — the `capability_matrix.csv` `question` column was replaced with the full natural-language questions from `ground_truth.yaml` (bundled + docs).
- **Eval is NOT 1:1 (documented honestly):** Genie column = real executed + recorded + hand-verified run; Ontobricks column = designed-capability from hypotheses — `src/benchmark/retrieval_eval/providers.py` has an Ontobricks provider that **refuses the toy `patientcare2` sample and degrades to "not published yet" until the real `clinicaldomain` triplestore lands**. Making it 1:1 = publish the clinicaldomain triplestore so the provider binds and runs under the same rubric (the "live Ontobricks arm" open item).

## Review changes — round 3: LIVE Ontobricks (2026-11-03, local devloop — not yet redeployed)

- **Corrected a wrong claim:** Ontobricks + clinicaldomain ARE published/live (`eswanson_demo.ontobricks.triplestore_clinicaldomain_v2_graph`, ~55M triples). I'd been repeating a stale `providers.py` comment. See memory `ontobricks-live`.
- **The app now QUERIES Ontobricks live** — `routes/ontobricks.py`: `/patient/{id}/ontobricks` (patient edges + guideline edges) and `/ontobricks/care_edges`. The Tracer graph lens (now a lazy "Query the graph ▸" live card) and the Arena Ontobricks panel both traverse the real triplestore (~0.8–3s), showing real triples incl. the `DRUGCLASS-STATIN recommendedFor Measure/SPD` hero path. No more "modeled from `protocol_edges`."
- **Source step shows a real excerpt** — `tracer.py` protocol stage now carries the actual CP-DM-2025.1 §2 GSD text (document / section / excerpt / eligible-population), not a hand-written dict.
- **`NOT_MET` persisted — confirmed and labeled:** it's `gold_adherence_gsd.status`/`numerator_flag`, computed by the measure engine and persisted; the GSD metric view just aggregates those flags (`COUNT(1) FILTER (WHERE numerator_flag)`). The user's point stands: the compliance *logic* lives in the pipeline, not computed live in the semantic layer. Not re-architected this round — that's making `gold_adherence_gsd` a computed view / pushing numerator logic into the metric-view source.
- **1:1 status:** the APP is now live-vs-live (Genie recorded/live vs Ontobricks live query). The **Benchmark `graph` column is still hypothesis-derived** — running `run_retrieval_eval.py`'s ontobricks provider against v2 and feeding real per-question verdicts is the remaining step for a scored 1:1.

## Review changes — round 4: SCORED graph column (2026-11-03, local devloop — not yet redeployed)

- **The Benchmark `graph` column is now live-measured, not hypothesis.** The eval harness's `ontobricks` provider was rebuilt to do **entity-linked subgraph retrieval** (mirrors `routes/ontobricks.py`: link question terms → IRI nodes via a synonym lexicon, return their typed 1-hop neighbourhood) instead of a blind term-LIKE dump. Then `run_retrieval_eval.py` (9 Qs × 5 arms) + `scripts/score_graph_remaining.py` (the other graph-claimed Qs, ontobricks-only) scored every graph cell against live `clinicaldomain_v2` with the same `is_correct` judge as the other arms. Full results: `docs/benchmark/GRAPH_EVAL_RESULTS.md` (+ `retrieval_eval.json`, `retrieval_eval_graph_remaining.json`).
- **Measured rollup: graph reached 5 / applicable 15** (was hypothesis 15/15). Reached = the two class-7 **definitions** (`contraindicatedWhen eGFR_LT_30`, `BPD hasThreshold`), the class-8 **rationale path** (the ONLY arm to reach it), `med_is_statin`, and the class-8 **correct refusal** of the undefined class. Not_reached = every aggregate **count** (classes 2/3/4/6), **vintage** (5), and **ops** (9) question.
- **The finding (demo thesis, Eli-approved framing = "measured as-is + caveat"):** the graph's lift **as an LLM-context source** is typed, cross-vocab edges (definitions + the multi-hop path + the correct refusal), NOT aggregation. **Fairness caveat shipped in the UI:** this scores graph-as-context (apples-to-apples with RAG); `closure_sql` injects a precomputed SQL scalar, so counts favour it — a graph *query* (COUNT traversal) would reach counts too. The caveat box + "live-measured" footnote render under the capability matrix in the Benchmark tab.
- **Bug fixed en route:** `agent.answer` crashed (`'list' object has no attribute 'strip'`) when the Claude serving endpoint returned `content` as a block-list (longer answers → the ontobricks arm); hardened to normalise block-list content to text. The first run's 4 corrupted ontobricks cells were error-misses; the re-run is clean (0 errors).
- CSV updated in both copies (`docs/benchmark/` + `src/app/server/benchmark_data/`); backend reads it per-request (no restart); `vite build` clean; verified in the browser (ladder + matrix + caveat render; no functional console errors).

## Deploy log

- **2026-11-03 — deployed to DMVM.** `databricks bundle deploy -t dmvm --profile DMVM` (45 files synced incl. the built SPA; 24 resources unchanged) + `databricks bundle run care_protocol_app -t dmvm`. App **RUNNING**, deployment SUCCEEDED (`01f1d7d1fad313aeafe7bf6f7f8bddd1`). URL: https://care-protocol-context-dmvm-3464092709171785.aws.databricksapps.com. Strict validate passed; dmvm owns no shared UC (ADR-0019). The deployed app runs as the service principal — Tracer/retrieval/Genie tabs depend on the SP's UC SELECT on `care_protocol*` + the governed Genie space on DMVM (granted in prior deploys); the Benchmark tab reads the bundled CSV (no warehouse).

## Decisions / notes (append as we go)

- 2026-11-03: Genie + RAG already live per-patient; metric_view + closure live inside the medallion spine; graph not yet a per-patient lens. Deterministic MCP tools exist in `src/mcp/care_protocol_tools.py` (reuse, don't re-derive).

## 2026-11-04 — Believable A1c + per-stage tracer retrieval (deployed to DMVM)

- **Calibrated A1c feed** (`care_behavior.py`): raw Synthea A1c was implausible (MY median 4.3%, min 2.3%, ~monthly).
  The effective feed is now quarterly and re-levelled per patient (poor control ≈ modeled 9.3–11.7%, other diabetics
  6.0–8.6%, non-diabetics 5.0–5.8%), keeping each patient's own variation. Step-3 is causally real: a missed follow-up
  has no A1c in the next 90 days (rows removed); a met one has a reading (kept or emitted, below 9%). No synthetic tags.
- **Measures** (`measures.py`): GSD `evidence_value` = actual latest A1c (modeled override removed — gold == silver,
  1971/1971). Step-3 follow-up = ANY A1c within 90 days, across the year boundary.
- **Results:** GSD 0.8071; poor control 282/1971; Step-3 1024 triggers, 48.5% followed. CLINIC-08 trailing-3mo 0.256 vs
  own baseline 0.433 (−17.6 pts, 2× any clinic) while CLINIC-01 is lowest annually (0.412) with ~0 drift. verify_gold
  13/13. Re-pinned op_worst_clinic_annual / op_clinic_drift (matrix + ground_truth.yaml).
- **Tracer Build click-ins** (`routes/stage_detail.py`, `NodeDetail.tsx`): each stage lazily retrieves THIS patient's
  piece (RAG chunk, raw/conformed rows, closure chain, eligibility, evidence row, the metric view's own rule executed on
  the evidence + tags, the Page from the UC volume, live graph path + subClassOf* walk) with the SQL shown.
- **R2RML** status/hasCareGap now derived from evidence (gold has no status column). The Ontobricks graph must be
  republished after any `measures` run, or the graph-vs-live warning fires.
- **Grant:** app SP got `READ VOLUME` on `care_protocol.ontology_pages` (Page panel).
