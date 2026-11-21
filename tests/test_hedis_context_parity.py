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


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
