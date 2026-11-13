"""Generator integration test (local Spark; skips if pyspark/dbldatagen are unavailable). ~1-2 minutes.

1. Determinism: two runs with different shuffle partitioning produce byte-identical CSVs.
2. Coherence: the pipeline's independent eligibility logic agrees with the EDC screening outcome, except for
   the planted cases (non-protocol screen failures, and participants enrolled in error).
3. The planted story is visible: SITE-118's late Week 24 visits leave endpoints missing under R1 and are
   recovered by R2; the drug arm loses more weight than placebo; on-treatment GLP-1 deviations sit in
   placebo at US sites.
4. Named fixtures land verbatim.

    PYSPARK_PYTHON=.venv/bin/python .venv/bin/python -I tests/test_ls_generator.py
"""

from __future__ import annotations

import collections
import csv
import glob
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
PY = sys.executable

RUNNER = """
import sys, json
sys.path.insert(0, {src!r})
from pyspark.sql import SparkSession
spark = (SparkSession.builder.master("local[4]").config("spark.ui.enabled", "false")
         .config("spark.sql.shuffle.partitions", sys.argv[2])
         .config("spark.sql.session.timeZone", "UTC").getOrCreate())
spark.sparkContext.setLogLevel("ERROR")
from clinical_study.generate import generate
generate(spark, sys.argv[1], "small", 2026)
"""

_CACHE: dict[str, str] = {}


def _have_spark() -> bool:
    try:
        import dbldatagen  # noqa: F401
        import pyspark  # noqa: F401
    except ImportError:
        return False
    return True


def _run(shuffle: str) -> str:
    if shuffle in _CACHE:
        return _CACHE[shuffle]
    out = tempfile.mkdtemp(prefix=f"ls_gen_{shuffle}_")
    script = Path(out) / "runner.py"
    script.write_text(RUNNER.format(src=str(ROOT / "src")))
    env = {**os.environ, "PYSPARK_PYTHON": PY}
    r = subprocess.run(
        [PY, "-I", str(script), f"{out}/data", shuffle],
        env=env,
        capture_output=True,
        text=True,
        cwd=out,
        timeout=900,
    )
    assert r.returncode == 0, r.stderr[-3000:]
    _CACHE[shuffle] = f"{out}/data"
    return _CACHE[shuffle]


def _read(d: str, table: str) -> list[dict]:
    (f,) = glob.glob(f"{d}/{table}/*.csv")
    with open(f, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _digest(d: str) -> dict[str, str]:
    return {
        t: hashlib.sha256(Path(glob.glob(f"{d}/{t}/*.csv")[0]).read_bytes()).hexdigest()
        for t in ("subjects", "vs", "ex", "mh", "cm", "ds", "sv")
    }


def test_deterministic_across_partitioning():
    if not _have_spark():
        print("SKIP (no pyspark/dbldatagen)")
        return
    a, b = _digest(_run("8")), _digest(_run("3"))
    assert a == b, {t: (a[t][:8], b[t][:8]) for t in a if a[t] != b[t]}


def _participants(d: str) -> dict[str, dict]:
    from clinical_study.standardize import ct_unit, obs_id

    subj = {
        r["usubjid"]: {"dm": r, "vs": [], "ex": [], "mh": [], "cm": [], "height": None}
        for r in _read(d, "subjects")
    }
    for r in _read(d, "vs"):
        p = subj[r["usubjid"]]
        if r["vstestcd"] == "WEIGHT":
            p["vs"].append(
                {
                    "obs_id": obs_id(r["usubjid"], "WEIGHT", r["vsseq"]),
                    "vsseq": int(r["vsseq"]),
                    "visit": r["visit"],
                    "vsdtc": r["vsdtc"],
                    "vsorres": r["vsorres"],
                    "vsorresu": ct_unit(r["vsorresu"]),
                    "vsstat": r["vsstat"] or None,
                }
            )
        elif r["vstestcd"] == "HEIGHT":
            p["height"] = {
                "obs_id": r["record_id"],
                "vsorres": r["vsorres"],
                "vsorresu": ct_unit(r["vsorresu"]),
            }
    for r in _read(d, "ex"):
        subj[r["usubjid"]]["ex"].append({"exstdtc": r["exstdtc"], "exdose": float(r["exdose"])})
    for r in _read(d, "mh"):
        subj[r["usubjid"]]["mh"].append({"mh_id": r["record_id"], "mondo_id": r["mhdecod_mondo"]})
    for r in _read(d, "cm"):
        subj[r["usubjid"]]["cm"].append(
            {
                "cm_id": r["record_id"],
                "rxnorm": r["cmdecod_rxnorm"],
                "cmstdtc": r["cmstdtc"],
                "cmendtc": r["cmendtc"],
            }
        )
    return subj


def test_coherence_story_and_fixtures():
    if not _have_spark():
        print("SKIP (no pyspark/dbldatagen)")
        return
    from clinical_study import eligibility as el
    from clinical_study import engine
    from clinical_study.standardize import load_registry

    d = _run("8")
    reg, onto = load_registry(), el.default_ontology()
    P = _participants(d)
    mismatch = collections.Counter()
    unexpected = []
    results = collections.defaultdict(dict)
    for u, p in P.items():
        dm = p["dm"]
        if dm["named_fixture"] == "Y":
            continue
        sv = el.screening_vitals(p["vs"], p["height"])
        a = el.assess(
            {
                "study_id": dm["study_id"],
                "usubjid": u,
                "screening_date": dm["screening_date"],
                "age": int(dm["age"]),
            },
            sv,
            p["mh"],
            p["cm"],
            reg,
            onto,
        )
        rnd = dm["screen_outcome"] == "RANDOMIZED"
        if a.eligible and not rnd:
            if dm["screen_fail_reason"] in ("WITHDRAWAL BY SUBJECT", "LAB EXCLUSION", "LOST TO FOLLOW-UP"):
                mismatch["eligible_but_nonprotocol_screen_fail"] += 1
            else:
                unexpected.append((u, "rule-eligible but screen failed", dm["screen_fail_reason"]))
        elif rnd and not a.eligible:
            mismatch["enrolled_in_error"] += 1
            failed = [c for c in a.criteria if c.outcome in ("NOT_MET", "TRIGGERED", "NOT_EVALUABLE")]
            # planted errors are exclusionary history only (ERROR_ENROLLED profile); anything else is a bug
            if not failed or any(c.criterion_id not in ("EXC-MH", "EXC-CI") for c in failed):
                unexpected.append(
                    (
                        u,
                        "enrolled in error for an unplanted reason",
                        [(c.criterion_id, c.outcome, c.detail) for c in failed],
                    )
                )
        elif not a.eligible and not rnd:
            mismatch["consistent_screen_fail"] += 1
        if rnd:
            ep_id = "EP-A-WT24" if dm["study_id"] == "CSL-A" else "EP-B-WT24"
            for rv in reg["endpoints"][ep_id]["rule_versions"]:
                r = engine.derive(
                    {"study_id": dm["study_id"], "usubjid": u, "randomized": True},
                    p["vs"],
                    p["ex"],
                    endpoint_id=ep_id,
                    endpoint=reg["endpoints"][ep_id],
                    rule_version=rv,
                    terminology_version="t",
                )
                results[u][rv] = r
    assert not unexpected, unexpected[:10]
    n_rand = sum(
        1 for p in P.values() if p["dm"]["screen_outcome"] == "RANDOMIZED" and p["dm"]["named_fixture"] == "N"
    )
    assert 0 < mismatch["enrolled_in_error"] <= max(3, 0.02 * n_rand), mismatch
    print("  eligibility reconciliation:", dict(mismatch), "randomized:", n_rand)

    # --- story: SITE-118 late Week 24 -> missing under R1, recovered by R2
    a_ids = [u for u in results if P[u]["dm"]["study_id"] == "CSL-A"]
    site = {u: P[u]["dm"]["site_id"] for u in a_ids}
    recovered = [
        u
        for u in a_ids
        if results[u]["R1"].result_status != engine.DERIVED
        and results[u]["R2"].result_status == engine.DERIVED
    ]
    by_site = collections.Counter(site[u] for u in recovered)
    n118 = sum(1 for u in a_ids if site[u] == "SITE-118")
    print(
        f"  CSL-A recovered by Amendment 1: {len(recovered)} "
        f"(SITE-118: {by_site['SITE-118']} of {n118} enrolled)"
    )
    assert recovered and by_site["SITE-118"] >= 0.5 * len(recovered), by_site.most_common(5)

    # --- story: treatment effect direction (descriptive only)
    arm = {u: P[u]["dm"]["armcd"] for u in results}
    for study, rv in (("CSL-A", "R2"), ("CSL-B", "R1")):
        means = {}
        for a_ in ("CSL101", "PBO"):
            v = [
                results[u][rv].analysis_value
                for u in results
                if P[u]["dm"]["study_id"] == study
                and arm[u] == a_
                and results[u][rv].result_status == engine.DERIVED
            ]
            means[a_] = sum(v) / len(v) if v else None
        print(f"  {study} {rv} mean % change: {means}")
        assert means["CSL101"] < means["PBO"] - 4, means

    # --- story: on-treatment GLP-1 deviations concentrate in placebo at US sites
    dev = collections.Counter()
    for u in results:
        p = P[u]
        first, _ = engine._first_dose(p["ex"])
        devs = el.on_treatment_deviations(first.day if first else None, None, p["cm"], reg, onto)
        if devs:
            dev[(p["dm"]["armcd"], p["dm"]["country"] == "US")] += 1
    print("  on-treatment GLP-1 deviations (arm, US):", dict(dev))
    assert dev[("PBO", True)] >= max(dev.values()) and sum(dev.values()) > 0, dev

    # --- named fixtures landed verbatim
    from clinical_study.standardize import load_named

    for n in load_named():
        u = n["participant"]["usubjid"]
        assert u in P, u
        got = sorted((w["vsseq"], w["vsdtc"], w["vsorres"], w["vsorresu"]) for w in P[u]["vs"])
        want = sorted((w["vsseq"], w["vsdtc"], w["vsorres"], w["vsorresu"]) for w in n["observations"])
        assert got == want, u


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                fails += 1
                print(f"FAIL {name}:\n{e}")
    sys.exit(1 if fails else 0)
