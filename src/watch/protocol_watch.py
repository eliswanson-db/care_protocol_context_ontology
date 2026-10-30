"""Weekly Protocol Watch — proactive, clinic-level drift detection over protocol-STEP adherence.

The "A Monday with Genie" hook: nobody asked, the watch noticed. A scheduled job scans gold_protocol_adherence
by CLINIC x month for Step-3 drift and appends to `protocol_watch_findings`. That table is the lineage spine
Genie One reasons over ("why did <clinic> slip in <month>?") and what a Genie One scheduled task reads to
deliver the weekly summary fast + grounded.

Why clinic-level, trailing-window: the care-behavior model (ADR-0012) puts the drift on ONE clinic after a
mid-year PCP handoff, and it's MASKED in the global/annual view (that clinic's annual rate sits mid-pack). A
global monthly scan misses it; a per-clinic trailing-3-month rate vs the peer baseline surfaces it. Serious,
not a toy threshold:
  * Right-censoring aware — a month is scored only once its 90-day follow-up window is fully observed.
  * Trailing 3-month window per clinic — enough N for a small clinic (~4 triggers/month) to be stable.
  * Peer baseline — pooled follow-up across all fully-observed clinic-months; flags a clinic that falls below it.

Append-only: each run writes an as-of snapshot (the watch log). Runs as a serverless spark_python_task.
Run AFTER measures. See resources/jobs.yml (protocol_watch).
"""
import argparse

from pyspark.sql import functions as F
from pyspark.sql.window import Window

DRIFT_PP = 0.15        # flag a clinic whose trailing rate is >= 15 pts below the peer baseline
MIN_TRIGGERS = 12      # small-N gate on the trailing-3-month window
FOLLOWUP_DAYS = 90
SEV_HIGH, SEV_MED = 0.30, 0.20


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--schema", default="care_protocol")
    ap.add_argument("--drift_pp", type=float, default=DRIFT_PP)
    ap.add_argument("--min_triggers", type=int, default=MIN_TRIGGERS)
    ap.add_argument("--followup_days", type=int, default=FOLLOWUP_DAYS)
    args = ap.parse_args()

    g = f"{args.catalog}.{args.schema}"
    findings_tbl = f"{g}.protocol_watch_findings"
    src = spark.table(f"{g}.gold_protocol_adherence")  # noqa: F821

    hz = src.agg(F.greatest(F.max("trigger_ts"), F.max("followup_ts")).cast("date").alias("horizon"))
    horizon_date = hz.collect()[0]["horizon"]

    monthly = (src
               .withColumn("month", F.date_trunc("month", "trigger_ts").cast("date"))
               .groupBy("clinic_id", "measurement_year", "month")
               .agg(F.count("*").alias("m_trig"),
                    F.sum(F.col("followup_within_90d").cast("int")).alias("m_follow"))
               .withColumn("month_end", F.last_day("month"))
               .crossJoin(hz)
               .withColumn("censored", F.date_add("month_end", args.followup_days) > F.col("horizon")))

    # Trailing 3-month window per clinic, and the clinic's OWN prior history (everything before that window).
    w_trail = Window.partitionBy("clinic_id").orderBy("month").rowsBetween(-2, 0)
    w_prior = Window.partitionBy("clinic_id").orderBy("month").rowsBetween(Window.unboundedPreceding, -3)
    trail = (monthly
             .withColumn("t_trig", F.sum("m_trig").over(w_trail))
             .withColumn("t_follow", F.sum("m_follow").over(w_trail))
             .withColumn("t_rate", F.col("t_follow") / F.col("t_trig"))
             .withColumn("baseline_n", F.sum("m_trig").over(w_prior))
             .withColumn("prior_follow", F.sum("m_follow").over(w_prior))
             .withColumn("baseline", F.col("prior_follow") / F.col("baseline_n")))

    # Peer baseline (context only, for the summary / NO_DRIFT row).
    brow = monthly.where(~F.col("censored")).agg(
        (F.sum("m_follow") / F.sum("m_trig")).alias("b"), F.sum("m_trig").alias("n")).collect()[0]
    peer_baseline, peer_n = (brow["b"] or 0.0), (brow["n"] or 0)

    # DRIFT = a clinic whose recent trailing rate fell vs the clinic's OWN prior history (a CHANGE), not merely
    # a clinic that is persistently below peers. This isolates the mid-year disruption from steady low performers.
    drift = (trail.where(~F.col("censored"))
             .where((F.col("t_trig") >= args.min_triggers) & (F.col("baseline_n") >= args.min_triggers))
             .withColumn("delta", F.col("baseline") - F.col("t_rate"))
             .where(F.col("delta") >= F.lit(args.drift_pp))
             .withColumn("finding_type", F.lit("CLINIC_STEP_DRIFT"))
             .withColumn("severity", F.when(F.col("delta") >= SEV_HIGH, F.lit("HIGH"))
                         .when(F.col("delta") >= SEV_MED, F.lit("MEDIUM")).otherwise(F.lit("LOW")))
             .withColumn("narrative", F.concat(
                 F.lit("Clinic "), F.col("clinic_id"), F.lit(": protocol Step-3 adherence in the 3 months ending "),
                 F.col("month").cast("string"), F.lit(" fell to "),
                 F.round(F.col("t_rate") * 100, 0).cast("int").cast("string"), F.lit("% ("),
                 F.col("t_follow").cast("string"), F.lit("/"), F.col("t_trig").cast("string"), F.lit("), "),
                 F.round(F.col("delta") * 100, 0).cast("int").cast("string"), F.lit(" pts below this clinic's own prior "),
                 F.round(F.col("baseline") * 100, 0).cast("int").cast("string"), F.lit("% (peer baseline "),
                 F.lit(round(peer_baseline * 100)).cast("string"),
                 F.lit("%). Investigate staffing / PCP changes / order-set handoff at this clinic."))))

    cols = ["finding_type", "severity", "clinic_id", "measure_id", "measurement_year", "month",
            "t_trig", "t_follow", "t_rate", "baseline", "baseline_n", "delta", "censored", "narrative"]
    drift = drift.withColumn("measure_id", F.lit("PROTO_STEP3")).select(*cols)
    n = drift.count()

    if n == 0:
        drift = (spark.range(1).select(  # noqa: F821
            F.lit("NO_DRIFT").alias("finding_type"), F.lit("NONE").alias("severity"),
            F.lit(None).cast("string").alias("clinic_id"), F.lit("PROTO_STEP3").alias("measure_id"),
            F.lit(src.agg(F.max("measurement_year")).collect()[0][0]).cast("int").alias("measurement_year"),
            F.lit(None).cast("date").alias("month"), F.lit(None).cast("long").alias("t_trig"),
            F.lit(None).cast("long").alias("t_follow"), F.lit(None).cast("double").alias("t_rate"),
            F.lit(peer_baseline).alias("baseline"), F.lit(peer_n).alias("baseline_n"),
            F.lit(None).cast("double").alias("delta"), F.lit(False).alias("censored"),
            F.concat(F.lit("No clinic Step-3 drift: every clinic held within "),
                     F.lit(str(round(args.drift_pp * 100))), F.lit(" pts of its own prior baseline this run (peer baseline "),
                     F.round(F.lit(peer_baseline) * 100, 0).cast("int").cast("string"),
                     F.lit("%).")).alias("narrative")).select(*cols))

    out = (drift.withColumn("as_of", F.current_timestamp())
           .withColumn("horizon_date", F.lit(horizon_date))
           .withColumn("drift_threshold_pp", F.lit(args.drift_pp))
           .withColumn("min_triggers", F.lit(args.min_triggers)))
    out.write.format("delta").mode("append").saveAsTable(findings_tbl)
    print(f"protocol_watch: appended {out.count()} row(s) to {findings_tbl} "
          f"(CLINIC_STEP_DRIFT this run: {n}; peer baseline={peer_baseline:.3f}, n={peer_n}, horizon={horizon_date}).")
    out.orderBy(F.col("delta").desc_nulls_last()).show(50, truncate=False)


if __name__ == "__main__":
    main()
