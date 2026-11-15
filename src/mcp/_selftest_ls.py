"""Live self-test of the Clinical Study A6 tools against ECT, checked against INDEPENDENT answers:
hand-authored oracle fixtures, direct SQL counts, and the Python ontology walk (a second implementation of the
contraindication logic). Also checks supervisor routing, abstention and demo isolation.

    python src/mcp/_selftest_ls.py --profile ECT [--catalog eli_test_classic_catalog]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src" / "mcp"), str(ROOT / "src")]

import yaml  # noqa: E402
from databricks.sdk import WorkspaceClient  # noqa: E402

import clinical_study_supervisor as sup  # noqa: E402
import demo_registry  # noqa: E402
from clinical_study.eligibility import default_ontology  # noqa: E402
from clinical_study_tools import InputError, make_tools  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--catalog", default="eli_test_classic_catalog")
    a = ap.parse_args()
    w = WorkspaceClient(profile=a.profile)
    wh = next(x.id for x in w.warehouses.list() if x.name == "Serverless Starter Warehouse")

    def query(sql: str) -> list[dict]:
        r = w.statement_execution.execute_statement(warehouse_id=wh, statement=sql, wait_timeout="50s")
        if r.status.state.value != "SUCCEEDED":
            raise RuntimeError(r.status.error.message if r.status.error else r.status.state.value)
        cols = [c.name for c in r.manifest.schema.columns]
        return [dict(zip(cols, row)) for row in (r.result.data_array or [])] if r.result else []

    T = make_tools(a.catalog)
    cs = f"{a.catalog}.clinical_study"
    oracle = yaml.safe_load(open(ROOT / "tests/fixtures/life_sciences/expected_endpoints.yaml"))["expected"]
    fails: list[str] = []

    def check(name: str, cond: bool, detail="") -> None:
        print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {detail}"))
        if not cond:
            fails.append(name)

    # 1. endpoint_summary vs a direct count on gold (a different query path)
    s = T["endpoint_summary"](query, "EP-A-WT24.R1")
    direct = {
        r["ARMCD"]: int(r["n"])
        for r in query(
            f"SELECT p.ARMCD, count_if(r.result_status = 'DERIVED') n FROM {cs}.gold_endpoint_result r JOIN "
            f"{cs}.gold_participant_population p USING (USUBJID) WHERE r.endpoint_version = 'EP-A-WT24.R1' AND "
            f"p.FASFL = 'Y' GROUP BY 1"
        )
    }
    check(
        "endpoint_summary derived == direct gold count",
        {x["arm"]: x["derived"] for x in s["by_arm"]} == direct,
        (s["by_arm"], direct),
    )
    check(
        "endpoint_summary cites SAP section",
        s["citation"]["document"] == "CSL-A-SAP-v1.0" and s["citation"]["section"] == "9.4.1",
        s["citation"],
    )

    # 2. participant_trace vs oracle
    for u, rv in (("CSL-A-FX-05", "R1"), ("CSL-A-FX-05", "R2"), ("CSL-A-FX-07", "R1"), ("CSL-B-FX-18", "R1")):
        ep = "EP-B-WT24" if u.startswith("CSL-B") else "EP-A-WT24"
        t = T["participant_trace"](query, u, f"{ep}.{rv}")
        e = oracle[u][rv]
        ok = t["result_status"] == e["status"] and (
            "value" not in e or abs(float(t["pct_change"]) - e["value"]) < 1e-9
        )
        check(f"participant_trace {u} {rv} == oracle", ok, (t["result_status"], t["pct_change"], e))
    t = T["participant_trace"](query, "CSL-A-FX-07", "EP-A-WT24.R1")
    check(
        "trace keeps every candidate with a reason",
        all(c["reason"] for c in t["candidates"])
        and any(c["reason"] == "FOLLOWUP_TIE_LOST" for c in t["candidates"]),
    )

    # 3. amendment_impact vs direct gold counts and oracle lists
    am = T["amendment_impact"](query, limit=200)
    became = int(
        query(f"SELECT count_if(endpoint_became_derivable) n FROM {cs}.gold_amendment_impact")[0]["n"]
    )
    check("amendment became_derivable == direct", am["counts"]["became"] == became, (am["counts"], became))
    fx = T["amendment_impact"](query, site_id="SITE-104", limit=200)
    ids = {r["USUBJID"] for r in fx["affected"]}
    check(
        "amendment affected includes FX-05 and FX-20 (candidates changed)",
        {"CSL-A-FX-05", "CSL-A-FX-20", "CSL-A-FX-04"} <= ids,
        sorted(ids)[:10],
    )

    # 4. rules
    rs = T["rule_status"](query, "CSL-A")
    states = {(x["value"], x["review_state"]) for x in rs["statements"]}
    check(
        "rule_status: ±21 is a candidate, not executable",
        ("21", "candidate") in states
        and {int(x["window_half_width_days"]) for x in rs["executable_rules"]} == {7, 14},
        states,
    )
    c1 = T["compare_endpoints"](query, "EP-A-WT24.R1", "EP-A-WT24.R2")
    check(
        "R1 vs R2 differ ONLY in the window",
        [d["parameter"] for d in c1["differences"]] == ["window_half_width_days"],
        c1["differences"],
    )
    c2 = T["compare_endpoints"](query, "EP-A-WT24.R2", "EP-B-WT24.R1")
    check(
        "CSL-A vs CSL-B not equivalent",
        not c2["equivalent"]
        and {"baseline_method", "target_offset_days", "tie_breaker"}
        <= {d["parameter"] for d in c2["differences"]},
        c2["differences"],
    )
    rd = T["rule_definition"](query, "EP-A-WT24.R2")
    check(
        "rule_definition returns the section text", rd["section_text"] and "±14" in rd["section_text"]["text"]
    )

    # 5. semantics: membership via closure vs expectations from the hand oracle / gate doc
    for cls, cid, want in (
        ("WRC-V1", "MONDO:0005439", True),
        ("WRC-V1", "MONDO:0008585", False),
        ("WRC-V1", "MONDO:0007147", False),
        ("WRC-V2", "MONDO:0007147", True),
        ("WRC-V1", "MONDO:0001302", False),
        ("WRC-V1", "MONDO:0001999", False),
    ):
        m = T["class_membership"](query, cls, cid)
        check(f"class_membership {cls} {cid} == {want}", m["member"] == want, m)

    # 6. contraindication SQL (closure tables) vs the Python graph walk (direct edges): two implementations
    onto = default_ontology()
    excluded = {"MESH:D004342"}
    for cid in (
        "MONDO:0012819",
        "MONDO:0015277",
        "MONDO:0007958",
        "MONDO:0008234",
        "MONDO:0008433",
        "MONDO:0000775",
        "MONDO:0005148",
        "MONDO:0005147",
    ):
        sql = set(T["contraindication_check"](query, cid)["drugs"])
        py = {onto.label(h["drug"]) for h in onto.contraindications(cid, "MEDRT:N0000178480", excluded)}
        check(f"contraindication {cid} SQL == graph walk", sql == py, (sorted(sql), sorted(py)))

    dm = T["dataset_mapping"](query)
    unit = next((r for r in dm["mappings"] if r["variable"] == "SDTM:VS.VSORRESU"), None)
    allowed = (
        sorted(unit["allowed_values"])
        if unit and isinstance(unit["allowed_values"], list)
        else str(unit and unit["allowed_values"])
    )
    check(
        "dataset_mapping: VSORRESU allows LB/g/kg and maps to silver_vs",
        unit is not None
        and all(x in str(allowed) for x in ('"LB"', '"g"', '"kg"'))
        and unit["physical_column"],
        unit,
    )
    el = T["eligibility_explain"](query, "CSL-A-FX-25")
    check(
        "eligibility_explain FX-25 excluded by EXC-CI only",
        [c["criterion_id"] for c in el["criteria"] if c["outcome"] == "TRIGGERED"] == ["EXC-CI"],
        el["criteria"],
    )

    # 7. input whitelisting
    for bad in (
        lambda: T["participant_trace"](query, "x'; DROP TABLE t; --", "EP-A-WT24.R1"),
        lambda: T["endpoint_summary"](query, "EP-A-WT24.R1' OR 1=1 --"),
        lambda: T["class_membership"](query, "WRC-V1", "MONDO:0005439' OR '1'='1"),
    ):
        try:
            bad()
            check("malicious input rejected", False)
        except InputError:
            check("malicious input rejected", True)

    # 8. supervisor routing + abstention + isolation
    cases = [
        ("What is the Week 24 endpoint summary for Study A under rule version 1?", "endpoint_summary"),
        ("What is the mean percent change at Week 24?", "clarify"),
        ("Why was CSL-A-FX-05's observation excluded under R1?", "participant_trace"),
        ("What changed after amendment 1?", "amendment_impact"),
        ("Do Studies A and B use equivalent baseline definitions?", "compare_endpoints"),
        ("The latest document mentions a wider window. Has that rule been approved?", "rule_status"),
        ("Where is this measurement represented in the standardized dataset?", "dataset_mapping"),
        ("Can this synthetic result establish treatment superiority?", "abstain"),
        ("What is the HEDIS GSD compliance rate?", "abstain"),
        ("Is MONDO:0012819 contraindicated for the GLP-1 class?", "contraindication_check"),
    ]
    for q, want in cases:
        got = sup.route(q)["tool"]
        check(f"route: {q[:55]!r} -> {want}", got == want, got)
    ls_tools = set(demo_registry.tools_for("life_sciences_clinical", a.catalog))
    hedis_tools = set(demo_registry.tools_for("healthcare_hedis", a.catalog))
    check("tool registries are disjoint per demo", not (ls_tools & hedis_tools), ls_tools & hedis_tools)
    out = demo_registry.answer("life_sciences_clinical", "What is the HEDIS KED rate?", a.catalog, query)
    check(
        "cross-demo question abstains with demo_id stamped",
        out["tool"] == "abstain" and out["demo_id"] == "life_sciences_clinical",
        out,
    )

    print(f"\n{'ALL PASS' if not fails else f'{len(fails)} FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
