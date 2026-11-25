"""Generate monitoring visit reports (MVRs) for every CSL-A and CSL-B site from the generated study data.

Why: in a real study the sponsor's clinical research associate (CRA) visits each site and files a monitoring visit
report in the CTMS: enrolment, visits since the last report, protocol deviations, source data verification, findings
and actions. These are free text, sponsor-confidential, numerous (one per site per visit), and nobody curates them
into a semantic layer. A customer lands the CTMS exports as files in a UC volume and indexes them for search; here
they are written from the data so every number in them agrees with it. Loaded into Lakebase RAG (corpus
clinical_study, access study_team) by scripts/lakebase_rag_corpus.py.

How visits are scheduled (ICH E6(R3) risk-based monitoring, the same rules for every site):
  * site initiation visit (SIV) 14 days before the site's first screening;
  * interim monitoring visits (IMV) every 8 weeks after the SIV, up to the data cutoff;
  * triggered monitoring visits (TMV): central monitoring's key risk indicator fires when a site has 3 or more
    Week 24 visits outside the protocol scheduling window within 30 days; a TMV follows 7 days later (at most one
    per 60 days per site).
Each report covers the period since the site's previous visit and uses only data dated inside it.

The one authored element: the root cause a CRA records when a site's Week 24 visits are systematically late (at
least 3, and at least half of them, 8 or more days after the target day in one period), i.e. what the site told
the monitor: a visit-calculator error (Week 24 computed as 25 weeks after first dose, then booked into the next
free clinic slot). Scattered late visits get "no common cause". Everything else is computed.

    .venv/bin/python -I scripts/gen_monitoring_reports.py
"""

from __future__ import annotations

import collections
import datetime as dt
import hashlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/life_sciences/documents/monitoring"
C = "eli_test_classic_catalog.clinical_study"
CUTOFF = dt.date(2026, 10, 31)
IMV_EVERY, TRIGGER_N, TRIGGER_DAYS, TMV_LAG, TMV_GAP = 56, 3, 30, 7, 60
WINDOWS = {  # protocol scheduling windows (study days), registry.yaml schedule
    "CSL-A": {"WEEK 4": (26, 32), "WEEK 8": (54, 60), "WEEK 12": (82, 88), "WEEK 16": (110, 116),
              "WEEK 20": (138, 144), "WEEK 24": (162, 176), "WEEK 36": (246, 260), "WEEK 52": (358, 372),
              "WEEK 72": (498, 512)},
    "CSL-B": {"WEEK 12": (80, 88), "WEEK 24": (161, 175), "WEEK 52": (357, 371)},
}
WK24_TARGET = {"CSL-A": 169, "CSL-B": 168}


def _q():
    spec = importlib.util.spec_from_file_location("q", ROOT / "scripts/q.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.run


def _d(s) -> dt.date | None:
    """ISO date from an SDTM --DTC; a partial date (e.g. '2025-07') has no day, so it isn't placed in a period."""
    try:
        return dt.date.fromisoformat(str(s)[:10]) if s else None
    except ValueError:
        return None


def _h(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest(), 16)


def load(run) -> dict:
    dm = run(f"SELECT USUBJID, STUDYID, SITEID, COUNTRY, DMDTC, RFXSTDTC, CPL_SCREEN_OUTCOME FROM {C}.silver_dm")
    ds = run(f"SELECT USUBJID, DSDECOD, DSSTDTC FROM {C}.silver_ds WHERE DSDECOD NOT IN ('RANDOMIZED', 'SCREEN FAILURE')")
    sv = run(f"SELECT sv.USUBJID, sv.VISIT, sv.SVSTDTC, datediff(CAST(sv.SVSTDTC AS DATE), CAST(dm.RFXSTDTC AS DATE)) + 1 "
             f"AS sd FROM {C}.silver_sv sv JOIN {C}.silver_dm dm USING (USUBJID) WHERE dm.RFXSTDTC IS NOT NULL "
             f"AND sv.VISIT LIKE 'WEEK %'")
    dev = run(f"SELECT p.USUBJID, p.d.drug AS drug, cm.CMSTDTC FROM (SELECT USUBJID, explode(deviations) AS d FROM "
              f"{C}.gold_participant_population) p JOIN {C}.silver_cm cm ON cm.CPL_SOURCE_RECORD_ID = p.d.evidence "
              f"WHERE p.d.deviation = 'PROHIBITED_MEDICATION_ON_TREATMENT'")
    err = run(f"SELECT p.USUBJID, dm.RFXSTDTC, concat_ws(', ', collect_set(e.criterion_id)) AS criteria "
              f"FROM {C}.gold_participant_population p JOIN {C}.silver_dm dm USING (USUBJID) "
              f"JOIN {C}.gold_eligibility_criterion e USING (USUBJID) WHERE p.edc_eligible = 'Y' AND NOT p.rule_eligible "
              f"AND p.randomized AND e.outcome IN ('TRIGGERED', 'NOT_MET') GROUP BY p.USUBJID, dm.RFXSTDTC")
    return {"dm": dm, "ds": ds, "sv": sv, "dev": dev, "err": err}


def schedule(site_dm: list[dict], site_wk24_late: list[dt.date]) -> list[tuple[dt.date, str]]:
    first = min(_d(r["DMDTC"]) for r in site_dm if _d(r["DMDTC"]))
    siv = first - dt.timedelta(days=14)
    visits = [(siv, "SIV")]
    d = siv + dt.timedelta(days=IMV_EVERY)
    while d <= CUTOFF:
        visits.append((d, "IMV"))
        d += dt.timedelta(days=IMV_EVERY)
    last_tmv = None
    late = sorted(site_wk24_late)
    for i, x in enumerate(late):  # key risk indicator: >= 3 late Week 24 visits within 30 days
        if i + 1 >= TRIGGER_N and (x - late[i + 1 - TRIGGER_N]).days <= TRIGGER_DAYS:
            t = x + dt.timedelta(days=TMV_LAG)
            if t <= CUTOFF and (last_tmv is None or (t - last_tmv).days >= TMV_GAP):
                visits.append((t, "TMV"))
                last_tmv = t
    return sorted(visits)


TYPE = {"SIV": "Site initiation visit", "IMV": "Interim monitoring visit", "TMV": "Triggered monitoring visit"}


def report(site: str, study: str, country: str, n: int, vdate: dt.date, vtype: str, prev: dt.date | None,
           data: dict, prior_cause: dt.date | None) -> tuple[str, str, bool]:
    """(document_id, markdown, root_cause_recorded)."""
    dm = data["dm"]
    within = lambda s: s and (prev is None or s > prev) and s <= vdate
    screened = [r for r in dm if _d(r["DMDTC"]) and _d(r["DMDTC"]) <= vdate]
    rand = [r for r in screened if r["RFXSTDTC"] and _d(r["RFXSTDTC"]) <= vdate]
    failed = [r for r in screened if r["CPL_SCREEN_OUTCOME"] == "SCREEN FAILED"]
    disp = collections.Counter(r["DSDECOD"] for r in data["ds"] if _d(r["DSSTDTC"]) and _d(r["DSSTDTC"]) <= vdate)
    completed = disp.pop("COMPLETED", 0)
    vis = [r for r in data["sv"] if within(_d(r["SVSTDTC"]))]
    outside = [r for r in vis if r["VISIT"] in WINDOWS[study]
               and not (WINDOWS[study][r["VISIT"]][0] <= int(r["sd"]) <= WINDOWS[study][r["VISIT"]][1])]
    wk24 = [r for r in vis if r["VISIT"] == "WEEK 24"]
    wk24_out = [r for r in outside if r["VISIT"] == "WEEK 24"]
    devs = [r for r in data["dev"] if within(_d(r["CMSTDTC"]))]
    errs = [r for r in data["err"] if within(_d(r["RFXSTDTC"]))]
    mode = "Remote" if vtype == "IMV" and _h(site, vdate) % 3 == 0 else "On-site"
    doc_id = f"MVR-{site}-{n:02d}"
    L = [
        "---",
        f"document_id: {doc_id}",
        f'title: "{study} {site} {TYPE[vtype]} report ({vdate.isoformat()})"',
        f"study_id: {study}",
        "doc_type: MONITORING_VISIT_REPORT",
        'version: "1.0"',
        "status: FINAL",
        f'effective_date: "{min(vdate + dt.timedelta(days=10), CUTOFF).isoformat()}"',
        f'access: "study:{study}"',
        "---",
        f"# {study} — {TYPE[vtype]} report — {site} ({country})",
        "",
        "SYNTHETIC DOCUMENT generated from the study data (scripts/gen_monitoring_reports.py). Sponsor confidential.",
        "",
        "## 1 Visit details",
        "",
        f"- Visit: {TYPE[vtype]} #{n}, {mode.lower()}, {vdate.isoformat()}",
        f"- Period covered: {'start of the study' if prev is None else prev.isoformat()} to {vdate.isoformat()}",
        "- Attendees: CRA (sponsor); principal investigator; study coordinator",
    ]
    if vtype == "TMV":
        L += ["- Trigger: central monitoring key risk indicator (3 or more Week 24 visits outside the scheduling window "
              "within 30 days)"]
    L += ["", "## 2 Enrolment status at the visit date", "",
          f"- Screened: {len(screened)}; screen failed: {len(failed)}; randomized: {len(rand)}",
          f"- Completed treatment: {completed}; discontinued: {sum(disp.values())}"
          + (f" ({', '.join(f'{k.lower()} {v}' for k, v in sorted(disp.items()))})" if disp else ""),
          "", "## 3 Visits since the previous monitoring visit", ""]
    if vtype == "SIV":
        L += ["- Not applicable (site initiation). Protocol, SAP, visit schedule and EDC entry were reviewed with the "
              "site team; delegation log and training records were checked."]
    else:
        L += [f"- Protocol visits conducted: {len(vis)}; outside the protocol scheduling window: {len(outside)}"]
        for r in sorted(outside, key=lambda r: (r["SVSTDTC"], r["USUBJID"]))[:25]:
            lo, hi = WINDOWS[study][r["VISIT"]]
            off = int(r["sd"]) - (hi if int(r["sd"]) > hi else lo)
            L.append(f"  - {r['USUBJID']} {r['VISIT']} on {str(r['SVSTDTC'])[:10]}: study day {r['sd']} "
                     f"({abs(off)} day{'s' if abs(off) != 1 else ''} {'after' if off > 0 else 'before'} the window)")
        if len(outside) > 25:
            L.append(f"  - … and {len(outside) - 25} more")
    L += ["", "## 4 Protocol deviations identified", ""]
    items = [f"- {r['USUBJID']}: prohibited medication on treatment ({r['drug']}, started {str(r['CMSTDTC'])[:10]}); "
             f"major deviation, reported in the CTMS"
             for r in sorted(devs, key=lambda r: (str(r["CMSTDTC"]), r["USUBJID"]))]
    items += [f"- {r['USUBJID']}: eligibility not met at screening ({r['criteria']}) but randomized; major deviation, "
              f"PI notified, reported to the sponsor medical monitor" for r in sorted(errs, key=lambda r: r["USUBJID"])]
    L += items or ["- None."]
    L += ["", "## 5 Source data verification", ""]
    if vtype == "SIV":
        L += ["- Not applicable."]
    else:
        sdv = {r["USUBJID"] for r in rand if within(_d(r["RFXSTDTC"]))} | {r["USUBJID"] for r in wk24}
        L += [f"- Eligibility and primary-endpoint (body weight) source data verified for {len(sdv)} participants "
              f"(randomized or with a Week 24 visit in the period)."]
    L += ["", "## 6 Findings and actions", ""]
    cause = False
    late8 = [r for r in wk24_out if int(r["sd"]) - WK24_TARGET[study] >= 8]
    if vtype != "SIV" and wk24:
        systematic = len(late8) >= TRIGGER_N and len(late8) >= 0.5 * len(wk24)  # most Week 24 visits late
        if systematic and prior_cause is None:
            cause = True
            L += [f"- Week 24 scheduling: {len(wk24_out)} of {len(wk24)} Week 24 visits in the period were booked "
                  f"after the scheduling window, {len(late8)} of them 8 or more days after the target day.",
                  f"  - Root cause (site interview): the site's visit-calculator spreadsheet computed the Week 24 visit "
                  f"as 25 weeks after first dose (study day {WK24_TARGET[study] + 7}) instead of day "
                  f"{WK24_TARGET[study]}; visits were then booked into the next free research-clinic slot. The study "
                  f"coordinator's other visit rows were correct.",
                  "  - Impact: Week 24 body weights outside the SAP analysis window give no evaluable primary "
                  "endpoint. Escalated to the study team (central monitoring, statistics).",
                  "  - Action: site to book Week 24 visits from the IRT visit calendar; calculator corrected; "
                  "coordinators retrained."]
        elif late8 and prior_cause is not None:  # follow-up on a pattern recorded earlier at this site
            L += [f"- Week 24 scheduling (see the report of {prior_cause.isoformat()}): {len(late8)} of {len(wk24)} "
                  f"Week 24 visits in the period were again 8 or more days late. The corrective action has not "
                  f"yet been effective; escalated to study management."]
        elif wk24_out:
            L += [f"- {len(wk24_out)} of {len(wk24)} Week 24 visits outside the scheduling window; reviewed with the "
                  f"site, rescheduled individually (participant availability). No common cause."]
    if vtype != "SIV" and len(outside) > len(wk24_out):
        L += [f"- {len(outside) - len(wk24_out)} other visits outside the scheduling window; reminded the site of the "
              f"visit windows."]
    if devs or errs:
        L += ["- Deviations above discussed with the principal investigator; documented in the CTMS."]
    if L[-1] == "" or L[-1].startswith("## 6"):
        L += ["- No findings requiring action."]
    L += ["", "## 7 Next visit", "", "- Per the monitoring plan (interim visit about every 8 weeks)."]
    return doc_id, "\n".join(L) + "\n", cause


def main() -> None:
    data = load(_q())
    by_site_dm = collections.defaultdict(list)
    for r in data["dm"]:
        by_site_dm[r["SITEID"]].append(r)
    site_of = {r["USUBJID"]: r["SITEID"] for r in data["dm"]}
    per = {k: collections.defaultdict(list) for k in ("ds", "sv", "dev", "err")}
    for k in per:
        for r in data[k]:
            per[k][site_of[r["USUBJID"]]].append(r)
    OUT.mkdir(parents=True, exist_ok=True)
    keep, n_tmv, causes = set(), 0, []
    for site in sorted(by_site_dm):
        dm = by_site_dm[site]
        study, country = dm[0]["STUDYID"], dm[0]["COUNTRY"]
        late = [_d(r["SVSTDTC"]) for r in per["sv"][site] if r["VISIT"] == "WEEK 24"
                and not (WINDOWS[study]["WEEK 24"][0] <= int(r["sd"]) <= WINDOWS[study]["WEEK 24"][1])]
        prev, prior_cause = None, None
        sdata = {"dm": dm, **{k: per[k][site] for k in per}}
        for n, (vdate, vtype) in enumerate(schedule(dm, late), 1):
            doc_id, md, cause = report(site, study, country, n, vdate, vtype, prev, sdata, prior_cause)
            (OUT / f"{doc_id}.md").write_text(md, encoding="utf-8")
            keep.add(f"{doc_id}.md")
            n_tmv += vtype == "TMV"
            if cause:
                prior_cause = vdate
                causes.append((site, vdate.isoformat(), vtype))
            prev = vdate
    for old in OUT.glob("MVR-*.md"):
        if old.name not in keep:
            old.unlink()
    print(f"wrote {len(keep)} reports for {len(by_site_dm)} sites to {OUT.relative_to(ROOT)}; "
          f"{n_tmv} triggered visits; systematic Week 24 root cause recorded at: {causes}")


if __name__ == "__main__":
    main()
