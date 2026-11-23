"""Gold checks for the Clinical Study lab.

check_named: the hand-authored test participants' gold rows vs their hand-calculated oracles
(tests/fixtures/life_sciences/*.yaml). Local only: those participants are engine test inputs and are not in the demo
data (tests/test_ls_pipeline_local.py).

check_invariants: properties every correct run must have, over the generated population (no hand-authored rows).
Run by the deployed gate (scripts/ls_verify_gold.py) and the local pipeline test.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def check_named(results, candidates, population, vs, fixtures_dir) -> list[str]:
    """Named-fixture gold rows vs the hand oracles."""
    end = yaml.safe_load(open(Path(fixtures_dir) / "expected_endpoints.yaml", encoding="utf-8"))
    eli = yaml.safe_load(open(Path(fixtures_dir) / "expected_eligibility.yaml", encoding="utf-8"))
    tol = end["tolerance"]
    errs = []
    res = {(r.USUBJID, r.rule_version): r for r in results.where("USUBJID like '%-FX-%'").collect()}
    cand = {}
    for r in candidates.where("USUBJID like '%-FX-%'").collect():
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
    pop = {r.USUBJID: r for r in population.where("USUBJID like '%-FX-%'").collect()}
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


WINDOW = {"EP-A-WT24.R1": 7, "EP-A-WT24.R2": 14, "EP-B-WT24.R1": 10}  # rule_version.window_half_width_days


def check_invariants(results, population, vs) -> list[str]:
    """Properties of a correct run over the generated population (deployed gate + local test)."""
    from pyspark.sql import functions as F

    errs = []
    # unit lineage: the raw unit survives, and only genuinely unmappable raw units are flagged
    bad = vs.where("CPL_UNIT_MAPPING_STATUS = 'UNMAPPED_RAW_UNIT'").select("CPL_RAW_UNIT").distinct().collect()
    if {r.CPL_RAW_UNIT for r in bad} - {"st"}:
        errs.append(f"unexpected unmapped raw units: {[r.CPL_RAW_UNIT for r in bad]}")
    if vs.where("CPL_RAW_UNIT = 'lb' AND VSORRESU = 'LB'").limit(1).count() != 1:
        errs.append("raw unit 'lb' not preserved alongside CT 'LB'")
    # one result per FAS participant per rule version of their study
    fas = population.where("FASFL = 'Y'").select("USUBJID", "STUDYID")
    per = results.groupBy("USUBJID", "endpoint_version").count()
    dup = per.where("count > 1").limit(5).collect()
    if dup:
        errs.append(f"more than one result per participant/rule version: {[(r.USUBJID, r.endpoint_version) for r in dup]}")
    for ev in WINDOW:
        study = "CSL-" + ev.split("-")[1]
        missing = (fas.where(F.col("STUDYID") == study).join(
            results.where(F.col("endpoint_version") == ev), "USUBJID", "left_anti").count())
        if missing:
            errs.append(f"{ev}: {missing} FAS participants have no result")
    # a derived result is the arithmetic of its two observations, and its follow-up is inside the window
    d = results.where("result_status = 'DERIVED'")
    nulls = d.where("BASE IS NULL OR AVAL_FU IS NULL OR PCHG IS NULL").count()
    if nulls:
        errs.append(f"{nulls} DERIVED results lack BASE / AVAL_FU / PCHG")
    off = d.where(F.abs(F.col("PCHG") - (F.col("AVAL_FU") - F.col("BASE")) / F.col("BASE") * 100) > 1e-6).count()
    if off:
        errs.append(f"{off} DERIVED results where PCHG != (AVAL_FU - BASE) / BASE * 100")
    fu = vs.select(F.col("CPL_OBS_ID").alias("followup_observation_id"), F.to_date("VSDTC").alias("fu_date"))
    win = F.create_map(*[x for k, v in WINDOW.items() for x in (F.lit(k), F.lit(v))])
    outside = (d.join(fu, "followup_observation_id", "left")
               .where(F.abs(F.datediff("fu_date", F.col("followup_target_date"))) > win[F.col("endpoint_version")])
               .count())
    if outside:
        errs.append(f"{outside} DERIVED results whose follow-up is outside its rule version's window")
    # widening CSL-A's window (Amendment 1) can only add derivations, never lose one
    r1 = results.where("endpoint_version = 'EP-A-WT24.R1' AND result_status = 'DERIVED'").select("USUBJID")
    r2 = results.where("endpoint_version = 'EP-A-WT24.R2' AND result_status = 'DERIVED'").select("USUBJID")
    lost = r1.join(r2, "USUBJID", "left_anti").count()
    if lost:
        errs.append(f"{lost} participants derived under R1 but not under R2")
    return errs
