"""Endpoint engine vs the hand-authored oracle (tests/fixtures/life_sciences/expected_endpoints.yaml).

Deterministic, no workspace:  python3 -I tests/test_ls_engine.py   (or pytest tests/test_ls_engine.py)
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinical_study import engine  # noqa: E402
from clinical_study.standardize import load_named, load_registry  # noqa: E402

ORACLE = yaml.safe_load(open(ROOT / "tests/fixtures/life_sciences/expected_endpoints.yaml", encoding="utf-8"))
TOL = ORACLE["tolerance"]
REG = load_registry()
NAMED = {n["participant"]["usubjid"]: n for n in load_named()}
ENDPOINT_FOR = {"CSL-A": "EP-A-WT24", "CSL-B": "EP-B-WT24"}


def run(usubjid: str, rule: str, endpoint_id: str | None = None, endpoint: dict | None = None):
    n = NAMED[usubjid]
    eid = endpoint_id or ENDPOINT_FOR[n["participant"]["study_id"]]
    return engine.derive(
        n["participant"],
        n["observations"],
        n["exposures"],
        endpoint_id=eid,
        endpoint=endpoint or REG["endpoints"][eid],
        rule_version=rule,
        terminology_version="test",
        execution_run_id="test-run",
    )


def check(res, exp: dict, label: str) -> list[str]:
    errs = []
    seq = {c.obs_id: c.vsseq for c in res.candidates}
    by_seq = {c.vsseq: c for c in res.candidates}
    if res.result_status != exp["status"]:
        errs.append(f"{label}: status {res.result_status} != {exp['status']} ({res.exclusion_reason})")
    if "exclusion_reason" in exp and res.exclusion_reason != exp["exclusion_reason"]:
        errs.append(f"{label}: reason {res.exclusion_reason!r} != {exp['exclusion_reason']!r}")
    if "population" in exp and res.analysis_population_status != exp["population"]:
        errs.append(f"{label}: population {res.analysis_population_status} != {exp['population']}")
    if "baseline" in exp and sorted(seq[o] for o in res.baseline_observation_ids) != sorted(exp["baseline"]):
        errs.append(
            f"{label}: baseline {[seq[o] for o in res.baseline_observation_ids]} != {exp['baseline']}"
        )
    if "followup" in exp and (seq.get(res.followup_observation_id) != exp["followup"]):
        errs.append(f"{label}: followup {seq.get(res.followup_observation_id)} != {exp['followup']}")
    for k, attr in (
        ("value", "analysis_value"),
        ("baseline_kg", "baseline_value"),
        ("followup_kg", "followup_value"),
    ):
        if k in exp:
            got = getattr(res, attr)
            if got is None or abs(got - exp[k]) > TOL:
                errs.append(f"{label}: {attr} {got!r} != {exp[k]!r}")
    if "display" in exp and res.analysis_value_display != exp["display"]:
        errs.append(f"{label}: display {res.analysis_value_display} != {exp['display']}")
    for s, r in (exp.get("reasons") or {}).items():
        if by_seq[int(s)].reason != r:
            errs.append(f"{label}: vsseq {s} reason {by_seq[int(s)].reason} != {r}")
    if res.result_status == engine.DERIVED:
        if res.analysis_value is None or not res.baseline_observation_ids or not res.followup_observation_id:
            errs.append(f"{label}: DERIVED without full provenance")
    return errs


def test_every_named_participant_matches_the_oracle():
    errs = []
    assert set(ORACLE["expected"]) == set(NAMED), set(ORACLE["expected"]) ^ set(NAMED)
    for usubjid, rules in ORACLE["expected"].items():
        for rule, exp in rules.items():
            if rule.endswith("_what_if"):
                continue
            errs += check(run(usubjid, rule), exp, f"{usubjid} {rule}")
    assert not errs, "\n".join(errs)


def test_all_twenty_edge_cases_are_present():
    assert sorted(n["edge_case"] for n in NAMED.values()) == list(range(1, 21))


def test_every_candidate_gets_exactly_one_decision_and_a_reason():
    for usubjid, n in NAMED.items():
        for rule in ORACLE["expected"][usubjid]:
            if rule.endswith("_what_if"):
                continue
            res = run(usubjid, rule)
            assert len(res.candidates) == len(n["observations"])
            for c in res.candidates:
                assert c.decision in (engine.SELECTED, engine.ELIGIBLE_NOT_SELECTED, engine.EXCLUDED)
                assert c.reason, (usubjid, rule, c)


def test_cross_study_same_data_under_study_a_definition_differs():
    """FX-18's data under Study A's R1 rule gives a different result; the endpoints are not equivalent."""
    exp = ORACLE["expected"]["CSL-B-FX-18"]["A_R1_what_if"]
    res = run("CSL-B-FX-18", "R1", endpoint_id="EP-A-WT24", endpoint=REG["endpoints"]["EP-A-WT24"])
    assert not check(res, exp, "FX-18 under A R1")
    assert abs(res.analysis_value - ORACLE["expected"]["CSL-B-FX-18"]["R1"]["value"]) > 0.1


def test_amendment_1_impact_matches_hand_derived_lists():
    exp = ORACLE["amendment_1_impact"]
    got = {k: [] for k in exp}
    for usubjid, n in sorted(NAMED.items()):
        if n["participant"]["study_id"] != "CSL-A":
            continue
        r1, r2 = run(usubjid, "R1"), run(usubjid, "R2")
        if r1.result_status != engine.DERIVED and r2.result_status == engine.DERIVED:
            got["endpoint_became_derivable"].append(usubjid)
        if r1.followup_observation_id != r2.followup_observation_id:
            got["selected_followup_changed"].append(usubjid)
        elig = lambda r: {c.obs_id for c in r.candidates if c.decision != engine.EXCLUDED}  # noqa: E731
        if elig(r1) != elig(r2):
            got["eligible_candidates_changed"].append(usubjid)
        if r1.analysis_value != r2.analysis_value:
            got["endpoint_value_changed"].append(usubjid)
    assert got == exp, got


def test_unapproved_rule_never_executes():
    """A candidate document assertion (e.g. a draft +/-21-day window) must not run, even if loaded."""
    ep = copy.deepcopy(REG["endpoints"]["EP-A-WT24"])
    ep["rule_versions"]["R3-DRAFT"] = {
        **copy.deepcopy(ep["rule_versions"]["R2"]),
        "review_state": "candidate",
    }
    ep["rule_versions"]["R3-DRAFT"]["followup"]["window_half_width_days"] = 21
    try:
        run("CSL-A-FX-19", "R3-DRAFT", endpoint=ep)
    except ValueError as e:
        assert "not approved" in str(e)
    else:
        raise AssertionError("candidate rule executed")
    # and the approved results for the participant it would have changed are unaffected
    assert run("CSL-A-FX-19", "R2").result_status == engine.NO_QUALIFYING_FOLLOWUP


def test_deterministic_and_input_order_independent():
    for usubjid, n in NAMED.items():
        rule = "R1"
        a = run(usubjid, rule).row()
        rev = {**n, "observations": list(reversed(n["observations"]))}
        NAMED[usubjid] = rev
        try:
            b = run(usubjid, rule).row()
        finally:
            NAMED[usubjid] = n
        assert a == b, usubjid


def test_oracle_detects_single_rule_mutations():
    """Each boundary/tie-break rule must be pinned by at least one named participant."""
    mutations = {
        "follow-up window +1": ("followup", "window_half_width_days", 8),
        "follow-up window -1": ("followup", "window_half_width_days", 6),
        "baseline window start -1": ("baseline", "window_days", [-29, -1]),
        "baseline window start +1": ("baseline", "window_days", [-27, -1]),
        "tie-breaker flipped": ("followup", "tie_breaker", ["earlier_date", "lower_seq"]),
        "same-day pre-dose disallowed": ("baseline", "same_day_predose", "not_allowed"),
        "target offset +1": ("followup", "target_offset_days", 169),
    }
    global REG
    original = REG
    try:
        for name, (part, key, val) in mutations.items():
            REG = copy.deepcopy(original)
            REG["endpoints"]["EP-A-WT24"]["rule_versions"]["R1"][part][key] = val
            errs = []
            for usubjid, rules in ORACLE["expected"].items():
                if "R1" in rules and NAMED[usubjid]["participant"]["study_id"] == "CSL-A":
                    errs += check(run(usubjid, "R1"), rules["R1"], usubjid)
            assert errs, f"mutation not detected: {name}"
    finally:
        REG = original


def test_display_rounding_is_half_away_from_zero_and_separate():
    assert engine.display_round(-6.25) == -6.3 and engine.display_round(6.25) == 6.3
    assert engine.display_round(-9.038461538461544) == -9.0


def test_unit_normalization_and_study_day():
    assert engine.to_kg("231.5", "LB")[0] == 231.5 * 0.45359237
    assert engine.to_kg("16.2", "st") == (None, "UNSUPPORTED_UNIT")
    assert engine.to_kg("97", "") == (None, "MISSING_UNIT")
    assert engine.to_kg("", "kg") == (None, "MISSING_RESULT")
    from datetime import date

    ref = date(2025, 3, 3)
    assert engine.study_day(ref, ref) == 1 and engine.study_day(date(2025, 3, 2), ref) == -1
    assert engine.parse_dtc("2025-03") is None and engine.parse_dtc("2025-02-30") is None


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
