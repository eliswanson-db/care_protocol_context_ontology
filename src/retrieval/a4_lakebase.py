"""A4 — Lakebase hybrid retriever over the ontology corpus.

Retrieval arm that serves governed ontology context from Lakebase Postgres. The corpus (one row per Page)
is loaded by scripts/lakebase_corpus.py; this module runs the retrieval. Lexical ranking uses Postgres
full-text search with an OR-of-terms tsquery (graceful partial matching); pgvector cosine can be layered in
as the semantic half once embeddings are added (see pgvector in the databricks-lakebase skill) — the
`hybrid=` hook is where that blends in.

Connects with an OAuth token from the Databricks SDK (refreshes per call; tokens last ~1h). Requires psycopg.

    from databricks.sdk import WorkspaceClient
    r = A4Retriever(endpoint="projects/care-protocol/branches/production/endpoints/primary",
                    host="ep-...database.us-east-1.cloud.databricks.com", user="me@databricks.com")
    r.search("how is the diabetes cohort defined", k=3)
"""
from __future__ import annotations

import re

import psycopg
from databricks.sdk import WorkspaceClient

_STOP = {"how", "is", "the", "a", "an", "what", "does", "do", "why", "need", "for", "of", "to", "as",
         "are", "in", "on", "and", "or", "which", "that", "this", "with", "be", "it", "counts", "count",
         "patients", "patient", "show", "me", "list"}


def _tsquery(question: str) -> str:
    terms = [w for w in re.findall(r"[a-z0-9]+", question.lower()) if len(w) > 2 and w not in _STOP]
    return " | ".join(dict.fromkeys(terms)) or question.lower()


class A4Retriever:
    def __init__(self, endpoint: str, host: str, user: str, dbname: str = "databricks_postgres",
                 profile: str | None = None):
        self.endpoint, self.host, self.user, self.dbname = endpoint, host, user, dbname
        self._w = WorkspaceClient(profile=profile) if profile else WorkspaceClient()

    def _token(self) -> str:
        return self._w.postgres.generate_database_credential(self.endpoint).token

    def _embed(self, text: str) -> str:
        r = self._w.serving_endpoints.query(name="databricks-gte-large-en", input=[text])
        vec = r.data[0].embedding if getattr(r, "data", None) else r.predictions[0]
        return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"

    def _rows(self, cur):
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def search(self, question: str, k: int = 5) -> list[dict]:
        """Lexical-only retrieval: Postgres full-text ts_rank over an OR-of-terms tsquery."""
        tsq = _tsquery(question)
        sql = ("SELECT doc_id, title, round(ts_rank(tsv, to_tsquery('english', %s))::numeric, 4) AS rank "
               "FROM retrieval_corpus WHERE tsv @@ to_tsquery('english', %s) ORDER BY rank DESC LIMIT %s")
        with psycopg.connect(host=self.host, user=self.user, password=self._token(),
                             dbname=self.dbname, sslmode="require") as conn, conn.cursor() as cur:
            cur.execute(sql, (tsq, tsq, k))
            return self._rows(cur)

    def search_semantic(self, question: str, k: int = 5) -> list[dict]:
        """Semantic-only retrieval: pgvector cosine similarity against the question embedding."""
        qvec = self._embed(question)
        sql = ("SELECT doc_id, title, round((1 - (embedding <=> %s::vector))::numeric, 4) AS sim "
               "FROM retrieval_corpus WHERE embedding IS NOT NULL ORDER BY embedding <=> %s::vector LIMIT %s")
        with psycopg.connect(host=self.host, user=self.user, password=self._token(),
                             dbname=self.dbname, sslmode="require") as conn, conn.cursor() as cur:
            cur.execute(sql, (qvec, qvec, k))
            return self._rows(cur)

    def search_hybrid(self, question: str, k: int = 5, rrf_k: int = 60) -> list[dict]:
        """Hybrid retrieval: Reciprocal Rank Fusion of the lexical and semantic rankings (scale-free)."""
        tsq, qvec = _tsquery(question), self._embed(question)
        sql = (
            "WITH lex AS (SELECT doc_id, row_number() OVER (ORDER BY ts_rank(tsv, to_tsquery('english', %s)) DESC) rk "
            "             FROM retrieval_corpus WHERE tsv @@ to_tsquery('english', %s)), "
            "sem AS (SELECT doc_id, row_number() OVER (ORDER BY embedding <=> %s::vector) rk "
            "        FROM retrieval_corpus WHERE embedding IS NOT NULL) "
            "SELECT c.doc_id, c.title, "
            "       round((coalesce(1.0/(%s+lex.rk),0) + coalesce(1.0/(%s+sem.rk),0))::numeric, 5) AS rrf "
            "FROM retrieval_corpus c LEFT JOIN lex USING (doc_id) LEFT JOIN sem USING (doc_id) "
            "ORDER BY rrf DESC LIMIT %s")
        with psycopg.connect(host=self.host, user=self.user, password=self._token(),
                             dbname=self.dbname, sslmode="require") as conn, conn.cursor() as cur:
            cur.execute(sql, (tsq, tsq, qvec, rrf_k, rrf_k, k))
            return self._rows(cur)


# Columns returned by every document-RAG query — real passages with citation provenance (never a bare score).
_CITE = ("c.chunk_id, c.document_id, d.title, c.section_path, c.page_start, "
         "d.source, d.measurement_year, c.content")


class A4RagRetriever(A4Retriever):
    """A4 document-RAG over the care-protocol corpus in rag.chunks (ADR-0014).

    Realizes the Lakebase-Search document-authorization design: retrieval runs against RLS-protected
    rag.chunks, so the querying identity (current_user) sees only authorized documents — no application-side
    ACL filter. Returns real passages with document/section/page provenance for citation.

    `search_ext=True` uses the Lakebase Search operators (lakebase_bm25 `to_bm25query`, lakebase_ann with
    `prefilter=on` so RLS is evaluated inside the index scan); `search_ext=False` uses the pgvector + Postgres
    full-text fallback (ADR-0009) for workspaces where Lakebase Search is not enabled.

    `as_user` SET ROLEs to a seeded identity so the negative-security test can simulate OBO identities without
    two real OAuth logins; in production the connection itself carries the end-user OAuth/OBO identity.
    """

    def __init__(self, *args, search_ext: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self.search_ext = search_ext

    def _run(self, sql: str, params: tuple, as_user: str | None, prefilter: bool = False) -> list[dict]:
        with psycopg.connect(host=self.host, user=self.user, password=self._token(),
                             dbname=self.dbname, sslmode="require") as conn, conn.cursor() as cur:
            if as_user:
                cur.execute('SET ROLE "%s"' % as_user.replace('"', ""))
            if prefilter and self.search_ext:
                cur.execute("SET lakebase_ann.prefilter TO on")
            cur.execute(sql, params)
            return self._rows(cur)

    def search_documents(self, question: str, k: int = 5, mode: str = "hybrid",
                         as_user: str | None = None) -> list[dict]:
        """Retrieve authorized care-protocol passages. mode = lexical | semantic | hybrid."""
        if mode == "lexical":
            return self.search_doc_lexical(question, k, as_user)
        if mode == "semantic":
            return self.search_doc_semantic(question, k, as_user)
        return self.search_doc_hybrid(question, k, as_user=as_user)

    def search_doc_lexical(self, question: str, k: int = 5, as_user: str | None = None) -> list[dict]:
        if self.search_ext:  # Lakebase Search BM25
            sql = (f"SELECT {_CITE}, (c.body_tsv <@> to_bm25query(to_tsvector('english', %s), "
                   "'rag.chunks_body_bm25')) AS score FROM rag.chunks c JOIN rag.documents d "
                   "USING (document_id) ORDER BY score LIMIT %s")
            return self._run(sql, (question, k), as_user)
        tsq = _tsquery(question)  # fallback: Postgres full-text
        sql = (f"SELECT {_CITE}, round(ts_rank(c.body_tsv, to_tsquery('english', %s))::numeric,4) AS score "
               "FROM rag.chunks c JOIN rag.documents d USING (document_id) "
               "WHERE c.body_tsv @@ to_tsquery('english', %s) ORDER BY score DESC LIMIT %s")
        return self._run(sql, (tsq, tsq, k), as_user)

    def search_doc_semantic(self, question: str, k: int = 5, as_user: str | None = None) -> list[dict]:
        qvec = self._embed(question)
        sql = (f"SELECT {_CITE}, round((1 - (c.embedding <=> %s::vector))::numeric,4) AS score "
               "FROM rag.chunks c JOIN rag.documents d USING (document_id) "
               "WHERE c.embedding IS NOT NULL ORDER BY c.embedding <=> %s::vector LIMIT %s")
        return self._run(sql, (qvec, qvec, k), as_user, prefilter=True)

    def search_doc_hybrid(self, question: str, k: int = 5, rrf_k: int = 60,
                         as_user: str | None = None) -> list[dict]:
        tsq, qvec = _tsquery(question), self._embed(question)
        sql = (
            "WITH lex AS (SELECT chunk_id, row_number() OVER (ORDER BY ts_rank(body_tsv, "
            "               to_tsquery('english', %s)) DESC) rk FROM rag.chunks "
            "             WHERE body_tsv @@ to_tsquery('english', %s)), "
            "sem AS (SELECT chunk_id, row_number() OVER (ORDER BY embedding <=> %s::vector) rk "
            "        FROM rag.chunks WHERE embedding IS NOT NULL) "
            f"SELECT {_CITE}, round((coalesce(1.0/(%s+lex.rk),0)+coalesce(1.0/(%s+sem.rk),0))::numeric,5) AS score "
            "FROM rag.chunks c JOIN rag.documents d USING (document_id) "
            "LEFT JOIN lex USING (chunk_id) LEFT JOIN sem USING (chunk_id) "
            "ORDER BY score DESC LIMIT %s")
        return self._run(sql, (tsq, tsq, qvec, rrf_k, rrf_k, k), as_user, prefilter=True)
