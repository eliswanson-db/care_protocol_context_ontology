"""Gold oracle gate for the Clinical Study lab: named participants' gold rows vs the hand-authored oracles.

Shared by tests/test_ls_pipeline_local.py (local Spark) and scripts/ls_verify_gold.py (deployed tables), so
the deployed gate runs exactly the checks that passed locally. Oracles: tests/fixtures/life_sciences/*.yaml.
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
    # unit lineage: the raw unit survives, and only genuinely unmappable raw units are flagged
    bad = (
        vs.where("CPL_UNIT_MAPPING_STATUS = 'UNMAPPED_RAW_UNIT'").select("CPL_RAW_UNIT").distinct().collect()
    )
    if {r.CPL_RAW_UNIT for r in bad} - {"st"}:
        errs.append(f"unexpected unmapped raw units: {[r.CPL_RAW_UNIT for r in bad]}")
    if vs.where("CPL_RAW_UNIT = 'lb' AND VSORRESU = 'LB'").limit(1).count() != 1:
        errs.append("raw unit 'lb' not preserved alongside CT 'LB'")
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
