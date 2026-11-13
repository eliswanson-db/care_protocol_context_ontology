"""Bundle task: apply generated SQL files (graph views, validation views) with ${catalog} substituted.

Comment lines are dropped, then statements are split at a ';' that ends a line. Each statement runs in order;
the first failure stops the task with the statement shown (nothing is skipped silently).
"""

import argparse
import re
from pathlib import Path

from pyspark.sql import SparkSession


def statements(sql: str) -> list[str]:
    body = "\n".join(ln for ln in sql.splitlines() if not ln.lstrip().startswith("--"))
    return [x.strip() for x in re.split(r";[ \t]*\n", body + "\n") if x.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--file", required=True, action="append")
    a = ap.parse_args()
    spark = SparkSession.builder.getOrCreate()
    for path in a.file:
        stmts = statements(Path(path).read_text(encoding="utf-8").replace("${catalog}", a.catalog))
        for i, s in enumerate(stmts, 1):
            try:
                spark.sql(s)
            except Exception as e:  # show which statement failed
                raise SystemExit(f"{path} statement {i} failed: {e}\n{s[:800]}") from e
        print(f"  {path}: {len(stmts)} statements applied")


if __name__ == "__main__":
    main()
