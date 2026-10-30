"""Verify the capability-map gold / closure_sql reference arm against live data.

Runs every `-- @id:` query in gold_queries.sql on a SQL warehouse and compares its single result to the
`-- expect:` value declared in that query's header. gold_queries.sql is the authoritative answer key AND the
closure_sql arm reference (fixed-shape SQL over the materialized closure/edge tables), so this is two things:
  * a reproducible REGRESSION GATE -- catches it when a reflow, crosswalk, or schema change moves a gold value
    out from under docs/benchmark/ground_truth.yaml (exactly the manual check done by hand on 2026-10-30);
  * the runnable closure_sql arm -- for classes 2-6 it reaches gold by construction, which is the baseline the
    other arms (metric_view / rag / graph) are scored against as they come online.

Not a full multi-arm capability-map scorer (that needs the live arms: Genie One, Lakebase RAG, Ontobricks).
This verifies the spine those arms are measured on.

Usage:
  python src/benchmark/verify_gold.py --warehouse_id <WH> --profile ECT
  (defaults: catalog=eli_test_classic_catalog, schema=care_protocol, tschema=care_protocol_terminology)
"""
import argparse
import os
import re
import sys

from databricks.sdk import WorkspaceClient

FLOAT_TOL = 0.01  # rates are rounded to 4 dp in the gold queries; a 1-pt tolerance absorbs rounding only


def parse_gold(path):
    """Split gold_queries.sql into {id, cls, min_approach, expect, sql} blocks on the `-- @id:` headers."""
    raw = open(path).read()
    blocks = []
    for chunk in re.split(r"(?m)^-- @id:\s*", raw)[1:]:
        lines = chunk.splitlines()
        qid = lines[0].strip()
        meta = re.search(r"class:\s*(\S+).*?min_approach:\s*(\S+)", chunk)
        expect = re.search(r"expect:\s*(.+)", chunk)
        # SQL = non-comment lines after the id line (the id line is bare text, not a comment).
        sql_lines = [ln for ln in lines[1:] if not ln.lstrip().startswith("--")]
        sql = "\n".join(sql_lines).strip()
        blocks.append({
            "id": qid,
            "cls": meta.group(1) if meta else "?",
            "approach": meta.group(2) if meta else "?",
            "expect": expect.group(1).strip() if expect else None,
            "sql": sql,
        })
    return blocks


def compare(expect, got):
    """True if the arm's scalar result matches the expected gold (int exact, float tol, set for code lists)."""
    if expect is None:
        return None
    got = "" if got is None else str(got)
    if "," in expect and not re.fullmatch(r"[\d.,]+", expect):  # code list, e.g. "33914-3,98979-8"
        return set(expect.split(",")) == set(got.split(","))
    try:
        e = float(expect)
        g = float(got)
        return abs(e - g) <= (FLOAT_TOL if "." in expect else 0.5)
    except ValueError:
        return expect.lower() in got.lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--warehouse_id", required=True)
    ap.add_argument("--catalog", default="eli_test_classic_catalog")
    ap.add_argument("--schema", default="care_protocol")
    ap.add_argument("--tschema", default="care_protocol_terminology")
    ap.add_argument("--gold", default=os.path.join(os.path.dirname(__file__), "gold_queries.sql"))
    args = ap.parse_args()

    w = WorkspaceClient()
    blocks = parse_gold(args.gold)
    subs = {"catalog": args.catalog, "schema": args.schema, "tschema": args.tschema}

    n_pass = n_fail = 0
    print(f"Verifying {len(blocks)} gold queries on warehouse {args.warehouse_id}...\n")
    for b in blocks:
        sql = b["sql"].format(**subs)
        try:
            r = w.statement_execution.execute_statement(
                warehouse_id=args.warehouse_id, statement=sql, wait_timeout="50s")
            data = (r.result.data_array if r.result and r.result.data_array else []) or []
            got = data[0][0] if data and data[0] else None
        except Exception as e:  # noqa: BLE001
            got = f"ERROR: {e}"
        ok = compare(b["expect"], got)
        mark = "PASS" if ok else ("----" if ok is None else "FAIL")
        if ok is True:
            n_pass += 1
        elif ok is False:
            n_fail += 1
        print(f"  [{mark}] {b['id']:<26} class={b['cls']:<22} expect={b['expect']!s:<16} got={got}")

    print(f"\nclosure_sql reference: {n_pass} pass / {n_fail} fail / {len(blocks)} total.")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
