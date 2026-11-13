"""Deterministic, versioned endpoint engine — percent change in body weight from baseline (SYNTHETIC demo).

Pure Python (stdlib only) so the SAME code runs in local tests and inside the Lakeflow pipeline via
applyInPandas. It never calls retrieval or an LLM. It reads only APPROVED rule versions from the registry
(src/clinical_study/rules/registry.yaml), and candidate document assertions never reach it.

Time handling (stated, and simplified vs. the full CDISC study-day conventions):
  * reference date = date part of the earliest administered dose (EX.EXSTDTC; placebo counts). A partial
    or missing date means the endpoint cannot be derived (NO_REFERENCE_DATE).
  * study day = (date - ref) + 1 if date >= ref else (date - ref). No day 0.
  * windows are inclusive. Dates drive the window logic; the time of day is used only to decide whether a
    day-1 record was taken before the first dose.
  * the follow-up target is a calendar date: ref + target_offset_days. Distance = |obs_date - target| in days.

Every observation gets exactly one decision row (role, decision, reason). Nothing is dropped silently.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

ENGINE_VERSION = "1.0.0"

UNIT_TO_KG = {"kg": 1.0, "LB": 0.45359237, "g": 0.001}  # COSMoS DSS WEIGHT: VSORRESU in {LB, g, kg}

# result_status
DERIVED = "DERIVED"
NOT_IN_POPULATION = "NOT_IN_POPULATION"
NO_REFERENCE_DATE = "NO_REFERENCE_DATE"
NO_VALID_BASELINE = "NO_VALID_BASELINE"
NO_QUALIFYING_FOLLOWUP = "NO_QUALIFYING_FOLLOWUP"

# candidate decisions
SELECTED = "SELECTED"
ELIGIBLE_NOT_SELECTED = "ELIGIBLE_NOT_SELECTED"
EXCLUDED = "EXCLUDED"

_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2})(?::(\d{2}))?)?$")


@dataclass(frozen=True)
class Stamp:
    """A parsed ISO 8601 date/datetime. `time` is None for a date-only value."""

    day: date
    time: tuple[int, int, int] | None


def parse_dtc(dtc: str | None) -> Stamp | None:
    """Full dates only. Partial (YYYY or YYYY-MM) or malformed values return None, so they never qualify."""
    if not dtc:
        return None
    m = _ISO.match(dtc.strip())
    if not m:
        return None
    y, mo, d, hh, mm, ss = m.groups()
    try:
        day = date(int(y), int(mo), int(d))
    except ValueError:
        return None
    t = (int(hh), int(mm), int(ss or 0)) if hh is not None else None
    return Stamp(day, t)


def study_day(d: date, ref: date) -> int:
    delta = (d - ref).days
    return delta + 1 if delta >= 0 else delta


def to_kg(orres: str | None, unit: str | None) -> tuple[float | None, str | None]:
    """(kg, None) or (None, reason). Units must be a CDISC CT submission value allowed by the WEIGHT DSS."""
    if orres is None or str(orres).strip() == "":
        return None, "MISSING_RESULT"
    try:
        v = float(orres)
    except ValueError:
        return None, "NON_NUMERIC_RESULT"
    if not math.isfinite(v):
        return None, "NON_NUMERIC_RESULT"
    if unit is None or str(unit).strip() == "":
        return None, "MISSING_UNIT"
    if unit not in UNIT_TO_KG:
        return None, "UNSUPPORTED_UNIT"
    return v * UNIT_TO_KG[unit], None


def display_round(x: float | None, ndigits: int = 1) -> float | None:
    """Display only (round half away from zero). Stored analysis values stay unrounded."""
    if x is None:
        return None
    q = 10**ndigits
    return math.copysign(math.floor(abs(x) * q + 0.5) / q, x)


@dataclass
class Candidate:
    obs_id: str
    vsseq: int
    vsdtc: str | None
    visit: str | None
    study_day: int | None
    weight_kg: float | None
    role: str = "NONE"  # BASELINE | FOLLOWUP | NONE
    decision: str = EXCLUDED
    reason: str = ""
    days_from_target: int | None = None


@dataclass
class Result:
    study_id: str
    participant_id: str
    endpoint_id: str
    endpoint_version: str
    rule_version: str
    protocol_version: str
    sap_version: str
    analysis_population_status: str
    reference_date: str | None
    followup_target_date: str | None
    baseline_method: str
    baseline_observation_ids: list[str]
    followup_observation_id: str | None
    baseline_value: float | None
    followup_value: float | None
    analysis_value: float | None
    analysis_value_display: float | None
    result_status: str
    exclusion_reason: str | None
    terminology_version: str
    engine_version: str = ENGINE_VERSION
    execution_run_id: str = ""
    candidates: list[Candidate] = field(default_factory=list)

    def row(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("candidates")
        d["baseline_observation_id"] = ",".join(self.baseline_observation_ids) or None
        d.pop("baseline_observation_ids")
        return d


def is_dose(e: dict) -> bool:
    """A dose record that occurred. Placebo is recorded with EXDOSE 0, so 'dosed' must not mean dose > 0."""
    return (e.get("exoccur") or "Y") != "N" and e.get("exdose") is not None and float(e["exdose"]) >= 0


def _first_dose(exposures: list[dict]) -> tuple[Stamp | None, str | None]:
    """Earliest administered dose (study drug or placebo). Returns (stamp, None) or (None, reason)."""
    doses = [e for e in exposures if is_dose(e)]
    if not doses:
        return None, "NOT_DOSED"
    stamps = [parse_dtc(e.get("exstdtc")) for e in doses]
    if any(s is None for s in stamps):
        # a partial/missing start date on ANY dosed record means the earliest dose can't be established
        return None, "FIRST_DOSE_DATE_INCOMPLETE"
    return min(stamps, key=lambda s: (s.day, s.time or (99, 0, 0))), None


def _dedupe(cands: list[Candidate], obs: list[dict]) -> None:
    """Same datetime + same original result + same unit = one measurement recorded twice.

    Keeps the lowest VSSEQ; the others are excluded as DUPLICATE_RECORD."""
    seen: dict[tuple, Candidate] = {}
    for c, o in sorted(zip(cands, obs, strict=True), key=lambda p: p[0].vsseq):
        if c.reason:
            continue
        key = (o.get("vsdtc"), str(o.get("vsorres")).strip(), o.get("vsorresu"))
        if key in seen:
            c.reason = "DUPLICATE_RECORD"
            c.decision = EXCLUDED
        else:
            seen[key] = c


def derive(
    participant: dict,
    observations: list[dict],
    exposures: list[dict],
    *,
    endpoint_id: str,
    endpoint: dict,
    rule_version: str,
    terminology_version: str,
    execution_run_id: str = "",
) -> Result:
    """Derive one participant's endpoint under one rule version.

    participant: study_id, usubjid, randomized (bool)
    observations: WEIGHT records -- obs_id, vsseq, vsdtc, vsorres, vsorresu (CT), vsstat, visit
    exposures:    EX records -- exstdtc, exdose
    """
    rule = endpoint["rule_versions"][rule_version]
    if rule.get("review_state") != "approved":
        raise ValueError(
            f"{endpoint_id} {rule_version} is not approved; the engine executes approved rules only"
        )
    bl_rule, fu_rule = rule["baseline"], rule["followup"]
    res = Result(
        study_id=participant["study_id"],
        participant_id=participant["usubjid"],
        endpoint_id=endpoint_id,
        endpoint_version=f"{endpoint_id}.{rule_version}",
        rule_version=rule_version,
        protocol_version=rule["protocol_version"],
        sap_version=rule["sap_version"],
        analysis_population_status="",
        reference_date=None,
        followup_target_date=None,
        baseline_method=bl_rule["method"],
        baseline_observation_ids=[],
        followup_observation_id=None,
        baseline_value=None,
        followup_value=None,
        analysis_value=None,
        analysis_value_display=None,
        result_status="",
        exclusion_reason=None,
        terminology_version=terminology_version,
        execution_run_id=execution_run_id,
    )

    cands: list[Candidate] = []
    for o in observations:
        s = parse_dtc(o.get("vsdtc"))
        kg, why = (
            (None, "NOT_DONE")
            if (o.get("vsstat") or "").upper() == "NOT DONE"
            else to_kg(o.get("vsorres"), o.get("vsorresu"))
        )
        c = Candidate(
            obs_id=o["obs_id"],
            vsseq=int(o["vsseq"]),
            vsdtc=o.get("vsdtc"),
            visit=o.get("visit"),
            study_day=None,
            weight_kg=kg,
        )
        if s is None:
            c.reason = "MISSING_OR_PARTIAL_DATE"
        elif why:
            c.reason = why
        elif kg is not None and kg <= rule["validity"]["min_kg_exclusive"]:
            c.reason = "NONPOSITIVE_VALUE"
        cands.append(c)
    res.candidates = cands
    _dedupe(cands, observations)

    # ---- population (FAS: randomized and dosed)
    first, why_not = _first_dose(exposures)
    if not participant.get("randomized"):
        res.analysis_population_status = "NOT_IN_FAS"
        return _finish(res, NOT_IN_POPULATION, "NOT_RANDOMIZED", "NOT_IN_POPULATION")
    if why_not == "NOT_DOSED":
        res.analysis_population_status = "NOT_IN_FAS"
        return _finish(res, NOT_IN_POPULATION, "NOT_DOSED", "NOT_IN_POPULATION")
    res.analysis_population_status = "IN_FAS"
    if first is None:
        return _finish(res, NO_REFERENCE_DATE, why_not, "NO_REFERENCE_DATE")
    ref = first.day
    res.reference_date = ref.isoformat()

    lo, hi = bl_rule["window_days"]
    target = date.fromordinal(ref.toordinal() + fu_rule["target_offset_days"])
    res.followup_target_date = target.isoformat()
    hw = fu_rule["window_half_width_days"]

    bl_pool: list[tuple[Candidate, Stamp]] = []
    fu_pool: list[Candidate] = []
    for c, o in zip(cands, observations, strict=True):
        s = parse_dtc(o.get("vsdtc"))
        if s is None:
            continue
        c.study_day = study_day(s.day, ref)
        if c.study_day <= 1:
            c.role = "BASELINE"
        else:
            c.role = "FOLLOWUP"
            c.days_from_target = (s.day - target).days
        if c.reason:  # already invalid (unit, value, duplicate, not done)
            continue
        if c.study_day == 1:
            policy = bl_rule["same_day_predose"]
            if policy == "not_allowed":
                c.reason = "SAME_DAY_NOT_ALLOWED"
            elif s.time is None:
                c.reason = "SAME_DAY_NO_TIME"
            elif first.time is None:
                c.reason = "SAME_DAY_DOSE_TIME_UNKNOWN"
            elif s.time >= first.time:
                c.reason = "SAME_DAY_POST_DOSE"
            else:
                bl_pool.append((c, s))
        elif c.study_day < 1:
            if lo <= c.study_day <= hi:
                bl_pool.append((c, s))
            else:
                c.reason = "OUTSIDE_BASELINE_WINDOW"
        else:
            if abs(c.days_from_target) <= hw:
                fu_pool.append(c)
            else:
                c.reason = "OUTSIDE_FOLLOWUP_WINDOW"

    # ---- baseline
    if not bl_pool:
        for c in fu_pool:
            c.decision, c.reason = ELIGIBLE_NOT_SELECTED, "FOLLOWUP_ELIGIBLE_NO_BASELINE"
        return _finish(res, NO_VALID_BASELINE, _why_no_baseline(cands), None)
    if bl_rule["method"] == "last":
        bl_pool.sort(key=lambda p: (p[1].day, p[1].time or (0, 0, 0), -p[0].vsseq))
        chosen = bl_pool[-1][0]
        for c, _ in bl_pool:
            c.decision, c.reason = (
                (SELECTED, "BASELINE_LAST_VALID")
                if c is chosen
                else (ELIGIBLE_NOT_SELECTED, "BASELINE_NOT_LAST")
            )
        res.baseline_observation_ids = [chosen.obs_id]
        res.baseline_value = chosen.weight_kg
    elif bl_rule["method"] == "mean":
        for c, _ in bl_pool:
            c.decision, c.reason = SELECTED, "BASELINE_INCLUDED_IN_MEAN"
        res.baseline_observation_ids = [c.obs_id for c, _ in sorted(bl_pool, key=lambda p: p[0].vsseq)]
        res.baseline_value = sum(c.weight_kg for c, _ in bl_pool) / len(bl_pool)
    else:
        raise ValueError(f"unknown baseline method {bl_rule['method']}")

    # ---- follow-up
    if not fu_pool:
        return _finish(res, NO_QUALIFYING_FOLLOWUP, _why_no_followup(cands), None)
    order = []
    for tb in fu_rule["tie_breaker"]:
        order.append(
            {
                "later_date": lambda c: -c.days_from_target,
                "earlier_date": lambda c: c.days_from_target,
                "lower_seq": lambda c: c.vsseq,
            }[tb]
        )
    fu_pool.sort(key=lambda c: (abs(c.days_from_target), *[f(c) for f in order]))
    chosen = fu_pool[0]
    best = abs(chosen.days_from_target)
    for c in fu_pool:
        if c is chosen:
            c.decision, c.reason = SELECTED, "FOLLOWUP_CLOSEST_TO_TARGET"
        elif abs(c.days_from_target) == best:
            c.decision, c.reason = ELIGIBLE_NOT_SELECTED, "FOLLOWUP_TIE_LOST"
        else:
            c.decision, c.reason = ELIGIBLE_NOT_SELECTED, "FOLLOWUP_NOT_CLOSEST"
    res.followup_observation_id = chosen.obs_id
    res.followup_value = chosen.weight_kg
    res.analysis_value = 100.0 * (res.followup_value - res.baseline_value) / res.baseline_value
    res.analysis_value_display = display_round(res.analysis_value, 1)
    return _finish(res, DERIVED, None, None)


def _why_no_baseline(cands: list[Candidate]) -> str:
    pre = [c for c in cands if c.role == "BASELINE"]
    if not pre:
        return "NO_PRETREATMENT_OBSERVATION"
    reasons = sorted({c.reason for c in pre})
    return "NO_VALID_BASELINE:" + "|".join(reasons)


def _why_no_followup(cands: list[Candidate]) -> str:
    post = [c for c in cands if c.role == "FOLLOWUP"]
    if not post:
        return "NO_POSTBASELINE_OBSERVATION"
    near = [c for c in post if c.reason == "OUTSIDE_FOLLOWUP_WINDOW"]
    if near and len(near) == len(post):
        closest = min(near, key=lambda c: abs(c.days_from_target))
        return f"NO_OBSERVATION_IN_WINDOW:closest_{closest.days_from_target:+d}d"
    return "NO_VALID_OBSERVATION_IN_WINDOW:" + "|".join(sorted({c.reason for c in post}))


def _finish(res: Result, status: str, reason: str | None, unassessed_reason: str | None) -> Result:
    res.result_status = status
    res.exclusion_reason = reason
    for c in res.candidates:
        if not c.reason and unassessed_reason:
            c.reason = unassessed_reason
        if c.decision == EXCLUDED and not c.reason:
            c.reason = "NOT_ASSESSED"
    return res
