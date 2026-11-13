"""Eligibility, deviations and populations vs the hand-authored oracle (expected_eligibility.yaml).

No workspace.

python3 -I tests/test_ls_eligibility.py   (or pytest tests/test_ls_eligibility.py)
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinical_study import eligibility as el  # noqa: E402
from clinical_study.engine import _first_dose  # noqa: E402
from clinical_study.standardize import load_named, load_registry  # noqa: E402

ORACLE = yaml.safe_load(
    open(ROOT / "tests/fixtures/life_sciences/expected_eligibility.yaml", encoding="utf-8")
)
REG = load_registry()
ONTO = el.default_ontology()
NAMED = {n["participant"]["usubjid"]: n for n in load_named()}


def evaluate(n: dict) -> tuple[el.Assessment, dict]:
    sv = el.screening_vitals(n["observations"], n["height"])
    a = el.assess(n["subject"], sv, n["mh"], n["cm"], REG, ONTO)
    first, _ = _first_dose(n["exposures"])
    dosed = any((e.get("exdose") or 0) > 0 for e in n["exposures"])
    on_tx = el.on_treatment_deviations(first.day if first else None, None, n["cm"], REG, ONTO)
    return a, el.participant_status(n["participant"]["randomized"], dosed, a, on_tx)


def test_eligibility_fixtures_match_oracle():
    errs = []
    for u, exp in ORACLE["expected"].items():
        n = NAMED[u]
        a, st = evaluate(n)
        by = {c.criterion_id: c for c in a.criteria}
        for k in ("protocol_version", "eligible"):
            got = {"protocol_version": a.protocol_version, "eligible": a.eligible}[k]
            if got != exp[k]:
                errs.append(f"{u}: {k} {got} != {exp[k]}")
        if a.eligibility_rule_id != exp["rule"]:
            errs.append(f"{u}: rule {a.eligibility_rule_id} != {exp['rule']}")
        for cid, ce in (exp.get("criteria") or {}).items():
            c = by[cid]
            if c.outcome != ce["outcome"]:
                errs.append(f"{u} {cid}: {c.outcome} != {ce['outcome']} ({c.detail})")
            if "path" in ce and c.path != ce["path"]:
                errs.append(f"{u} {cid}: path {c.path} != {ce['path']}")
            if "evidence_mh" in ce and f"{u}.MH.{ce['evidence_mh']}" not in c.evidence:
                errs.append(f"{u} {cid}: evidence {c.evidence} lacks MH.{ce['evidence_mh']}")
            if "evidence_cm" in ce and c.evidence != [f"{u}.CM.{ce['evidence_cm']}"]:
                errs.append(f"{u} {cid}: evidence {c.evidence}")
            if "drug" in ce and (not c.path or c.path[-1] != ce["drug"]):
                errs.append(f"{u} {cid}: drug {c.path[-1:]} != {ce['drug']}")
            if "basis" in ce and ce["basis"] not in c.detail:
                errs.append(f"{u} {cid}: basis {c.detail}")
        if "deviations" in exp:
            got = [d["deviation"] for d in st["deviations"]]
            want = [d["deviation"] for d in exp["deviations"]]
            if got != want:
                errs.append(f"{u}: deviations {got} != {want}")
            for d, w in zip(st["deviations"], exp["deviations"], strict=False):
                if "evidence_cm" in w and d["evidence"] != f"{u}.CM.{w['evidence_cm']}":
                    errs.append(f"{u}: deviation evidence {d['evidence']}")
        for k in ("fas", "pps"):
            if k in exp and st[k] != exp[k]:
                errs.append(f"{u}: {k} {st[k]} != {exp[k]}")
    assert not errs, "\n".join(errs)


def test_endpoint_fixtures_are_ordinary_eligible_participants():
    bad = []
    for u, n in NAMED.items():
        if n["edge_case"] is None:
            continue
        a, st = evaluate(n)
        if not a.eligible:
            bad.append(
                (
                    u,
                    [
                        (c.criterion_id, c.outcome, c.detail)
                        for c in a.criteria
                        if c.outcome in ("NOT_MET", "TRIGGERED", "NOT_EVALUABLE")
                    ],
                )
            )
        if st["fas"] != (u not in ORACLE["not_in_fas"]):
            bad.append((u, "fas", st["fas"]))
    assert not bad, bad


def test_class_semantics_carve_outs_and_known_gap():
    r1, x1 = el.class_roots(REG, "WRC-V1"), el.class_exclusions(REG, "WRC-V1")
    r2, x2 = el.class_roots(REG, "WRC-V2"), el.class_exclusions(REG, "WRC-V2")
    member = lambda t, r, x: el.member_path(ONTO, t, r, x) is not None  # noqa: E731
    assert member("MONDO:0005439", r1, x1)  # familial hypercholesterolemia (multi-hop)
    assert not member("MONDO:0008585", r1, x1)  # HELLP syndrome (pregnancy carve-out)
    assert not member("MONDO:0019944", r1, x1)  # Eisenmenger (pulmonary hypertension carve-out)
    assert not member("MONDO:0001999", r1, x1)  # IPAH: reaches HF too, but exclusion wins
    assert not member("MONDO:0007147", r1, x1) and member("MONDO:0007147", r2, x2)  # OSA: Amendment 2
    assert not member("MONDO:0024356", r2, x2)  # central sleep apnea is not added
    assert not member("MONDO:0001302", r1, x1)  # hypertensive heart disease: documented MONDO gap


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
