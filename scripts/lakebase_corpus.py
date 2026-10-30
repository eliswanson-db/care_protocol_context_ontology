"""Generate the A4 Lakebase retrieval-corpus SQL from the Genie Ontology Pages (docs/ontology/pages/*.md).

Emits (to stdout) idempotent Postgres DDL + INSERTs + a tsvector full-text index: one corpus row per Page
(doc_id, title, synonyms, body). This is the lexical half of the A4 hybrid retriever (pgvector can be added
for the semantic half). Pipe into Lakebase:

    python scripts/lakebase_corpus.py --src_dir docs/ontology/pages | \
      PGPASSWORD="$TOKEN" psql "host=$HOST user=$USER dbname=databricks_postgres sslmode=require"

Reproducible-by-code: the corpus is derived from the version-controlled Pages, not hand-entered.
"""
import argparse
import glob
import os
import re


def parse_md(path):
    text = open(path).read()
    name, synonyms = os.path.basename(path)[:-3], ""
    body = text
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if m:
        fm, body = m.group(1), m.group(2)
        for line in fm.splitlines():
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip()
            if line.startswith("synonyms:"):
                synonyms = line.split(":", 1)[1].strip().strip("[]")
    return os.path.basename(path)[:-3], name, synonyms, body.strip()


def sql_str(s):
    return "'" + s.replace("'", "''") + "'"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src_dir", default="docs/ontology/pages")
    args = ap.parse_args()

    print("-- A4 Lakebase retrieval corpus (generated from docs/ontology/pages by lakebase_corpus.py)")
    print("DROP TABLE IF EXISTS retrieval_corpus;")
    print("CREATE TABLE retrieval_corpus (doc_id text PRIMARY KEY, title text, synonyms text, body text, tsv tsvector);")
    for path in sorted(glob.glob(os.path.join(args.src_dir, "*.md"))):
        if os.path.basename(path).lower() == "readme.md":
            continue
        doc_id, title, synonyms, body = parse_md(path)
        print(f"INSERT INTO retrieval_corpus (doc_id, title, synonyms, body) VALUES "
              f"({sql_str(doc_id)}, {sql_str(title)}, {sql_str(synonyms)}, {sql_str(body)});")
    print("UPDATE retrieval_corpus SET tsv = to_tsvector('english', "
          "coalesce(title,'') || ' ' || coalesce(synonyms,'') || ' ' || coalesce(body,''));")
    print("CREATE INDEX IF NOT EXISTS idx_corpus_tsv ON retrieval_corpus USING GIN(tsv);")
    print("SELECT count(*) AS corpus_docs FROM retrieval_corpus;")


if __name__ == "__main__":
    main()
