-- A4 Lakebase RAG — document corpus + Lakebase Search indexes + document-level RLS.
--
-- Realizes the "Lakebase Search Document Level Authorization" design doc, re-aligned to this demo's
-- care-protocol corpus (ADR-0014). Idempotent; apply to the `databricks_postgres` database of the
-- `care-protocol` Lakebase project (production/primary endpoint). See docs/RUNBOOK.md "A4 Lakebase RAG".
--
-- Enabling Lakebase Search is IRREVERSIBLE and restarts computes — do it once, confirmed (RUNBOOK ⚙).
-- Embedding dimension 1024 matches the governed endpoint databricks-gte-large-en used elsewhere in the repo.
--
-- Two paths are supported so the demo runs whether or not Lakebase Search is enabled:
--   * Lakebase Search (preferred): lakebase_vector / lakebase_text, indexes lakebase_ann + lakebase_bm25,
--     with lakebase_ann.prefilter = on so RLS is evaluated INSIDE the index scan (true pre-filtering).
--   * Fallback (verified working today, ADR-0009): pgvector + Postgres full-text tsvector (hnsw + GIN).
-- The fallback lines are commented; uncomment them (and comment the Lakebase Search lines) if Search is off.

CREATE SCHEMA IF NOT EXISTS rag;

-- ---------------------------------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------------------------------
-- Preferred (requires Settings → Enable Lakebase Search; CASCADE pulls pgvector in as a dependency):
CREATE EXTENSION IF NOT EXISTS lakebase_vector CASCADE;   -- vector type + lakebase_ann index access method
CREATE EXTENSION IF NOT EXISTS lakebase_text;             -- BM25 keyword search (lakebase_bm25 + to_bm25query)
-- Fallback if Lakebase Search is not enabled:
-- CREATE EXTENSION IF NOT EXISTS vector;                 -- pgvector (hnsw cosine); Postgres FTS is built in

-- ---------------------------------------------------------------------------------------------------
-- Tables (design doc §7, tuned for the care-protocol corpus)
-- ---------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rag.documents (
  document_id       TEXT PRIMARY KEY,
  title             TEXT        NOT NULL,
  source            TEXT,                        -- provenance / citation of the source material
  license           TEXT,                        -- e.g. public-domain-derived-synthetic, synthetic
  measurement_year  INTEGER,
  effective_date    DATE,
  supersedes        TEXT,                         -- doc_id this version replaces (drift / superseded-policy story)
  patient_id        TEXT,                         -- NULL for population docs; set for patient-specific records
  source_uri        TEXT,                         -- UC Volume path when staged (ai_parse path)
  content_hash      TEXT        NOT NULL,         -- idempotent reload key
  active            BOOLEAN     NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS rag.chunks (
  chunk_id          TEXT PRIMARY KEY,
  document_id       TEXT        NOT NULL REFERENCES rag.documents (document_id),
  chunk_position    INTEGER     NOT NULL,
  content           TEXT        NOT NULL,          -- displayable passage (cited verbatim by the agent)
  section_path      TEXT,                          -- heading trail, e.g. "Metformin and kidney function"
  page_start        INTEGER,
  page_end          INTEGER,
  embedding         VECTOR(1024),                  -- gte-large-en; must match the endpoint + ANN index
  body_tsv          TSVECTOR,                      -- lexical half (BM25 / full-text)
  active            BOOLEAN     NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS rag.document_acl (
  document_id       TEXT        NOT NULL REFERENCES rag.documents (document_id),
  principal_type    TEXT        NOT NULL CHECK (principal_type IN ('USER', 'GROUP')),
  principal_id      TEXT        NOT NULL,
  effect            TEXT        NOT NULL DEFAULT 'ALLOW' CHECK (effect IN ('ALLOW', 'DENY')),
  permission        TEXT        NOT NULL DEFAULT 'READ',
  PRIMARY KEY (document_id, principal_type, principal_id, permission, effect)
);

CREATE TABLE IF NOT EXISTS rag.group_membership (
  user_id           TEXT        NOT NULL,
  group_id          TEXT        NOT NULL,
  PRIMARY KEY (user_id, group_id)
);

-- ---------------------------------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS chunks_document_lookup ON rag.chunks (document_id);
CREATE INDEX IF NOT EXISTS document_acl_lookup   ON rag.document_acl (document_id, principal_type, principal_id);
CREATE INDEX IF NOT EXISTS group_membership_lookup ON rag.group_membership (user_id, group_id);

-- Preferred: Lakebase Search indexes. Build the BM25 index AFTER loading (corpus stats at build time).
CREATE INDEX IF NOT EXISTS chunks_embedding_ann ON rag.chunks USING lakebase_ann (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_body_bm25     ON rag.chunks USING lakebase_bm25 (body_tsv);
-- Fallback (pgvector + GIN) if Lakebase Search is off:
-- CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw ON rag.chunks USING hnsw (embedding vector_cosine_ops);
-- CREATE INDEX IF NOT EXISTS chunks_body_gin       ON rag.chunks USING gin (body_tsv);

-- ---------------------------------------------------------------------------------------------------
-- Roles (design doc §8 "RLS security controls": separate load vs read; reader is not owner, no BYPASSRLS)
-- ---------------------------------------------------------------------------------------------------
DO $$ BEGIN CREATE ROLE rag_loader; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE ROLE rag_reader; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
ALTER ROLE rag_reader NOBYPASSRLS;

GRANT USAGE ON SCHEMA rag TO rag_reader, rag_loader;
GRANT SELECT ON rag.documents, rag.chunks TO rag_reader;              -- reader sees ONLY these two, via RLS
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA rag TO rag_loader;
-- Direct access to ACL / membership tables is restricted to the loader (design doc §8).
REVOKE SELECT ON rag.document_acl, rag.group_membership FROM rag_reader;

-- ---------------------------------------------------------------------------------------------------
-- Row-Level Security (design doc §8). Enforced on BOTH chunks and documents to avoid metadata leakage.
-- Policy: a row is visible iff an ALLOW ACL matches the caller (USER = current_user, or GROUP the caller
-- belongs to per group_membership) AND no matching DENY ACL exists (deny precedence). Allow-only corpora
-- simply carry no DENY rows.
--
-- The ACL decision is encapsulated in rag.acl_allows(), a SECURITY DEFINER function: Postgres evaluates a
-- policy USING expression AS THE INVOKING ROLE, but §8 revokes the reader's direct SELECT on document_acl /
-- group_membership (so a reader cannot enumerate the org's ACLs/memberships). The definer function runs as
-- its owner (the schema owner, who can read those tables) and returns only a boolean, so RLS is enforced
-- without ever granting the reader visibility into the control tables. current_user is captured in the
-- policy (invoker) context and passed in as an argument, because inside a SECURITY DEFINER body current_user
-- would resolve to the function owner, not the caller.
-- ---------------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION rag.acl_allows(p_document_id text, p_caller text)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = rag, pg_temp
AS $$
  SELECT EXISTS (
    SELECT 1 FROM rag.document_acl a
    WHERE a.document_id = p_document_id AND a.permission = 'READ' AND a.effect = 'ALLOW'
      AND ( (a.principal_type = 'USER'  AND a.principal_id = p_caller)
         OR (a.principal_type = 'GROUP' AND EXISTS (
               SELECT 1 FROM rag.group_membership gm
               WHERE gm.user_id = p_caller AND gm.group_id = a.principal_id)) )
  )
  AND NOT EXISTS (
    SELECT 1 FROM rag.document_acl d
    WHERE d.document_id = p_document_id AND d.permission = 'READ' AND d.effect = 'DENY'
      AND ( (d.principal_type = 'USER'  AND d.principal_id = p_caller)
         OR (d.principal_type = 'GROUP' AND EXISTS (
               SELECT 1 FROM rag.group_membership gm
               WHERE gm.user_id = p_caller AND gm.group_id = d.principal_id)) )
  );
$$;
-- The reader may only CALL the decision, never read the control tables it consults.
REVOKE ALL ON FUNCTION rag.acl_allows(text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION rag.acl_allows(text, text) TO rag_reader;

ALTER TABLE rag.chunks    ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag.chunks    FORCE  ROW LEVEL SECURITY;
ALTER TABLE rag.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag.documents FORCE  ROW LEVEL SECURITY;

DROP POLICY IF EXISTS chunks_read_policy ON rag.chunks;
CREATE POLICY chunks_read_policy ON rag.chunks FOR SELECT USING (
  active = TRUE AND rag.acl_allows(rag.chunks.document_id, current_user::text)
);

DROP POLICY IF EXISTS documents_read_policy ON rag.documents;
CREATE POLICY documents_read_policy ON rag.documents FOR SELECT USING (
  active = TRUE AND rag.acl_allows(rag.documents.document_id, current_user::text)
);
