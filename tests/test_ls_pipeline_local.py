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
    blob = gold.pack_kb(concepts, edges)
    fns = {
        "eligibility": gold.make_eligibility_fn(reg, blob, run_id),
        "population": gold.make_population_fn(reg, blob, run_id),
        "result": gold.make_result_fn(reg, tv, run_id),
        "candidate": gold.make_candidate_fn(reg, tv, run_id),
    }
    # serverless broadcasts (and then fails on) any pickled UDF over ~1 MB: keep every closure well under it
    from pyspark import cloudpickle

    sizes = {k: len(cloudpickle.dumps(f)) for k, f in fns.items()}
    print("   UDF closure bytes:", sizes)
    assert max(sizes.values()) < gold.UDF_PAYLOAD_LIMIT, sizes
    elig = b.mapInPandas(fns["eligibility"], gold.ELIG_SCHEMA)
    pop = b.mapInPandas(fns["population"], gold.POP_SCHEMA)
    rb = gold.randomized_bundles(b)
    res = rb.mapInPandas(fns["result"], gold.RESULT_SCHEMA)
    cand = rb.mapInPandas(fns["candidate"], gold.CAND_SCHEMA)
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
    from clinical_study.verify import check_named as _check

    return _check(
        t["results"], t["candidates"], t["population"], t["vs"], ROOT / "tests/fixtures/life_sciences"
    )


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
