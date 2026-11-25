"""Audit a benchmark run for judgments a hand check must look at (protocol v3, ADR-0028). Read-only, offline.

Flags, for every run of every cell (not just the stored one):
  * value_in_result   a run judged a miss whose query result contains the expected fact's numbers;
  * value_in_context  a cell judged a miss whose stored context contains the expected fact's numbers;
  * runs_disagree     the runs' outcomes differ;
  * contradicted      a contradiction verdict, with its quote (wrong answers must be right to call wrong);
  * declined_partial  the agent declined although the context already stated some facts.
A cell's note in the question file's hand_notes should address every flag on it.

    .venv/bin/python -I scripts/benchmark_audit.py                       # HEDIS
    .venv/bin/python -I scripts/benchmark_audit.py --demo life_sciences_clinical
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FILES = {"healthcare_hedis": ("questions_v2.yaml", "benchmark_v2.json"),
         "life_sciences_clinical": ("ls_questions.yaml", "ls_benchmark.json")}


def numbers(text: str) -> list[str]:
    """The values a fact asserts: numbers with a decimal point or at least three digits (rates, counts, codes), not
    dates, years or section numbers."""
    t = re.sub(r"\d{4}-\d{2}-\d{2}|\bMY\d{4}\b|\b(?:19|20)\d{2}\b|§\s*[\d.]+|CSL-[AB]-\d{3}-\d{4}|SITE-\d{3}|"
               r"[0-9a-f]{8}-[0-9a-f-]{27}|\b[A-Z_]+:[\w.]+|(?:protocol|SAP|version|v)\s*\d+\.\d+", " ", text,
               flags=re.IGNORECASE)
    out = []
    for n in re.findall(r"(?<![\w.])[−-]?\d[\d,]*\.?\d*(?![\w])", t):
        v = n.replace(",", "").replace("−", "-").lstrip("-").rstrip(".")
        if "." in v or len(v) >= 3:
            out.append(v)
    return out


def found(values: list[str], text: str) -> list[str]:
    flat = (text or "").replace(",", "")
    hits = []
    for v in values:
        if v in flat:
            hits.append(v)
        elif "." in v:  # 37.2% may appear as 0.372 or 0.3719...
            try:
                f = float(v)
            except ValueError:
                continue
            if any(abs(float(x) * 100 - f) < 0.06 or abs(float(x) - f) < 0.006
                   for x in re.findall(r"-?\d+\.\d+", flat)):
                hits.append(v)
    return hits


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", default="healthcare_hedis", choices=sorted(FILES))
    a = ap.parse_args()
    qfile, rfile = FILES[a.demo]
    spec = yaml.safe_load((ROOT / "docs/benchmark" / qfile).read_text())
    rows = json.loads((ROOT / "docs/benchmark" / rfile).read_text())["rows"]
    notes = spec.get("hand_notes") or {}
    flags: list[tuple] = []
    for r in rows:
        cell = (r["qid"], r["arm"])
        runs = r.get("runs") or [r]
        outs = [x.get("outcome") for x in runs]
        if len(set(outs)) > 1:
            flags.append((*cell, "runs_disagree", str(outs)))
        if r.get("outcome") in ("incomplete",) and not r.get("sql") and r.get("declined_reason"):
            flags.append((*cell, "declined_partial", r["declined_reason"][:120]))
        for i, x in enumerate(runs):
            facts = x.get("facts") or r.get("facts") or []
            for f in facts:
                vals = numbers(f["fact"])
                c, res = f.get("in_context") or {}, f.get("in_result") or {}
                if not (c.get("ok") or res.get("ok")):
                    hit = found(vals, x.get("sql_result") or "")
                    if vals and len(hit) >= max(1, (len(vals) + 1) // 2):
                        flags.append((*cell, "value_in_result", f"run {i}: {hit} of {vals} | {f['fact'][:70]}"))
                    if i == 0:
                        hitc = found(vals, r.get("context") or "")
                        if vals and len(hitc) >= max(1, (len(vals) + 1) // 2):
                            flags.append((*cell, "value_in_context", f"{hitc} of {vals} | {f['fact'][:70]}"))
                for j in (c, res):
                    if j.get("verdict") == "contradicted":
                        flags.append((*cell, "contradicted", f"run {i}: {str(j.get('quote'))[:90]}"))
    seen = set()
    for qid, arm, kind, detail in sorted(flags):
        key = (qid, arm, kind, detail.split(":", 1)[-1])
        if key in seen:
            continue
        seen.add(key)
        noted = "noted" if (notes.get(arm) or {}).get(qid) else "NO NOTE"
        print(f"{qid:5} {arm:15} {kind:17} [{noted}] {detail}")
    print(f"\n{len(seen)} flag(s) on {len({(q, a) for q, a, *_ in seen})} cell(s).")


if __name__ == "__main__":
    main()
