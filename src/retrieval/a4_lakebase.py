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

    def search(self, question: str, k: int = 5) -> list[dict]:
        """Return the top-k ontology docs for a question (lexical ts_rank over the corpus)."""
        tsq = _tsquery(question)
        sql = (
            "SELECT doc_id, title, round(ts_rank(tsv, to_tsquery('english', %s))::numeric, 4) AS rank "
            "FROM retrieval_corpus WHERE tsv @@ to_tsquery('english', %s) "
            "ORDER BY rank DESC LIMIT %s")
        with psycopg.connect(host=self.host, user=self.user, password=self._token(),
                             dbname=self.dbname, sslmode="require") as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (tsq, tsq, k))
                cols = [c.name for c in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
