"""Bundle task: build mondo/medrt_class/mesh/bc closures in clinical_study_standards (driver-side BFS).

Validates each closure (unique keys, self rows, every direct edge at depth 1) BEFORE publishing; an invalid
closure fails the task and is never written.
"""

import argparse
import sys

from pyspark.sql import SparkSession

PAIRS = {
    "mondo_hier": "mondo_closure",
    "medrt_class_hier": "medrt_class_closure",
    "mesh_hier": "mesh_closure",
    "bc_hier": "bc_closure",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--schema", default="clinical_study_standards")
    ap.add_argument("--src_dir", required=True)
    a = ap.parse_args()
    sys.path.insert(0, a.src_dir)
    from clinical_study.closure import closure_rows, validate

    spark = SparkSession.builder.getOrCreate()
    t = f"{a.catalog}.{a.schema}"
    for hier_t, clo_t in PAIRS.items():
        hier = [r.asDict() for r in spark.table(f"{t}.{hier_t}").collect()]
        rows = closure_rows(hier)
        errs = validate(hier, rows)
        if errs:
            raise SystemExit(f"{clo_t} invalid, not published: {errs}")
        schema = (
            "ancestor_code string, ancestor_name string, descendant_code string, descendant_name string, "
            "depth int, relationship_path string"
        )
        spark.createDataFrame(rows, schema).write.mode("overwrite").option(
            "overwriteSchema", "true"
        ).saveAsTable(f"{t}.{clo_t}")
        spark.sql(
            f"COMMENT ON TABLE {t}.{clo_t} IS 'Transitive closure of {hier_t} (shortest distance; depth 0 = "
            f"self). One equality selects a whole subtree: WHERE ancestor_code = X. Derived from kb_edge "
            f"direct edges; routes not kept (a traversal question for the graph).'"
        )
        print(f"  {t}.{clo_t}: {len(rows)} rows from {len(hier)} edges")


if __name__ == "__main__":
    main()
