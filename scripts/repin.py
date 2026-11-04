"""Run the canonical gold_queries.sql blocks for the 10 benchmark ids against the CURRENT ect data, so the
re-pin uses authoritative values (the closure_sql answer key IS gold_queries.sql). Prints id -> first row.

  PYTHONPATH=src DATABRICKS_CONFIG_PROFILE=ECT .venv/bin/python scripts/repin.py
"""
import re
import sys

sys.path.insert(0, "scripts")
from q import run  # noqa: E402

CAT, SCH, TSCH = "eli_test_classic_catalog", "care_protocol", "care_protocol_terminology"
IDS = ["kpi_gsd_rate", "sub_kidney", "med_on_statin", "vintage_egfr_2026", "proto_cardiorenal",
       "op_worst_clinic_annual"]  # numeric; definitions/path/drift handled separately

raw = open("src/benchmark/gold_queries.sql").read()
blocks = {}
for chunk in re.split(r"(?m)^-- @id:\s*", raw)[1:]:
    lines = chunk.splitlines()
    qid = lines[0].strip()
    sql = "\n".join(ln for ln in lines[1:] if not ln.lstrip().startswith("--")).strip().rstrip(";")
    if sql:
        blocks[qid] = sql.format(catalog=CAT, schema=SCH, tschema=TSCH)

for qid in IDS:
    sql = blocks.get(qid)
    if not sql:
        print(f"{qid:<24} (no gold query)")
        continue
    try:
        rows = run(sql)
        print(f"{qid:<24} {rows[0] if rows else '(no rows)'}")
    except Exception as e:  # noqa: BLE001
        print(f"{qid:<24} ERROR {type(e).__name__}: {str(e)[:120]}")
