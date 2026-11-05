"""Capability-map benchmark runner (ADR-0010, docs/BENCHMARK_CHARTER.md).

Runs an arm over the ground-truth questions (docs/benchmark/ground_truth.yaml) and scores each answer against
the PINNED gold (values verified by src/benchmark/verify_gold.py). The deliverable is the capability map:
per class, which approach reaches the answer and HOW (which assets it used).

Arms:
  A1 (genie)      Genie One front door, driven headless via `databricks genie ask`. Reasons over the workspace
                  (metric views + comments + whatever Genie Ontology / Pages exist); we capture the assets it
                  cited (metric views, tables, Pages, SQL) as the lineage trail.
  M0 (metric_view) The governed metric-view layer ALONE -- a structural baseline for "is a definition enough?".
                  Applicable only where a metric view yields the answer directly (min_approach == metric_view);
                  structurally insufficient for subsumption / multiaxial / vintage / multi-hop / graph classes.

Scoring is a FIRST PASS -- the charter says ground truth is hand-verified, so answer_ok (does the primary gold
token appear in the answer, with numeric/percent variants) is an aid, and the per-question answer + cited
assets are written to the detail file for human audit. Nothing here is wired to an answer; A1 must reason.

Usage:
  python src/benchmark/run_capability_map.py --arm A1 --profile ECT \
      --ground_truth docs/benchmark/ground_truth.yaml --out /tmp/capmap
"""
import argparse
import json
import os
import re
import subprocess
import time

import yaml


def load_questions(path):
    doc = yaml.safe_load(open(path))
    qs = []
    for cls in doc["classes"]:
        for q in cls["questions"]:
            gold = q.get("gold_value_25k", q.get("gold_value_500", q.get("gold")))
            qs.append({
                "id": q["id"],
                "cls": cls["class"],
                "question": q["question"],
                "gold": str(gold),
                "min_approach": q.get("min_approach", "?"),
                "hypothesis": q.get("hypothesis", {}),
            })
    return qs


def gold_tokens(gold):
    """Salient tokens to look for in an answer: CLINIC-xx labels, and numbers with percent/comma variants.
    Returns (primary, all_variants). primary is the single token we treat as the pass/fail signal."""
    clinics = re.findall(r"CLINIC-\d+", gold)
    nums = re.findall(r"\d+\.?\d*", gold)
    variants = set(clinics)
    primary = clinics[0] if clinics else None
    for n in nums:
        variants.add(n)
        try:
            f = float(n)
        except ValueError:
            continue
        if 0 < f < 1:  # a rate -> also match its percent forms
            variants.add(f"{f * 100:.1f}")
            variants.add(str(round(f * 100)))
        if f >= 1000:  # also match a thousands-comma form
            variants.add(f"{int(f):,}")
        if primary is None:
            primary = n
    return primary, variants


def norm(s):
    return re.sub(r"\s+", " ", (s or "").lower())


def score(answer, gold):
    """Auto-score (a FIRST PASS; the hand-verified matrix in docs/benchmark/capability_map.md is authoritative).
    Returns (ok, matched, primary). ok is None = needs manual verdict (pure-prose gold, or an errored run)."""
    primary, variants = gold_tokens(gold)
    a = norm(answer)
    matched = sorted(v for v in variants if norm(v) in a)
    if a.startswith("error:"):
        return False, matched, primary
    if primary is None:  # pure-string gold: auto-score only yes/no; otherwise defer to human
        g = norm(gold)
        if g in ("yes", "no"):
            return (g in a), matched, primary
        return None, matched, primary
    # `matched` already holds every surface form of the gold (raw, percent for a rate, thousands-comma),
    # so a match on any of them is the pass signal. Small-int substring collisions are possible -> the
    # hand-verified matrix is authoritative (charter).
    return bool(matched), matched, primary


def run_genie(question, session, profile):
    """Drive Genie One headless; return (text, assets[], latency_s)."""
    t0 = time.time()
    cmd = ["databricks", "genie", "ask", "-s", session, "--output", "json", "--profile", profile, question]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
        d = json.loads(out.stdout)
        text = d.get("text", "") or ""
    except Exception as e:  # noqa: BLE001
        return f"ERROR: {e}", [], round(time.time() - t0, 1), [], False
    assets = []
    tool_names = []
    ontology_used = False
    for t in d.get("tool_calls", []):
        name = t.get("name", "")
        if name:
            tool_names.append(name)
        if t.get("sql"):
            assets.append(("sql", t["sql"][:300]))
        # Ontology-engagement signal (ADR-0018): did Genie One consult the native ontology for THIS answer?
        # search_knowledge_snippets = inferred-snippet retrieval; a knowledge_page asset = a modeled Page.
        if name == "search_knowledge_snippets":
            ontology_used = True
            assets.append(("snippet_search", (t.get("arguments") or "")[:200]))
        if name == "get_asset_info" and "knowledge_page" in (t.get("arguments") or ""):
            ontology_used = True
            assets.append(("knowledge_page", (t.get("arguments") or "")[:200]))
    assets += [("table", m) for m in sorted(set(re.findall(r"care_protocol\w*\.\w+\.\w+", text)))]
    if "/discover/pages/" in text:
        assets.append(("page", "Genie Ontology Page cited"))
        ontology_used = True
    if "_metrics" in text:
        assets.append(("metric_view", "metric view cited"))
    return text, assets, round(time.time() - t0, 1), tool_names, ontology_used


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["A1", "M0"], default="A1")
    ap.add_argument("--profile", required=True)
    ap.add_argument("--ground_truth", default="docs/benchmark/ground_truth.yaml")
    ap.add_argument("--out", default="/tmp/capmap")
    ap.add_argument("--only_class", default="", help="optional: run one class, e.g. 6_protocol_multihop")
    ap.add_argument("--ids", default="", help="optional: comma-separated question ids to run")
    ap.add_argument("--session_suffix", default="",
                    help="optional: new Genie session names (capmap_<id>_<suffix>) so answers don't carry prior context")
    ap.add_argument("--smoke", action="store_true",
                    help="run the 5-question representative smoke subset (fast dev loop; Genie One is slow)")
    args = ap.parse_args()

    # One id per key capability — fast iteration without paying for all 20 slow Genie calls.
    SMOKE_IDS = ["kpi_gsd_rate", "sub_kidney", "med_on_statin", "def_controlled_bp", "op_clinic_drift"]

    os.makedirs(args.out, exist_ok=True)
    qs = load_questions(args.ground_truth)
    if args.only_class:
        qs = [q for q in qs if q["cls"] == args.only_class]
    if args.smoke:
        qs = [q for q in qs if q["id"] in set(SMOKE_IDS)]
    elif args.ids:
        want = {x.strip() for x in args.ids.split(",") if x.strip()}
        qs = [q for q in qs if q["id"] in want]

    rows = []
    for q in qs:
        if args.arm == "M0":
            applicable = q["min_approach"] == "metric_view"
            rows.append({**q, "arm": "M0", "answer_ok": applicable, "verdict": q["hypothesis"].get("metric_view", "?"),
                         "answer": "metric-view layer applicable" if applicable else "no covering metric view",
                         "assets": [], "latency_s": 0.0, "matched": []})
            continue
        print(f"  A1 {q['id']} ...", flush=True)
        text, assets, dt, tool_names, ontology_used = run_genie(q["question"], f"capmap_{q['id']}" + (f"_{args.session_suffix}" if args.session_suffix else ""), args.profile)
        ok, matched, primary = score(text, q["gold"])
        rows.append({**q, "arm": "A1", "answer_ok": ok, "primary": primary, "matched": matched,
                     "answer": text[:600], "assets": assets, "latency_s": dt,
                     "tool_names": tool_names, "ontology_used": ontology_used})
        print(f"     {'OK ' if ok else 'XX '} gold={q['gold'][:40]!r} matched={matched} "
              f"{'[ontology]' if ontology_used else '[no-ontology]'} ({dt}s)")
        # Write after EACH question so a late failure (transient Genie error) never wipes a long run.
        json.dump(rows, open(os.path.join(args.out, f"{args.arm}_detail.json"), "w"), indent=2, default=str)

    # Capability-map rollup by class.
    by_cls = {}
    for r in rows:
        by_cls.setdefault(r["cls"], []).append(r["answer_ok"])
    print(f"\n=== {args.arm} capability map (answer reached gold, by class) ===")
    for cls in sorted(by_cls):
        v = by_cls[cls]
        n_manual = sum(x is None for x in v)
        tail = f" ({n_manual} manual)" if n_manual else ""
        print(f"  {cls:<24} {sum(x is True for x in v)}/{len(v)}{tail}")
    n_ok = sum(r["answer_ok"] is True for r in rows)
    n_manual = sum(r["answer_ok"] is None for r in rows)
    print(f"\n{args.arm}: {n_ok}/{len(rows)} reached gold auto ({n_manual} need manual verdict); "
          f"hand-verified matrix is authoritative.")
    if args.arm == "A1":
        n_ont = sum(bool(r.get("ontology_used")) for r in rows)
        print(f"{args.arm}: ontology consulted on {n_ont}/{len(rows)} answers "
              f"(search_knowledge_snippets / knowledge_page / cited Page) — the ADR-0018 ON/OFF signal.")

    detail = os.path.join(args.out, f"{args.arm}_detail.json")
    json.dump(rows, open(detail, "w"), indent=2, default=str)
    print(f"Per-question detail (answers + cited assets) -> {detail}")


if __name__ == "__main__":
    main()
