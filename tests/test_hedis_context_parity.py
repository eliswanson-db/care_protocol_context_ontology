"""HEDIS context parity (ADR-0025 applied to HEDIS; docs/benchmark/CONTEXT_CONSISTENCY_AUDIT.md).

- the Page stating the care-protocol edges is generated from protocol_edges.csv and current (same facts as the
  graph and the closure/edge tables)
- Pages state the constants the pipeline actually computes with (Step-3 trigger and window, MAD PDC)
- Pages quote no data-derived percentages (they go stale whenever data is regenerated)
"""

from __future__ import annotations

import csv
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "docs/ontology/pages"
PIPE = (ROOT / "src/pipelines/measures.py").read_text()


def _gen():
    spec = importlib.util.spec_from_file_location("gen", ROOT / "scripts/gen_protocol_pages.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_protocol_rules_page_is_current_and_complete():
    page = (PAGES / "care-protocol-rules.md").read_text()
    assert page == _gen().build(), "rerun scripts/gen_protocol_pages.py"
    with open(ROOT / "src/terminology/protocol_edges.csv", encoding="utf-8") as f:
        n = sum(1 for _ in csv.DictReader(f))
    assert len(re.findall(r"^- ", page, re.M)) == n


def test_step3_page_states_the_computed_rule():
    trig = float(re.search(r"^A1C_TRIGGER = ([\d.]+)", PIPE, re.M).group(1))
    days = int(re.search(r"^FOLLOWUP_DAYS = (\d+)", PIPE, re.M).group(1))
    assert re.search(r'value_num"\) > A1C_TRIGGER', PIPE), (
        "trigger comparison changed: update the Step-3 Page"
    )
    behavior = (ROOT / "src/data_generation/care_behavior.py").read_text()
    assert re.search(r'v_cal"\) > A1C_TRIGGER', behavior), "care-behavior model must use the same trigger"
    page = (PAGES / "protocol-step-3.md").read_text().replace("**", "")
    assert f"above {trig:.1f}%" in page and f"within {days} days" in page
    drift = (ROOT / "src/app/frontend/src/tabs/DriftLab.tsx").read_text()
    assert f"within {days} days of an A1c result above {trig:.0f}%" in drift


def test_mad_page_states_the_computed_rule():
    mv = (ROOT / "src/semantic/metric_views/mad_compliance.metric_view.sql").read_text()
    assert (
        "pdc >= 0.8" in mv
        and re.search(r'F.col\("fills"\) >= 2', PIPE)
        and re.search(r'F.col\("age"\) >= 18\)', PIPE)
    )
    page = (PAGES / "mad.md").read_text().replace("**", "")
    assert "PDC ≥ 80%" in page and "at least 2 fills" in page and "18+" in page


def test_pages_quote_no_data_derived_percentages():
    allowed = re.compile(r"^(<|>|≥|≤)?\s*(7|8|9|80)(\.0)?\s*%$")
    bad = []
    for p in sorted(PAGES.glob("*.md")):
        for m in re.finditer(r"(~\s*)?[<>≥≤]?\s*\d+(\.\d+)?\s*%", p.read_text()):
            if m.group(0).lstrip().startswith("~") or not allowed.match(m.group(0).strip()):
                bad.append((p.name, m.group(0)))
    assert not bad, bad


def test_dashboards_and_seeded_queries_use_current_rules():
    # Dashboards and seeded query history are mined into Genie Ontology's inferred snippets, so a stale rule there
    # becomes stale context (the q7 `status` miss). Gold has no verdict columns; GSD's gap is "> 9% or no test".
    import json

    removed = re.compile(r"\b(numerator_flag|egfr_flag|uacr_flag|a1c_lt8|a1c_gt9)\b|\bstatus\s*=|GROUP BY status\b")
    texts = {}
    for p in sorted((ROOT / "resources").glob("*.lvdash.json")):
        for ds in json.loads(p.read_text())["datasets"]:
            texts[f"{p.name}:{ds['name']}"] = " ".join(ds.get("queryLines") or [ds.get("query", "")])
    texts["seed_query_history.py"] = (ROOT / "src/semantic/seed_query_history.py").read_text()
    for name, t in texts.items():
        assert not removed.search(t), (name, removed.search(t).group(0))
        assert not re.search(r"gold_adherence_gsd WHERE evidence_datetime IS NULL[\"']", t), (name, "old GSD gap rule")
    # The dashboard worklist applies each metric view's own rules (it needs patient rows the views don't expose).
    gaps = next(v for k, v in texts.items() if k.endswith("hedis_quality.lvdash.json:ds_gaps"))
    import yaml
    for m in ("gsd", "ked", "bpd", "spd", "eed"):
        txt = (ROOT / f"src/semantic/metric_views/{m}_compliance.metric_view.sql").read_text()
        body = txt[txt.index("$$") + 2: txt.rindex("$$")].replace("{catalog}", "c").replace("{schema}", "s")
        dims = {d["name"]: d["expr"] for d in yaml.safe_load(body)["dimensions"]}
        assert dims["Gap Reason"] in gaps and dims["Compliance Status"] in gaps, f"{m}: worklist drifted from the view"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
