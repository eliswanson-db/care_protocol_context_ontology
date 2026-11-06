"""Build a transitive closure table from an adjacency (hierarchy) table.

Direct edges are the source of truth; the closure is derived (the "Closure-Table Retrieval on Databricks" review,
2026-11-06). Run as a bundle job task (resources/jobs.yml: setup), NOT ad-hoc SQL.

Contract: one row per (ancestor_code, descendant_code) at the SHORTEST unweighted distance, including a depth-0 self
row for every node. Built breadth-first with a deduplicated frontier (seed self pairs; extend the frontier by one
edge; drop pairs already discovered; stop when the frontier is empty), so a node with several parents (a DAG) gets
one row per ancestor rather than one per route. Alternate routes are deliberately NOT kept: a closure answers
"is X under Y, and how far", not "by which path" -- that is a traversal question (see the graph runner).

Relationships: pass --relationship to build a closure over one edge type only (e.g. RxNorm class_member vs
ingredient_of). Without it, every edge is used and each row records the relationship sequence it crossed
(`relationship_path`, e.g. 'class_member>ingredient_of' for drug class -> clinical drug), so a composed closure is
explicit rather than silently mixing relationships.

Defaults build the ICD-10-CM closure (icd10_hier -> icd10_closure).
"""
import argparse

from pyspark.sql import SparkSession, functions as F


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", default="eli_test_classic_catalog")
    p.add_argument("--schema", default="care_protocol_terminology")
    p.add_argument("--hier_table", default="icd10_hier", help="Adjacency table (code, parent_code, name[, relationship]).")
    p.add_argument("--closure_table", default="icd10_closure", help="Closure table to write.")
    p.add_argument("--label", default="icd10_hier", help="Name used in the table comment.")
    p.add_argument("--relationship", default="", help="Only follow edges of this relationship (default: all).")
    p.add_argument("--max_depth", type=int, default=50)
    args = p.parse_args()

    spark = SparkSession.builder.getOrCreate()
    t = f"{args.catalog}.{args.schema}"
    hier = spark.table(f"{t}.{args.hier_table}")
    has_rel = "relationship" in hier.columns
    rel = F.col("relationship") if has_rel else F.lit(None).cast("string")
    edges = hier.where(F.col("parent_code").isNotNull()).select(
        F.col("parent_code").alias("a"), F.col("code").alias("d"), rel.alias("rel"))
    if args.relationship:
        if not has_rel:
            raise SystemExit(f"{args.hier_table} has no relationship column")
        edges = edges.where(F.col("rel") == args.relationship)
    edges = edges.distinct()

    # Nodes in scope: every code (as child or parent) that the selected edges touch, plus all codes when unfiltered.
    names = hier.select("code", "name").where(F.col("code").isNotNull()).dropDuplicates(["code"])
    if args.relationship:
        touched = edges.select(F.col("a").alias("code")).union(edges.select(F.col("d").alias("code"))).distinct()
        nodes = touched.join(names, "code", "left")
    else:
        nodes = names

    seen = nodes.select(F.col("code").alias("a"), F.col("code").alias("d"), F.lit(0).alias("depth"),
                        F.lit("").alias("relationship_path"))
    frontier = seen
    depth = 0
    while depth < args.max_depth:
        nxt = (frontier.alias("f").join(edges.alias("e"), F.col("f.d") == F.col("e.a"))
               .select(F.col("f.a").alias("a"), F.col("e.d").alias("d"), F.lit(depth + 1).alias("depth"),
                       F.when(F.col("f.relationship_path") == "", F.coalesce(F.col("e.rel"), F.lit("")))
                        .otherwise(F.concat_ws(">", F.col("f.relationship_path"), F.coalesce(F.col("e.rel"), F.lit(""))))
                        .alias("relationship_path"))
               .dropDuplicates(["a", "d"])
               .join(seen.select("a", "d"), ["a", "d"], "left_anti"))
        if nxt.limit(1).count() == 0:
            break
        seen = seen.unionByName(nxt)
        frontier = nxt
        depth += 1
    else:
        raise SystemExit(f"closure did not converge within {args.max_depth} levels (cycle or very deep hierarchy); "
                         f"not publishing a truncated closure")

    closure = (seen
               .join(names.withColumnRenamed("code", "a").withColumnRenamed("name", "ancestor_name"), "a", "left")
               .join(names.withColumnRenamed("code", "d").withColumnRenamed("name", "descendant_name"), "d", "left")
               .select(F.col("a").alias("ancestor_code"), "ancestor_name",
                       F.col("d").alias("descendant_code"), "descendant_name", "depth",
                       *([F.col("relationship_path")] if has_rel else [])))

    # Validate before publishing: one row per key, a self row per node, every selected direct edge at depth 1.
    keys = closure.groupBy("ancestor_code", "descendant_code").count().where("count > 1").count()
    missing_edges = (edges.join(closure.where("depth = 1"),
                                (edges.a == closure.ancestor_code) & (edges.d == closure.descendant_code), "left_anti")
                     .count())
    if keys or missing_edges:
        raise SystemExit(f"closure invalid: {keys} duplicate keys, {missing_edges} direct edges not at depth 1")

    fqn = f"{t}.{args.closure_table}"
    closure.write.mode("overwrite").option("overwriteSchema", True).saveAsTable(fqn)
    scope = f" ({args.relationship} edges only)" if args.relationship else ""
    spark.sql(
        f"COMMENT ON TABLE {fqn} IS 'Transitive closure of {args.label}{scope}: one row per ancestor/descendant pair "
        f"at the shortest distance (depth 0 = self). Select a whole subtree with one equality (WHERE ancestor_code=X). "
        f"Derived from the direct edges by build_closure.py; routes are not kept.'")
    print(f"closure rows: {closure.count()} -> {fqn}")


if __name__ == "__main__":
    main()
