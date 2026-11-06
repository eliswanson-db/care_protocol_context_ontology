"""Migrate a Genie space's SQL to the post-2026-11-04 names, validate every statement, and (only with --apply)
write it back.

What changed on 2026-11-04 (ADR-0013 rule-in-the-semantic-layer):
  * metric views moved from `care_protocol.*_metrics` to `care_protocol_semantic.*_metrics`;
  * the gold tables lost their derived columns (`status`, `numerator_flag`, `a1c_gt9`, `a1c_lt8`, `egfr_flag`,
    `uacr_flag`); the rules now live in the metric views and are re-expressed here over the evidence columns,
    exactly as the metric views compute them.

Usage (read-only unless --apply):
  .venv/bin/python -I scripts/migrate_genie_space_names.py --profile ECT --space-id <id> --out /tmp/space_fix
  .venv/bin/python -I scripts/migrate_genie_space_names.py --profile ECT --space-id <id> --out /tmp/space_fix --apply
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
import time

from databricks.sdk import WorkspaceClient

CATALOG = "eli_test_classic_catalog"

# Rules per gold table, as the metric views define them. {p} = the column qualifier ("" or "alias.").
_BOTH_KED = "({p}egfr_datetime IS NOT NULL AND {p}uacr_datetime IS NOT NULL)"
_BPD_OK = "coalesce({p}systolic < 140 AND {p}diastolic < 90, false)"   # no reading -> NOT_MET, as in the view
RULES: dict[str, dict[str, str]] = {
    "gsd": {"MET": "{p}evidence_datetime IS NOT NULL", "NOT_MET": "{p}evidence_datetime IS NULL",
            "numerator_flag": "({p}evidence_datetime IS NOT NULL)",
            "a1c_gt9": "({p}evidence_value > 9.0)", "a1c_lt8": "({p}evidence_value < 8.0)"},
    "spd": {"MET": "{p}evidence_datetime IS NOT NULL", "NOT_MET": "{p}evidence_datetime IS NULL",
            "numerator_flag": "({p}evidence_datetime IS NOT NULL)"},
    "eed": {"MET": "{p}evidence_datetime IS NOT NULL", "NOT_MET": "{p}evidence_datetime IS NULL",
            "numerator_flag": "({p}evidence_datetime IS NOT NULL)"},
    "ked": {"MET": _BOTH_KED, "NOT_MET": "NOT " + _BOTH_KED, "numerator_flag": _BOTH_KED,
            "egfr_flag": "({p}egfr_datetime IS NOT NULL)", "uacr_flag": "({p}uacr_datetime IS NOT NULL)"},
    "bpd": {"MET": _BPD_OK, "NOT_MET": "NOT " + _BPD_OK, "numerator_flag": _BPD_OK},
}
REMOVED = {"status", "numerator_flag", "a1c_gt9", "a1c_lt8", "egfr_flag", "uacr_flag"}
_TABLE = re.compile(r"(?:\w+\.)?(?:care_protocol\.)?gold_adherence_(gsd|spd|eed|ked|bpd)\b(?:\s+(?:AS\s+)?(?!ON\b|WHERE\b|JOIN\b|"
                    r"GROUP\b|ORDER\b|LEFT\b|INNER\b|UNION\b|USING\b|LIMIT\b)([a-z_]\w*))?", re.I)


_FLAG_COLS = ("numerator_flag", "a1c_gt9", "a1c_lt8", "egfr_flag", "uacr_flag")
_PROJECTED = re.compile(r"(?<=[,\s])((?:[a-z_]\w*\.)?)(" + "|".join(_FLAG_COLS) + r")(?=\s+FROM\b)", re.I)


def _rewrite_segment(seg: str, keep_bare: set[str] = frozenset()) -> str:
    """Rewrite one UNION branch. Qualified refs (gold_adherence_x.col / alias.col) use their table's rules; bare refs
    use the branch's table when the branch reads exactly one gold table. A flag that a CTE projects is re-aliased to
    its old name (`<rule> AS numerator_flag`), and bare refs to that name elsewhere are left alone (they read the CTE)."""
    quals: dict[str, str] = {}
    tables = set()
    for m in _TABLE.finditer(seg):
        tables.add(m.group(1).lower())
        quals[f"gold_adherence_{m.group(1).lower()}"] = m.group(1).lower()
        if m.group(2):
            quals[m.group(2)] = m.group(1).lower()
    bare = next(iter(tables)) if len(tables) == 1 else None

    def sub(prefix_re: str, measure: str, prefix: str, s: str) -> str:
        r = RULES[measure]
        s = re.sub(rf"{prefix_re}\bstatus\s*=\s*'(NOT_MET|MET)'",
                   lambda m: r[m.group(1)].format(p=prefix), s)
        for col in ("numerator_flag", "a1c_gt9", "a1c_lt8", "egfr_flag", "uacr_flag"):
            if col in r:
                s = re.sub(rf"{prefix_re}\b{col}\b", r[col].format(p=prefix), s)
        return s

    def project(m):
        q, col = m.group(1).rstrip("."), m.group(2)
        measure = quals.get(q) if q else bare
        if not measure or col not in RULES[measure]:
            return m.group(0)
        return RULES[measure][col].format(p=f"{q}." if q else "") + f" AS {col}"
    seg = _PROJECTED.sub(project, seg)
    for q, measure in sorted(quals.items(), key=lambda kv: -len(kv[0])):
        seg = sub(rf"(?<![\w.]){re.escape(q)}\.", measure, f"{q}.", seg)
    if bare:
        r = {k: v for k, v in RULES[bare].items() if k not in keep_bare}
        saved = RULES[bare]
        RULES[bare] = r
        try:
            seg = sub(r"(?<![\w.`])", bare, "", seg)
        finally:
            RULES[bare] = saved
    return seg


def rewrite_sql(sql: str) -> str:
    sql = re.sub(r"\bcare_protocol\.(\w+_metrics)\b", r"care_protocol_semantic.\1", sql)
    keep = {m.group(2) for m in _PROJECTED.finditer(sql)}   # names a CTE re-exports: bare refs read the CTE
    parts = re.split(r"(\bUNION\s+ALL\b|\bUNION\b)", sql, flags=re.I)
    return "".join(p if i % 2 else _rewrite_segment(p, keep) for i, p in enumerate(parts))


def _join(x) -> str:
    return "\n".join(x) if isinstance(x, list) else (x or "")


def _split(s: str, like) -> list[str] | str:
    return s.split("\n") if isinstance(like, list) else s


TEXT_FIX = (
    "For patient-level detail or care gaps, use gold_adherence_<measure>. status = 'NOT_MET' means a care gap; "
    "'MET' means compliant.",
    "For patient-level detail or care gaps, use gold_adherence_<measure>. The MET / NOT_MET rule lives in each metric "
    "view's `Compliance Status` dimension; over the gold tables a care gap is: GSD/SPD/EED evidence_datetime IS NULL, "
    "KED egfr_datetime IS NULL OR uacr_datetime IS NULL, BPD NOT (systolic < 140 AND diastolic < 90) or no reading.",
)


def migrate(ss: dict, current_cols: dict[str, set[str]]) -> tuple[dict, list[tuple[str, str, str]]]:
    """Return (new serialized space, [(where, old, new)]) -- every changed string."""
    ss = json.loads(json.dumps(ss))
    changes: list[tuple[str, str, str]] = []

    def fix(where: str, holder: dict, key: str):
        old = _join(holder.get(key))
        new = rewrite_sql(old)
        if new != old:
            holder[key] = _split(new, holder.get(key))
            changes.append((where, old, new))

    for t in ss.get("data_sources", {}).get("tables", []):
        old = t["identifier"]
        t["identifier"] = re.sub(r"\.care_protocol\.(\w+_metrics)$", r".care_protocol_semantic.\1", old)
        if t["identifier"] != old:
            changes.append(("data_sources.table", old, t["identifier"]))
        name = t["identifier"].split(".")[-1]
        if t.get("column_configs") and name in current_cols:
            keep = [c for c in t["column_configs"] if c["column_name"] in current_cols[name]]
            for c in t["column_configs"]:
                if c not in keep:
                    changes.append((f"column_config {name}", c["column_name"], "(removed: column no longer exists)"))
            t["column_configs"] = keep
    inst = ss.get("instructions", {})
    for kind, items in (inst.get("sql_snippets") or {}).items():
        for s in items:
            fix(f"sql_snippet/{kind}: {s.get('display_name', '')[:60]}", s, "sql")
    for j in inst.get("join_specs", []):
        fix("join_spec", j, "sql")
        for side in ("left", "right"):
            if isinstance(j.get(side), dict) and "identifier" in j[side]:
                j[side]["identifier"] = rewrite_sql(j[side]["identifier"])
    for e in inst.get("example_question_sqls", []):
        fix(f"example: {_join(e.get('question'))[:60]}", e, "sql")
    for t in inst.get("text_instructions", []):
        old = _join(t.get("content"))
        new = old.replace(*TEXT_FIX)
        new = re.sub(r"\bcare_protocol\.(\w+_metrics)\b", r"care_protocol_semantic.\1", new)
        if new != old:
            t["content"] = _split(new, t.get("content"))
            changes.append(("text_instruction", old, new))
    for q in (ss.get("benchmarks") or {}).get("questions", []):
        for a in q.get("answer", []) or []:
            if isinstance(a, dict) and "content" in a:
                fix(f"benchmark: {_join(q.get('question'))[:60]}", a, "content")
    # The import API requires sorted lists (moving metric views to another schema changes the table order).
    ds = ss.get("data_sources", {})
    if ds.get("tables"):
        ds["tables"].sort(key=lambda t: t["identifier"])
        for t in ds["tables"]:
            if t.get("column_configs"):
                t["column_configs"].sort(key=lambda c: c["column_name"])
    return ss, changes


def _statements(ss: dict) -> list[tuple[str, str]]:
    """Every SQL fragment in the space, wrapped as a runnable read-only statement."""
    out = []
    inst = ss.get("instructions", {})
    for kind, items in (inst.get("sql_snippets") or {}).items():
        for s in items:
            frag = _join(s["sql"])
            m = re.search(r"gold_adherence_(\w+)", frag)
            tbl = f"{CATALOG}.care_protocol.gold_adherence_{m.group(1)}" if m else None
            if not tbl:
                continue
            stmt = {"filters": f"SELECT count(*) AS n FROM {tbl} WHERE {frag}",
                    "expressions": f"SELECT {frag} AS v, count(*) AS n FROM {tbl} GROUP BY 1 ORDER BY 2 DESC LIMIT 6",
                    "measures": f"SELECT {frag} AS v FROM {tbl} WHERE measurement_year = 2026"}[kind]
            out.append((f"{kind}: {s.get('display_name', '')[:60]}", stmt))
    for j in inst.get("join_specs", []):
        on = re.sub(r"--.*$", "", _join(j["sql"]), flags=re.M).strip()
        lt, rt = j["left"]["identifier"], j["right"]["identifier"]
        out.append((f"join {lt.split('.')[-1]} -> {rt.split('.')[-1]}",
                    f"SELECT count(*) AS n FROM {lt} JOIN {rt} ON {on}"))
    for e in inst.get("example_question_sqls", []):
        out.append((f"example: {_join(e.get('question'))[:60]}", _join(e["sql"]).rstrip().rstrip(";")))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--space-id", required=True)
    ap.add_argument("--out", required=True, help="directory for before/after JSON, diff and validation report")
    ap.add_argument("--warehouse", default="Serverless Starter Warehouse")
    ap.add_argument("--apply", action="store_true", help="write the migrated space back (external write)")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    w = WorkspaceClient(profile=args.profile)
    d = w.api_client.do("GET", f"/api/2.0/genie/spaces/{args.space_id}", query={"include_serialized_space": "true"})
    ss = json.loads(d["serialized_space"])

    wh = next(x.id for x in w.warehouses.list() if x.name == args.warehouse)

    def run(stmt: str):
        r = w.statement_execution.execute_statement(warehouse_id=wh, statement=stmt, wait_timeout="30s")
        while r.status.state.value in ("PENDING", "RUNNING"):
            time.sleep(2)
            r = w.statement_execution.get_statement(r.statement_id)
        if r.status.state.value != "SUCCEEDED":
            raise RuntimeError(r.status.error.message if r.status.error else r.status.state.value)
        cols = [c.name for c in r.manifest.schema.columns]
        return [dict(zip(cols, row)) for row in (r.result.data_array or [])] if r.result else []

    cols = {}
    for row in run(f"SELECT table_name, collect_set(column_name) AS c FROM {CATALOG}.information_schema.columns "
                   f"WHERE table_schema IN ('care_protocol', 'care_protocol_semantic') GROUP BY 1"):
        cols[row["table_name"]] = set(json.loads(row["c"]) if isinstance(row["c"], str) else row["c"])

    new, changes = migrate(ss, cols)
    # Every SQL statement is executed below, so a stale column in SQL fails validation on its own. This check covers the
    # prose (text instructions) and column configs, which nothing executes.
    prose = json.dumps([t.get("content") for t in new.get("instructions", {}).get("text_instructions", [])]
                       + [c.get("column_name") for t in new.get("data_sources", {}).get("tables", [])
                          for c in t.get("column_configs", [])])
    leftover = sorted(set(re.findall(r"\b(" + "|".join(REMOVED - {"status"}) + r")\b", prose))
                      | ({"status"} if re.search(r"status = 'NOT_MET'", prose) else set()))
    stale_loc = re.findall(r"care_protocol\.\w+_metrics", json.dumps(new))
    json.dump(ss, open(os.path.join(args.out, "before.json"), "w"), indent=1)
    json.dump(new, open(os.path.join(args.out, "after.json"), "w"), indent=1)
    with open(os.path.join(args.out, "diff.txt"), "w") as f:
        for where, old, nw in changes:
            f.write(f"### {where}\n")
            f.writelines(difflib.unified_diff(old.splitlines(True), nw.splitlines(True), "before", "after", n=0))
            f.write("\n")

    report, ok = [], True
    for label, stmt in _statements(new):
        try:
            rows = run(stmt)
            report.append(f"OK   {label} -> {json.dumps(rows[:3])[:160]}")
        except Exception as e:  # noqa: BLE001
            ok = False
            report.append(f"FAIL {label} -> {str(e)[:200]}")
    open(os.path.join(args.out, "validation.txt"), "w").write("\n".join(report) + "\n")
    print(f"{len(changes)} changed strings; leftover removed-column refs: {leftover or 'none'}; "
          f"leftover old view locations: {len(stale_loc)}")
    print("\n".join(report))
    if not ok or leftover or stale_loc:
        print("NOT APPLYING: validation failed or stale names remain.")
        sys.exit(1)
    if args.apply:
        w.api_client.do("PATCH", f"/api/2.0/genie/spaces/{args.space_id}",
                        body={"serialized_space": json.dumps(new)})
        print(f"applied to space {args.space_id}")
    else:
        print(f"dry run: review {args.out}/diff.txt, then re-run with --apply")


if __name__ == "__main__":
    main()
