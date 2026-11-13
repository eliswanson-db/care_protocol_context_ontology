"""Eligibility and protocol-deviation assessment over the vendored KB (SYNTHETIC demo). ADR-0022 / ADR-0025.

Pure Python, run by the pipeline through applyInPandas and called directly by tests. Class membership is is_a*
over the KB (closure semantics, polyhierarchy-aware), never a flat code list. Each criterion result
carries the evidence record and the ontology path that decided it, so the graph, closure, RAG and Genie
approaches can be scored against the same, inspectable answer.
"""

from __future__ import annotations

import collections
import csv
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from clinical_study.engine import parse_dtc

STD = Path(__file__).resolve().parents[1] / "standards" / "life_sciences"
EQUIV = ("skos:exactMatch", "oboInOwl:hasDbXref", "cpl:curatedEquivalent")
ELIGIBILITY_ENGINE_VERSION = "1.0.0"


class Ontology:
    """Read-only view of kb_concept / kb_edge (direct edges). Traversal is computed, not pre-materialized."""

    def __init__(self, concepts: list[dict], edges: list[dict]):
        self.concepts = {c["concept_id"]: c for c in concepts}
        self.out: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
        self.inv: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
        for e in edges:
            self.out[(e["subject"], e["predicate"])].append(e["object"])
            self.inv[(e["object"], e["predicate"])].append(e["subject"])
        for v in (*self.out.values(), *self.inv.values()):
            v.sort()
        self.release = sorted({f"{c['scheme']}:{c['release']}" for c in concepts})

    @classmethod
    def from_csv(cls, std_dir: Path = STD) -> Ontology:
        with open(std_dir / "kb_concept.csv", encoding="utf-8") as f:
            concepts = list(csv.DictReader(f))
        with open(std_dir / "kb_edge.csv", encoding="utf-8") as f:
            edges = list(csv.DictReader(f))
        return cls(concepts, edges)

    def label(self, c: str) -> str:
        return self.concepts.get(c, {}).get("label", "")

    def path_up(self, term: str, roots: set[str]) -> list[str] | None:
        """Shortest is_a path term -> ... -> a root (BFS, deterministic). None if not under any root."""
        if term in roots:
            return [term]
        prev, frontier, seen = {term: None}, [term], {term}
        while frontier:
            nxt = []
            for c in frontier:
                for p in self.out.get((c, "rdfs:subClassOf"), []):
                    if p in seen:
                        continue
                    seen.add(p)
                    prev[p] = c
                    if p in roots:
                        path, x = [p], c
                        while x is not None:
                            path.append(x)
                            x = prev[x]
                        return list(reversed(path))
                    nxt.append(p)
            frontier = sorted(nxt)
        return None

    def ancestors(self, term: str) -> list[str]:
        seen, st = [], [term]
        while st:
            for p in self.out.get((st.pop(), "rdfs:subClassOf"), []):
                if p not in seen:
                    seen.append(p)
                    st.append(p)
        return seen

    def _broader_mesh(self, x: str) -> list[str]:
        seen, st = [x], [x]
        while st:
            cur = st.pop()
            for p in ("mesh:headingMappedTo", "mesh:broaderDescriptor"):
                for y in self.out.get((cur, p), []):
                    if y not in seen:
                        seen.append(y)
                        st.append(y)
        return seen

    def class_members(self, drug_class: str) -> list[str]:
        return list(self.inv.get((drug_class, "medrt:memberOf"), []))

    def contraindications(self, term: str, drug_class: str, excluded_targets: set[str]) -> list[dict]:
        """Sound (broadening-only) walk from a MONDO condition to MED-RT CI_with on members of drug_class."""
        members = set(self.class_members(drug_class))
        hits: dict[str, dict] = {}
        for d in [term, *self.ancestors(term)]:
            for pred in EQUIV:
                for x in self.out.get((d, pred), []):
                    if not x.startswith("MESH:"):
                        continue
                    for rec in self._broader_mesh(x):
                        if rec in excluded_targets:
                            continue
                        for m in self.inv.get((rec, "mesh:conceptOf"), []):
                            for drug in self.inv.get((m, "medrt:CI_with"), []):
                                if drug in members and drug not in hits:
                                    up = self.path_up(term, {d}) or [term]
                                    hits[drug] = {
                                        "drug": drug,
                                        "path": [*up, pred, x, rec, m, "medrt:CI_with", drug],
                                    }
        return [hits[k] for k in sorted(hits)]

    def prohibited(self, rxcui_node: str, rule: dict) -> dict | None:
        for cls in rule.get("member_of_classes", []):
            if cls in self.out.get((rxcui_node, "medrt:memberOf"), []):
                return {"basis": "member_of_class", "path": [rxcui_node, "medrt:memberOf", cls]}
        pe_ids = {
            c for c, r in self.concepts.items() if r["label"] in set(rule.get("has_physiologic_effect", []))
        }
        for pe in self.out.get((rxcui_node, "medrt:has_PE"), []):
            if pe in pe_ids:
                return {"basis": "physiologic_effect", "path": [rxcui_node, "medrt:has_PE", pe]}
        return None


@lru_cache(maxsize=1)
def default_ontology() -> Ontology:
    return Ontology.from_csv()


def class_roots(registry: dict, class_id: str) -> set[str]:
    c = registry["concept_classes"][class_id]
    roots = set(c.get("roots", []))
    if "extends" in c:
        roots |= class_roots(registry, c["extends"])
    return roots | set(c.get("add_roots", []))


def class_exclusions(registry: dict, class_id: str) -> set[str]:
    c = registry["concept_classes"][class_id]
    ex = {x["id"] for x in c.get("exclude_roots", [])}
    if "extends" in c:
        ex |= class_exclusions(registry, c["extends"])
    return ex


def member_path(onto: Ontology, term: str, roots: set[str], excluded: set[str]) -> list[str] | None:
    """is_a* path to a class root, or None. Exclusion wins: a term under any excluded root is not a member."""
    if excluded and onto.path_up(term, excluded):
        return None
    return onto.path_up(term, roots)


def protocol_version_on(registry: dict, study_id: str, d: date) -> str:
    versions = sorted(registry["studies"][study_id]["study_versions"], key=lambda v: v["effective_date"])
    current = None
    for v in versions:
        if date.fromisoformat(v["effective_date"]) <= d:
            current = v["protocol_version"]
    if current is None:
        raise ValueError(f"{study_id}: no protocol version effective on {d}")
    return current


def eligibility_rule_for(registry: dict, study_id: str, protocol_version: str) -> tuple[str, dict]:
    for rid, r in sorted(registry["eligibility"].items()):
        if r["study"] == study_id and protocol_version in r["applies_to_protocol_versions"]:
            if r.get("review_state") != "approved":
                raise ValueError(f"{rid} is not approved")
            return rid, r
    raise ValueError(f"{study_id}: no eligibility rule for protocol {protocol_version}")


@dataclass
class CriterionResult:
    criterion_id: str
    criterion_type: str
    outcome: str  # MET | NOT_MET | TRIGGERED | NOT_TRIGGERED | NOT_EVALUABLE
    evidence: list[str] = field(default_factory=list)  # source record ids (MH/CM/VS)
    path: list[str] = field(default_factory=list)  # ontology path that decided it
    detail: str = ""


@dataclass
class Assessment:
    study_id: str
    usubjid: str
    screening_date: str
    protocol_version: str
    eligibility_rule_id: str
    eligible: bool
    criteria: list[CriterionResult]
    engine_version: str = ELIGIBILITY_ENGINE_VERSION


def _active_between(cm: dict, lo: date, hi: date) -> bool:
    start = parse_dtc(cm.get("cmstdtc"))
    end = parse_dtc(cm.get("cmendtc"))
    s = start.day if start else date.min
    e = end.day if end else date.max
    return s <= hi and e >= lo


def assess(
    subject: dict, screening_vitals: dict, mh: list[dict], cm: list[dict], registry: dict, onto: Ontology
) -> Assessment:
    """subject: study_id, usubjid, screening_date (ISO), age
    screening_vitals: weight_kg, height_cm, weight_obs_id, height_obs_id (any may be None)
    mh: mh_id, mondo_id ; cm: cm_id, rxnorm (RXNORM:<code>), cmstdtc, cmendtc"""
    study = subject["study_id"]
    sdate = date.fromisoformat(subject["screening_date"])
    pv = protocol_version_on(registry, study, sdate)
    rid, rule = eligibility_rule_for(registry, study, pv)
    results: list[CriterionResult] = []
    wt, ht = screening_vitals.get("weight_kg"), screening_vitals.get("height_cm")
    bmi = wt / (ht / 100.0) ** 2 if wt and ht else None
    vs_ev = [x for x in (screening_vitals.get("weight_obs_id"), screening_vitals.get("height_obs_id")) if x]

    for c in rule["criteria"]:
        r = CriterionResult(c["id"], c["type"], "")
        if c["id"] == "INC-AGE":
            a = subject.get("age")
            r.outcome = (
                "NOT_EVALUABLE" if a is None else ("MET" if c["min_age"] <= a <= c["max_age"] else "NOT_MET")
            )
            r.detail = f"age={a}"
        elif c["id"] == "INC-BMI":
            if bmi is None:
                r.outcome, r.detail = "NOT_EVALUABLE", "screening weight or height missing"
            elif bmi >= c["bmi_alone"]:
                r.outcome, r.detail, r.evidence = "MET", f"BMI {bmi:.2f} >= {c['bmi_alone']}", vs_ev
            elif "bmi_with_comorbidity" in c and bmi >= c["bmi_with_comorbidity"]:
                roots = class_roots(registry, c["comorbidity_class"])
                excluded = class_exclusions(registry, c["comorbidity_class"])
                hit = None
                for h in sorted(mh, key=lambda x: x["mh_id"]):
                    p = member_path(onto, h["mondo_id"], roots, excluded)
                    if p and (hit is None or len(p) < len(hit[1])):
                        hit = (h, p)
                if hit:
                    r.outcome, r.evidence, r.path = "MET", [*vs_ev, hit[0]["mh_id"]], hit[1]
                    r.detail = (
                        f"BMI {bmi:.2f} >= {c['bmi_with_comorbidity']} with {c['comorbidity_class']} member "
                        f"{onto.label(hit[1][0])} (is_a* {onto.label(hit[1][-1])})"
                    )
                else:
                    r.outcome, r.evidence = "NOT_MET", vs_ev
                    lo_, hi_ = c["bmi_with_comorbidity"], c["bmi_alone"]
                    r.detail = f"BMI {bmi:.2f} in [{lo_}, {hi_}) and no {c['comorbidity_class']} member"
            else:
                r.outcome, r.evidence, r.detail = "NOT_MET", vs_ev, f"BMI {bmi:.2f}"
        elif c["id"] == "INC-T2D":
            roots = set(c["required_class_roots"])
            hit = next(((h, p) for h in mh if (p := onto.path_up(h["mondo_id"], roots))), None)
            r.outcome = "MET" if hit else "NOT_MET"
            if hit:
                r.evidence, r.path = [hit[0]["mh_id"]], hit[1]
        elif c["id"] == "EXC-MH":
            roots = class_roots(registry, c["class"]) - set(c.get("except_roots", []))
            hit = next(
                (
                    (h, p)
                    for h in sorted(mh, key=lambda x: x["mh_id"])
                    if (p := onto.path_up(h["mondo_id"], roots))
                ),
                None,
            )
            r.outcome = "TRIGGERED" if hit else "NOT_TRIGGERED"
            if hit:
                r.evidence, r.path, r.detail = (
                    [hit[0]["mh_id"]],
                    hit[1],
                    f"{onto.label(hit[1][0])} is_a* {onto.label(hit[1][-1])}",
                )
        elif c["id"] == "EXC-CI":
            cdef = registry["concept_classes"][c["class"]]
            excluded = {x["target"] for x in cdef.get("excluded_ci_targets", [])}
            hit = None
            for h in sorted(mh, key=lambda x: x["mh_id"]):
                ci = onto.contraindications(h["mondo_id"], cdef["drug_class"], excluded)
                if ci:
                    hit = (h, ci[0])
                    break
            r.outcome = "TRIGGERED" if hit else "NOT_TRIGGERED"
            if hit:
                r.evidence, r.path = [hit[0]["mh_id"]], hit[1]["path"]
                cond, drug = onto.label(hit[0]["mondo_id"]), onto.label(hit[1]["drug"])
                r.detail = f"{cond}: MED-RT CI_with for class member {drug}"
        elif c["id"] == "EXC-CM":
            pdef = registry["concept_classes"][c["class"]]
            lo = sdate - timedelta(days=pdef["lookback_days_before_screening"])
            hit = None
            for m in sorted(cm, key=lambda x: x["cm_id"]):
                p = onto.prohibited(m["rxnorm"], pdef)
                if p and _active_between(m, lo, sdate):
                    hit = (m, p)
                    break
            r.outcome = "TRIGGERED" if hit else "NOT_TRIGGERED"
            if hit:
                r.evidence, r.path = [hit[0]["cm_id"]], hit[1]["path"]
                days = pdef["lookback_days_before_screening"]
                drug = onto.label(hit[0]["rxnorm"])
                r.detail = f"{drug} ({hit[1]['basis']}) active within {days}d before screening"
        else:
            raise ValueError(f"unknown criterion {c['id']}")
        results.append(r)

    eligible = all(
        (x.outcome == "MET") if x.criterion_type == "inclusion" else (x.outcome == "NOT_TRIGGERED")
        for x in results
    )
    return Assessment(study, subject["usubjid"], sdate.isoformat(), pv, rid, eligible, results)


def on_treatment_deviations(
    first_dose: date | None, last_contact: date | None, cm: list[dict], registry: dict, onto: Ontology
) -> list[dict]:
    """Prohibited medication started or active on treatment = major protocol deviation (excludes from PPS)."""
    if first_dose is None:
        return []
    pdef = registry["concept_classes"]["PROHIB-CM-V1"]
    hi = last_contact or date.max
    out = []
    for m in sorted(cm, key=lambda x: x["cm_id"]):
        p = onto.prohibited(m["rxnorm"], pdef)
        if p and _active_between(m, first_dose, hi):
            out.append(
                {
                    "deviation": "PROHIBITED_MEDICATION_ON_TREATMENT",
                    "severity": "MAJOR",
                    "evidence": m["cm_id"],
                    "path": p["path"],
                    "drug": onto.label(m["rxnorm"]),
                }
            )
    return out


def screening_vitals(weights: list[dict], height: dict | None) -> dict:
    """Weight for the BMI criterion: the valid SCREENING-visit weight, else the earliest valid BASELINE weight
    (registry INC-BMI.bmi_source). Height: the screening height record (cm)."""
    from clinical_study.engine import to_kg

    def valid(visit: str):
        rows = []
        for w in weights:
            if w.get("visit") != visit or (w.get("vsstat") or "").upper() == "NOT DONE":
                continue
            kg, why = to_kg(w.get("vsorres"), w.get("vsorresu"))
            s = parse_dtc(w.get("vsdtc"))
            if kg and kg > 0 and not why and s:
                rows.append((s.day, s.time or (0, 0, 0), int(w["vsseq"]), kg, w["obs_id"]))
        return sorted(rows)

    pick = (valid("SCREENING") or valid("BASELINE") or [None])[0]
    h_cm = None
    if height and height.get("vsorresu") == "cm":
        try:
            h_cm = float(height["vsorres"])
        except (TypeError, ValueError):
            h_cm = None
    return {
        "weight_kg": pick[3] if pick else None,
        "weight_obs_id": pick[4] if pick else None,
        "height_cm": h_cm,
        "height_obs_id": height.get("obs_id") if h_cm else None,
    }


def participant_status(
    randomized: bool, dosed: bool, assessment: Assessment, on_treatment: list[dict]
) -> dict:
    """FAS / PPS membership and major deviations (registry populations). FAS = randomized and dosed, even when
    the first-dose date is incomplete (the endpoint is NO_REFERENCE_DATE, but the participant is in FAS)."""
    deviations = list(on_treatment)
    if randomized and not assessment.eligible:
        failed = [
            c.criterion_id
            for c in assessment.criteria
            if (c.criterion_type == "inclusion" and c.outcome != "MET")
            or (c.criterion_type == "exclusion" and c.outcome != "NOT_TRIGGERED")
        ]
        deviations.insert(
            0,
            {
                "deviation": "ELIGIBILITY_VIOLATION",
                "severity": "MAJOR",
                "evidence": ",".join(failed),
                "path": [],
                "drug": None,
            },
        )
    fas = bool(randomized and dosed)
    return {
        "fas": fas,
        "pps": fas and not any(d["severity"] == "MAJOR" for d in deviations),
        "deviations": deviations,
    }
