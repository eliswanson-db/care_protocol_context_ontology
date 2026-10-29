"""Build the ICD-10-CM transitive closure (icd10_closure) from icd10_hier.

Iterative (BFS) build — portable across any Spark, no recursive-CTE dependency. Run as a bundle job task
(resources/jobs.yml: setup -> build_closure), NOT ad-hoc SQL. Writes <catalog>.<schema>.icd10_closure:
one row per ancestor->descendant pair (incl. depth-0 self rows), so a whole subtree = one equality.
"""
import argparse

from pyspark.sql import SparkSession, functions as F


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", default="eli_test_classic_catalog")
    p.add_argument("--schema", default="care_protocol_terminology")
    args = p.parse_args()

    spark = SparkSession.builder.getOrCreate()
    t = f"{args.catalog}.{args.schema}"
    hier = spark.table(f"{t}.icd10_hier").select("code", "parent_code", "name")

    edges = hier.where(F.col("parent_code").isNotNull()).select(
        F.col("parent_code").alias("a"), F.col("code").alias("d"))
    pairs = hier.select(F.col("code").alias("a"), F.col("code").alias("d"), F.lit(0).alias("depth"))
    cur = edges.select("a", "d", F.lit(1).alias("depth"))

    depth = 1
    while depth <= 20 and cur.limit(1).count() > 0:
        pairs = pairs.unionByName(cur)
        cur = (cur.alias("c").join(edges.alias("e"), F.col("c.d") == F.col("e.a"))
               .select(F.col("c.a").alias("a"), F.col("e.d").alias("d"), F.lit(depth + 1).alias("depth")))
        depth += 1

    names = hier.select("code", "name")
    closure = (pairs
               .join(names.withColumnRenamed("code", "a").withColumnRenamed("name", "ancestor_name"), "a")
               .join(names.withColumnRenamed("code", "d").withColumnRenamed("name", "descendant_name"), "d")
               .select(F.col("a").alias("ancestor_code"), "ancestor_name",
                       F.col("d").alias("descendant_code"), "descendant_name", "depth"))

    fqn = f"{t}.icd10_closure"
    closure.write.mode("overwrite").option("overwriteSchema", True).saveAsTable(fqn)
    spark.sql(
        f"COMMENT ON TABLE {fqn} IS 'Transitive closure of icd10_hier; select a whole subtree with "
        f"one equality (WHERE ancestor_code=X). Built once by build_closure.py.'")
    print(f"closure rows: {closure.count()} -> {fqn}")


if __name__ == "__main__":
    main()
