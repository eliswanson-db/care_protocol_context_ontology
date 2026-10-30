"""Local self-test: route questions through the A6 supervisor against live data via `aitools query`.

Run: python src/mcp/_selftest.py --profile ECT --catalog eli_test_classic_catalog
Proves the governed tools return correct, deterministic answers and the router picks the right tool.
"""
import argparse
import json
import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from care_protocol_tools import make_tools  # noqa: E402
from supervisor import answer, summarize  # noqa: E402


def make_query(profile):
    def query(sql):
        out = subprocess.run(
            ["databricks", "experimental", "aitools", "tools", "query", sql, "--profile", profile, "-o", "json"],
            capture_output=True, text=True)
        if out.returncode != 0:
            raise RuntimeError(out.stderr.strip())
        txt = out.stdout.strip()
        return json.loads(txt) if txt and txt[0] == "[" else []
    return query


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--catalog", default="eli_test_classic_catalog")
    args = ap.parse_args()

    tools = make_tools(args.catalog)
    query = make_query(args.profile)
    questions = [
        "What is the GSD compliance rate?",
        "What share of eligible diabetic patients are on statin therapy (SPD)?",
        "How many patients are in the diabetes cohort?",
        "Show care gaps for KED",
        "What codes are under E11?",
        "Which value set codes for SPD_STATIN?",
        "What is driving the revenue decline?",  # should fall back to Genie
    ]
    for q in questions:
        ans = answer(q, tools, query)
        print(f"Q: {q}\n  -> tool={ans['tool']}: {summarize(ans)}\n")


if __name__ == "__main__":
    main()
