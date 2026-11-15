---
page: pages/a5bb74e9-015f-4883-bee6-16baea560dd5
title: "Document Access Scope \u2014 Care Team vs Population Quality Analytics"
state: DRAFT
updated: 2026-11-01T22:42:45.675Z
synonyms: ["RAG row-level security", "care team scope", "document ACL", "document access scope", "population analytics scope", "retrieval authorization", "who can see which document"]
description: "Document access scope governs which unstructured documents a user may retrieve from the A4 Lakebase RAG corpus."
---
**Document access scope** governs which unstructured documents a user may retrieve from the A4 Lakebase RAG
corpus. It is enforced by **PostgreSQL Row-Level Security (RLS)** on `rag.chunks` and `rag.documents`, not by
an application filter — so the entitlement check is logically mandatory and cannot be omitted by a query.

Two scopes model the clinical reality:

- **`quality_analytics`** — population quality analysts. May read protocol, measure-specification, and payer
  policy documents. May **not** read patient-specific clinical records.
- **`care_team`** — the treating care team. May read everything `quality_analytics` reads **plus**
  patient-specific clinical correspondence (e.g. an outside ophthalmology consult letter for one patient).

The retrieval connection carries the **end-user identity** (OAuth/OBO), so Lakebase evaluates `current_user`
against `document_acl` (ALLOW/DENY) and `group_membership`. With `lakebase_ann.prefilter = on`, the policy is
evaluated **inside** the vector/BM25 index scan — unauthorized rows are never scored or returned.

This realizes the demo's access-scope security tracer (**+perm**): an analyst asking for a patient's retinal
exam gets the population screening-cadence guidance but **not** the patient's consult letter; a care-team
clinician gets both. "Aggregate visible, patient record not" is enforced at the database, across the RAG arm.

> See `src/retrieval/lakebase/schema.sql` (policy) and the "Lakebase Search Document Level Authorization"
> design. Synthetic demo; identities are placeholders backed by workspace groups on deploy.
