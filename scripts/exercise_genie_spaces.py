"""Put real usage on the repo-managed Genie spaces: ask each space a few of its own sample questions.

Why: Genie One mines inferred snippets from workspace assets, and on ECT it mined the long-used dev spaces but none
of the managed (ect) spaces, three days after their knowledge stores were deployed. Usage is the one thing the dev
spaces have that ours didn't. This asks the questions a user would (the spaces' own sample questions, never a
benchmark question), as the calling identity, and reports what each space answered.

    .venv/bin/python -I scripts/exercise_genie_spaces.py --profile ECT [--per-space 3]

Read-only on data (Genie runs SELECTs); it creates Genie conversations in the spaces, which is the point.
"""

from __future__ import annotations

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml
from databricks.sdk import WorkspaceClient

ROOT = Path(__file__).resolve().parents[1]


def _benchmark_questions() -> set[str]:
    qs = yaml.safe_load((ROOT / "docs/benchmark/questions_v2.yaml").read_text())["questions"]
    return {q["question"].strip().lower() for q in qs}


def _titles(target: str = "ect") -> dict[str, str]:
    """{space body file -> deployed title}, read from the bundle (title + file_path in the same resource block)."""
    out = {}
    for f in ("databricks.yml", "resources/genie_spaces.yml"):
        t = (ROOT / f).read_text()
        for m in re.finditer(r"title:\s*(.+?)\n(?:(?!title:).)*?file_path:\s*\.?/?(?:resources/)?(\S+\.geniespace\.json)",
                             t, re.DOTALL):
            out[m.group(2)] = m.group(1).strip().replace("${bundle.target}", target)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--per-space", type=int, default=3)
    a = ap.parse_args()
    w = WorkspaceClient(profile=a.profile)
    held_out = _benchmark_questions()
    spaces = {s.title: s.space_id for s in w.genie.list_spaces().spaces or []}
    jobs = []
    for res, title in sorted(_titles().items()):
        spec = json.loads((ROOT / "resources" / res).read_text())
        qs = [" ".join(q.get("question") or []) for q in spec.get("config", {}).get("sample_questions", [])]
        qs = [q for q in qs if q.strip().lower() not in held_out][: a.per_space]
        if title not in spaces:
            print(f"skip {res}: '{title}' is not deployed")
            continue
        jobs += [(title, spaces[title], q) for q in qs]

    def ask(job):
        title, sid, q = job
        try:
            m = w.genie.start_conversation_and_wait(sid, q)
            return title, q, str(m.status.value if m.status else m.status)
        except Exception as e:  # noqa: BLE001 -- report every failure, keep going
            return title, q, f"error: {type(e).__name__}: {str(e)[:120]}"

    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(ask, jobs))
    for title, q, status in results:
        print(f"{status:<10} {title[:48]:<48} {q[:80]}")
    ok = sum(r[2] == "COMPLETED" for r in results)
    print(f"\n{ok}/{len(results)} conversations completed")


if __name__ == "__main__":
    main()
