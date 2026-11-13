"""Pipeline transforms end to end on local Spark: raw EDC CSVs -> bronze -> SDTM-shaped silver -> gold.
The named participants' gold rows must equal the hand-authored oracles (same check as the post-deploy gate).

    PYSPARK_PYTHON=.venv/bin/python .venv/bin/python -I tests/test_ls_pipeline_local.py [landing_dir]
"""

from __future__ import annotations

import csv
import os
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))


def build(spark, landing: str) -> dict:
    from clinical_study import eligibility as el
    from clinical_study import gold, sdtm
    from clinical_study.standardize import load_registry

    gold.ship_by_value()
    std = ROOT / "src/standards/life_sciences"
    concepts = list(csv.DictReader(open(std / "kb_concept.csv", encoding="utf-8")))
    edges = list(csv.DictReader(open(std / "kb_edge.csv", encoding="utf-8")))
    onto, reg = el.Ontology(concepts, edges), load_registry()
    run_id = gold.execution_run_id(reg, onto.release, {"seed": "local"})
    tv = sdtm.terminology_version(concepts)
    labels = spark.createDataFrame(
        [(c["concept_id"], c["label"]) for c in concepts], "concept_id string, label string"
    )
    raw = {t: sdtm.read_raw(spark, landing, t) for t in sdtm.RAW_COLUMNS}
    dm = sdtm.dm(raw["subjects"], raw["ex"])
    vs = sdtm.vs(raw["vs"], dm, sdtm.vstest_labels(concepts, edges))
    ex = sdtm.ex(raw["ex"], dm)
    mh, cm = sdtm.mh(raw["mh"], labels), sdtm.cm(raw["cm"], labels)
    b = gold.subject_bundles(dm, vs, ex, mh, cm)
    elig = b.mapInPandas(gold.make_eligibility_fn(reg, onto, run_id), gold.ELIG_SCHEMA)
    pop = b.mapInPandas(gold.make_population_fn(reg, onto, run_id), gold.POP_SCHEMA)
    rb = gold.randomized_bundles(b)
    res = rb.mapInPandas(gold.make_result_fn(reg, tv, run_id), gold.RESULT_SCHEMA)
    cand = rb.mapInPandas(gold.make_candidate_fn(reg, tv, run_id), gold.CAND_SCHEMA)
    out = {
        "dm": dm,
        "vs": vs,
        "ex": ex,
        "mh": mh,
        "cm": cm,
        "eligibility": elig,
        "population": pop,
        "results": res,
        "candidates": cand,
    }
    out["amendment"] = gold.amendment_impact(res, cand)
    out["summary"] = gold.study_summary(res, pop)
    out["provenance"] = gold.provenance_edges(res, cand, reg, spark)
    out["tracers"] = gold.tracer_registry(spark)
    return out


def check_named(t: dict) -> list[str]:
    """Named-fixture gold rows vs the hand oracles."""
    end = yaml.safe_load(open(ROOT / "tests/fixtures/life_sciences/expected_endpoints.yaml"))
    eli = yaml.safe_load(open(ROOT / "tests/fixtures/life_sciences/expected_eligibility.yaml"))
    tol = end["tolerance"]
    errs = []
    res = {(r.USUBJID, r.rule_version): r for r in t["results"].where("USUBJID like '%-FX-%'").collect()}
    cand = {}
    for r in t["candidates"].where("USUBJID like '%-FX-%'").collect():
        cand[(r.USUBJID, r.rule_version, r.vsseq)] = r
    for u, rules in end["expected"].items():
        for rv, e in rules.items():
            if rv.endswith("_what_if"):
                continue
            r = res.get((u, rv))
            if r is None:
                errs.append(f"{u} {rv}: no gold row")
                continue
            if r.result_status != e["status"]:
                errs.append(f"{u} {rv}: {r.result_status} != {e['status']}")
            if "exclusion_reason" in e and r.exclusion_reason != e["exclusion_reason"]:
                errs.append(f"{u} {rv}: {r.exclusion_reason} != {e['exclusion_reason']}")
            if "value" in e and (r.PCHG is None or abs(r.PCHG - e["value"]) > tol):
                errs.append(f"{u} {rv}: PCHG {r.PCHG} != {e['value']}")
            if "followup" in e and r.followup_observation_id != f"{u}.WEIGHT.{e['followup']}":
                errs.append(f"{u} {rv}: followup {r.followup_observation_id}")
            for s, why in (e.get("reasons") or {}).items():
                c = cand.get((u, rv, int(s)))
                if c is None or c.reason != why:
                    errs.append(f"{u} {rv} vsseq {s}: {c.reason if c else None} != {why}")
    # unit lineage: the raw unit survives, and only genuinely unmappable raw units are flagged
    bad = (
        t["vs"]
        .where("CPL_UNIT_MAPPING_STATUS = 'UNMAPPED_RAW_UNIT'")
        .select("CPL_RAW_UNIT")
        .distinct()
        .collect()
    )
    if {r.CPL_RAW_UNIT for r in bad} - {"st"}:
        errs.append(f"unexpected unmapped raw units: {[r.CPL_RAW_UNIT for r in bad]}")
    if t["vs"].where("CPL_RAW_UNIT = 'lb' AND VSORRESU = 'LB'").limit(1).count() != 1:
        errs.append("raw unit 'lb' not preserved alongside CT 'LB'")
    pop = {r.USUBJID: r for r in t["population"].where("USUBJID like '%-FX-%'").collect()}
    for u, e in eli["expected"].items():
        p = pop[u]
        if p.rule_eligible != e["eligible"] or p.protocol_version != e["protocol_version"]:
            errs.append(f"{u}: eligible/protocol {p.rule_eligible}/{p.protocol_version}")
        for k, col in (("fas", "FASFL"), ("pps", "PPSFL")):
            if k in e and (getattr(p, col) == "Y") != e[k]:
                errs.append(f"{u}: {col} {getattr(p, col)} != {e[k]}")
        if "deviations" in e and [d.deviation for d in p.deviations] != [
            d["deviation"] for d in e["deviations"]
        ]:
            errs.append(f"{u}: deviations {[d.deviation for d in p.deviations]}")
    return errs


def main(landing: str | None = None) -> int:
    from pyspark.sql import SparkSession

    spark = (
        SparkSession.builder.master("local[4]")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    if landing is None:
        from clinical_study.generate import generate

        landing = tempfile.mkdtemp(prefix="ls_pipe_") + "/raw"
        generate(spark, landing, "small", 2026)
    t = build(spark, landing)
    errs = check_named(t)
    for e in errs:
        print("FAIL", e)
    r = (
        t["results"]
        .groupBy("STUDYID", "rule_version", "result_status")
        .count()
        .orderBy("STUDYID", "rule_version", "result_status")
    )
    for x in r.collect():
        print("  ", x.STUDYID, x.rule_version, x.result_status, x["count"])
    from pyspark.sql import functions as F

    a = t["amendment"].agg(F.sum(F.col("endpoint_became_derivable").cast("int"))).collect()[0][0]
    print(
        "   amendment rows:",
        t["amendment"].count(),
        "| became derivable under R2:",
        a,
        "| provenance edges:",
        t["provenance"].count(),
        "| VS unit status:",
        {x[0]: x[1] for x in t["vs"].groupBy("CPL_UNIT_MAPPING_STATUS").count().collect()},
    )
    print("PASS named fixtures (gold == oracle)" if not errs else f"FAILED {len(errs)}")
    return 1 if errs else 0


if __name__ == "__main__":
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
