"""Run Synthea (Java) on the classic driver, export CSV, load raw tables to Delta.

Classic single-node cluster only (serverless can't run arbitrary JVM/JAR). JDK 17 is selected on the job
cluster via the JNAME env var. Writes raw_synthea_* tables into <catalog>.<schema>.
"""
import argparse
import glob
import os
import shutil
import subprocess

from pyspark.sql import SparkSession

RAW_TABLES = ["patients", "encounters", "conditions", "observations", "medications", "procedures", "immunizations"]


def find_java() -> str:
    for pat in ("/usr/lib/jvm/*17*/bin/java", "/usr/lib/jvm/*11*/bin/java"):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[0]
    return "java"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", default="eli_test_classic_catalog")
    p.add_argument("--schema", default="care_protocol")
    p.add_argument("--volume_dir", default="/Volumes/eli_test_classic_catalog/care_protocol/synthea")
    p.add_argument("--population", default="500")
    p.add_argument("--seed", default="20261029")
    p.add_argument("--state", default="Massachusetts")
    args = p.parse_args()

    jar = os.path.join(args.volume_dir, "synthea-with-dependencies.jar")
    if not os.path.exists(jar):
        raise FileNotFoundError(f"Synthea JAR not staged at {jar} — run stage_synthea first")

    outdir = "/local_disk0/synthea_output"
    if os.path.exists(outdir):
        shutil.rmtree(outdir)
    os.makedirs(outdir, exist_ok=True)

    java = find_java()
    subprocess.run([java, "-version"], check=False)
    cmd = [
        java, "-jar", jar,
        "-p", args.population, "-s", args.seed,
        "--exporter.baseDirectory", outdir,
        "--exporter.csv.export", "true",
        "--exporter.fhir.export", "false",
        "--exporter.hospital.fhir.export", "false",
        "--exporter.practitioner.fhir.export", "false",
        "--generate.only_alive_patients", "true",
        args.state,
    ]
    print("running:", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=outdir)

    spark = SparkSession.builder.getOrCreate()
    csv_dir = os.path.join(outdir, "csv")
    for name in RAW_TABLES:
        f = os.path.join(csv_dir, f"{name}.csv")
        if not os.path.exists(f):
            print(f"skip missing {f}")
            continue
        df = spark.read.option("header", True).option("inferSchema", True).csv(f"file:{f}")
        fqn = f"{args.catalog}.{args.schema}.raw_synthea_{name}"
        df.write.mode("overwrite").option("overwriteSchema", True).saveAsTable(fqn)
        print(f"loaded {df.count():>6} rows -> {fqn}")


if __name__ == "__main__":
    main()
