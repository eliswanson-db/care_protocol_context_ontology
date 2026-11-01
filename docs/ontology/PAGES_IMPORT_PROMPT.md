# Genie Code — Pages bulk-import prompt (reproducible, workspace-agnostic)

The one irreducible manual step (ADR-0008): Pages have no API/CLI/DAB resource, so they are bulk-imported
through the **Genie Code** pane in the Databricks UI. Everything *feeding* the import is code — the Page
sources (`docs/ontology/pages/*.md`), the staging job (`stage_pages`), and the domain — so the import itself
is the only hand step, and this prompt makes it deterministic.

This prompt works on **either workspace** (ECT or DMVM): both are in the same metastore, share the one catalog
`eli_test_classic_catalog`, and share the **same `Clinical Domain`** domain object
(`domain_id b624f99f-8903-40db-a1d6-61c11e3336e7`, metastore-level — not per-workspace). Only the workspace you
run Genie Code in differs.

---

## Prerequisites (run once per catalog — not per workspace; the volume is shared)

1. **Refresh the staging volume so it matches the repo.** The volume is in the shared catalog, so one run
   serves both workspaces:
   ```
   databricks bundle run stage_pages -t ect --profile ECT     # or -t dmvm --profile DMVM — same shared volume
   ```
   After this, `/Volumes/eli_test_classic_catalog/care_protocol/ontology_pages` holds **17 files**:
   16 Page sources + `README.md`. (A stale copy from 2026-10-30 was missing `ssd.md` and
   `document-access-scope.md` and had the measure metric-view links pointing at `care_protocol` instead of
   `care_protocol_semantic`; re-staging overwrites all of that from the version-controlled source, which is
   correct.)
2. **Confirm the domain exists** (it does, on both workspaces — shared): `Clinical Domain`,
   id `b624f99f-8903-40db-a1d6-61c11e3336e7`. Do not create a new domain or subdomains.

---

## Prompt — paste into Genie Code

> **Bulk-import the Care Protocol HEDIS demo Pages into the existing domain `Clinical Domain`**
> (id `b624f99f-8903-40db-a1d6-61c11e3336e7`). Do not create a new domain or any subdomains.
>
> **Source:** `/Volumes/eli_test_classic_catalog/care_protocol/ontology_pages`
>
> **One Page per `.md` file, skipping `README.md` → exactly 16 Pages.**
>
> Each file's YAML front matter is authoritative, and the Markdown body is the Page body — use them verbatim:
> - `name` → Page title (verbatim; do not rename, merge, or split)
> - `synonyms` → synonyms
> - `owner` → owner
> - `related_assets` → linked UC assets
> - body → Page body (verbatim; add no facts not in the file)
>
> Rules:
> - **Link the metric views in `eli_test_classic_catalog.care_protocol_semantic`** (the governed semantic layer),
>   never the `care_protocol` copies. The files already list the correct `*_semantic.*_compliance_metrics`
>   identifiers in `related_assets` — use those as written.
> - Keep the **"HEDIS-aligned demo, not NCQA-certified"** note on every measure Page.
> - If a Page with the same `name` already exists, **update it in place** — do not create a duplicate.
>
> **Before publishing, show me a review table:** file · Page name · synonym count · linked assets · new-vs-update.
> After I confirm, publish all 16 to `Clinical Domain`.

---

## Step 2 (separate, after the 16 are published) — PROPOSE additional Pages (do not publish)

> Read `/Volumes/eli_test_classic_catalog/care_protocol/source_documents` (9 facts-only source files) and
> **propose — do not publish** — new Pages only for terms that do **not** already have a Page. Known gaps:
> - **MAD / PDC** (medication adherence — proportion of days covered)
> - **Protocol Step-3 A1c follow-up** rate (`protocol_adherence_metrics`)
> - **Statin, metformin, and ACE/ARB contraindication rules** (`protocol_edges`)
>
> For each proposed Page, **cite the source file** backing each fact. Present as a table (proposed name ·
> source file · one-line definition · suggested linked assets). I will review before anything is published.

---

## Verify after publishing

Ask Genie One a seeded question (e.g. *"what is the GSD compliance rate?"*) and confirm the answer **cites** the
Page / metric view under **Ontology References**. **Extraction is slow — roughly daily, sometimes hours, NOT
minutes** (snippets are also density-gated: a workspace fetches inferred snippets only above ~1,000 — ADR-0018).
Don't expect citations right after publishing.

## What this covers vs. the backlog

- **Covered (16 Pages):** GSD, KED, SPD, BPD, EED, SSD; Care Gap, Diabetes Cohort, HbA1c, eGFR, uACR, Value Set,
  ICD-10 Subsumption, Measurement Year, Measure Drift, Document Access Scope.
- **Backlog (Step-2 proposals, not yet Pages):** MAD/PDC, Protocol Step-3 follow-up, contraindication/
  recommended-therapy rules (`protocol_edges`). Promote to `docs/ontology/pages/*.md` once reviewed, so they
  become code like the rest.
