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
