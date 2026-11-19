"""Apply and validate the Genie-space knowledge stores (src/genie/knowledge_stores.py; ADR-0027).

    .venv/bin/python -I scripts/genie_knowledge.py              # write into resources/*.geniespace.json
    .venv/bin/python -I scripts/genie_knowledge.py --validate   # also run every snippet/join/benchmark on ECT

Applying is idempotent: sql_snippets, join_specs, column_configs and benchmarks are replaced wholesale from
the spec; text instructions, example SQL, sample questions and data sources are kept. Ids are content-
derived, sorted as the Genie API requires. --validate fails on any snippet that errors, a filter/join that
matches nothing (unless allow_empty), a column config on a missing column, or a benchmark whose answer
differs from its expected value. It also refreshes src/genie/table_columns.json, the schema snapshot the
offline test checks against.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genie.knowledge_stores import Store, stores  # noqa: E402

COLS = ROOT / "src/genie/table_columns.json"


def hid(*parts: str) -> str:
    return hashlib.md5("|".join(parts).encode()).hexdigest()


def body_with(store: Store, key: str, body: dict) -> dict:
    snips = {"measures": [], "filters": [], "expressions": []}
    for s in store.snippets:
        item = {"id": hid(key, s.kind, s.name), "display_name": s.name, "sql": [s.sql]}
        if s.alias:
            item["alias"] = s.alias
        if s.synonyms and s.kind in ("measure", "filter"):
            item["synonyms"] = s.synonyms
        snips[s.kind + "s"].append(item)
    instr = body.setdefault("instructions", {})
    instr["sql_snippets"] = {k: sorted(v, key=lambda x: x["id"]) for k, v in snips.items() if v}
    instr["join_specs"] = sorted(
        [
            {
                "id": hid(key, "join", j.left, j.right, j.on),
                "left": {"identifier": j.left, "alias": j.left.split(".")[-1]},
                "right": {"identifier": j.right, "alias": j.right.split(".")[-1]},
                "sql": [j.on, j.rt],
            }
            for j in store.joins
        ],
        key=lambda x: x["id"],
    )
    for k in ("sql_snippets", "join_specs"):
        if not instr[k]:
            instr.pop(k)
    for src in ("tables", "metric_views"):
        for t in body["data_sources"].get(src, []):
            cfg = store.columns.get(t["identifier"])
            t.pop("column_configs", None)
            if cfg:
                t["column_configs"] = sorted(
                    [{"column_name": c, **v} for c, v in cfg.items()], key=lambda x: x["column_name"]
                )
    if store.benchmarks:
        body["benchmarks"] = {
            "questions": sorted(
                [
                    {
                        "id": hid(key, "bench", b.question),
                        "question": [b.question],
                        "answer": [{"format": "SQL", "content": [b.sql]}],
                        **({"evaluation_note": [b.note]} if b.note else {}),
                    }
                    for b in store.benchmarks
                ],
                key=lambda x: x["id"],
            )
        }
    else:
        body.pop("benchmarks", None)
    return body


def apply_all() -> dict[str, Store]:
    out = stores()
    for key, st in out.items():
        p = ROOT / st.file
        body = body_with(st, key, json.loads(p.read_text()))
        p.write_text(json.dumps(body, indent=1, ensure_ascii=False) + "\n")
    return out


# ---------------------------------------------------------------------------------------------- validation
def _client():
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient(profile="ECT")
    wh = next(x.id for x in w.warehouses.list() if x.name == "Serverless Starter Warehouse")

    def q(sql: str):
        r = w.statement_execution.execute_statement(warehouse_id=wh, statement=sql, wait_timeout="50s")
        if r.status.state.value != "SUCCEEDED":
            raise RuntimeError((r.status.error.message if r.status.error else r.status.state.value)[:300])
        return r.result.data_array if r.result and r.result.data_array else []

    return q


def _tables_of(sql: str, known: dict[str, str]) -> list[str]:
    """fq tables a snippet's qualified columns refer to (qualifier = last identifier segment)."""
    quals = set(re.findall(r"\b([A-Za-z_]\w*)\.[A-Za-z_`]", re.sub(r"'[^']*'", "", sql)))
    return [known[q] for q in sorted(quals) if q in known]


def validate(all_stores: dict[str, Store]) -> int:
    q = _client()
    fails, n = [], 0
    tables = sorted(
        {
            t["identifier"]
            for st in all_stores.values()
            for t in json.loads((ROOT / st.file).read_text())["data_sources"].get("tables", [])
        }
    )
    schema = {}
    for s in sorted({t.split(".")[1] for t in tables}):
        for tbl, col in q(
            f"SELECT table_name, column_name FROM eli_test_classic_catalog.information_schema.columns "
            f"WHERE table_schema = '{s}' ORDER BY table_name, ordinal_position"
        ):
            fq = f"eli_test_classic_catalog.{s}.{tbl}"
            if fq in tables:
                schema.setdefault(fq, []).append(col)
    COLS.write_text(json.dumps(schema, indent=1, sort_keys=True) + "\n")

    def check(label: str, fn):
        nonlocal n
        n += 1
        try:
            msg = fn()
        except Exception as e:  # noqa: BLE001
            msg = f"ERROR {e}"
        if msg:
            fails.append(f"{label}: {msg}")
            print(f"  FAIL {label}: {msg}")

    for key, st in all_stores.items():
        body = json.loads((ROOT / st.file).read_text())
        space_tables = {t["identifier"] for t in body["data_sources"].get("tables", [])}
        known = {t.split(".")[-1]: t for t in space_tables}
        print(
            f"== {key}: {len(st.snippets)} snippets, {len(st.joins)} joins, "
            f"{sum(len(v) for v in st.columns.values())} column configs, {len(st.benchmarks)} benchmarks"
        )
        for s in st.snippets:
            ts = _tables_of(s.sql, known)

            def run(s=s, ts=ts):
                if len(ts) != 1:
                    return f"must reference exactly one space table by qualifier, found {ts}"
                t = ts[0]
                if s.kind == "measure":
                    q(f"SELECT {s.sql} FROM {t}")
                elif s.kind == "expression":
                    q(f"SELECT {s.sql} FROM {t} LIMIT 5")
                else:
                    c = int(q(f"SELECT COUNT(*) FROM {t} WHERE {s.sql}")[0][0])
                    if c == 0 and not s.allow_empty:
                        return "filter matches no rows"
                return ""

            check(f"{key} {s.kind} '{s.name}'", run)
        for j in st.joins:

            def runj(j=j):
                if not {j.left, j.right} <= space_tables:
                    return "join table not in the space"
                c = int(q(f"SELECT COUNT(*) FROM {j.left} JOIN {j.right} ON {j.on}")[0][0])
                return "" if c else "join matches no rows"

            check(f"{key} join {j.left.split('.')[-1]}~{j.right.split('.')[-1]}", runj)
        for t, cfg in st.columns.items():
            for c in cfg:
                check(
                    f"{key} column {t.split('.')[-1]}.{c}",
                    lambda t=t, c=c: (
                        "table not in the space"
                        if t not in space_tables
                        else ("" if c in schema.get(t, []) else "no such column")
                    ),
                )
        for b in st.benchmarks:

            def runb(b=b):
                rows = q(b.sql)
                got = rows[0][0] if rows else None
                if b.expect is None:
                    return "" if rows else "no rows"
                try:
                    ok = abs(float(got) - float(b.expect)) < 1e-6
                except (TypeError, ValueError):
                    ok = str(got) == b.expect
                return "" if ok else f"got {got!r}, expected {b.expect!r}"

            check(f"{key} benchmark '{b.question[:60]}'", runb)
    print(f"\nvalidated {n} items: {n - len(fails)} ok, {len(fails)} failed")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", action="store_true")
    a = ap.parse_args()
    st = apply_all()
    print(
        "applied:",
        ", ".join(f"{k}({len(v.snippets)}s/{len(v.joins)}j/{len(v.benchmarks)}b)" for k, v in st.items()),
    )
    return validate(st) if a.validate else 0


if __name__ == "__main__":
    rc = main()
    if rc:
        raise SystemExit(rc)
