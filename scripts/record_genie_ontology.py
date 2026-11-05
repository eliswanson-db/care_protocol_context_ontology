"""Record Genie Ontology's OWN retrieval for the 10 benchmark questions, per workspace, as the calling user.

Runs Genie One (responses API) and keeps ONLY its ontology retrieval: the knowledge-snippet search results
(inferred snippets + Pages) and the Page bodies it read. Genie One's answer, SQL and other tools are discarded.
Retrieval is identity-scoped, so each recording notes who ran it.

  .venv/bin/python scripts/record_genie_ontology.py [--profiles ECT,DMVM]
-> docs/benchmark/genie_ontology_retrieval.json (+ the app's bundled copy)
"""
import argparse
import csv
import datetime
import json
import os
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "app"))
from databricks.sdk import WorkspaceClient  # noqa: E402

from server.genie_trace import parse  # noqa: E402

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))


def events(w, question):
    resp = w.api_client.do(
        "POST", "/api/2.0/data-rooms/tools/onechat/responses",
        body={"input": [{"role": "user", "type": "message", "content": [{"type": "input_text", "text": question}]}],
              "enable_viz": False},
        headers={"Accept": "text/event-stream", "Content-Type": "application/json"}, raw=True)
    out = []
    for line in resp["contents"].read().decode("utf-8", "replace").splitlines():
        s = line[5:].strip() if line.startswith("data:") else line.strip()
        if s.startswith("{"):
            try:
                out.append(json.loads(s))
            except json.JSONDecodeError:
                pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profiles", default="ECT,DMVM")
    ap.add_argument("--retry-missing", action="store_true",
                    help="re-run only questions where Genie One did not call its knowledge search (up to 3 attempts)")
    args = ap.parse_args()
    dst = os.path.join(ROOT, "docs/benchmark/genie_ontology_retrieval.json")
    prev = json.load(open(dst)) if args.retry_missing and os.path.isfile(dst) else None
    qs = [(r["question_id"], r["question"]) for r in csv.DictReader(open(os.path.join(ROOT, "docs/benchmark/capability_matrix.csv")))]
    result = {"recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "workspaces": {}}
    for prof in args.profiles.split(","):
        w = WorkspaceClient(profile=prof)
        who = w.current_user.me().user_name
        host = w.config.host.replace("https://", "").split(".")[0]

        old = ((prev or {}).get("workspaces", {}).get(prof.lower(), {}) or {}).get("questions", {})

        def one(item):
            qid, q = item
            if prev and old.get(qid, {}).get("queries"):
                return qid, old[qid]                      # already has a real ontology search: keep it
            attempts = 3 if prev else 1
            for n in range(1, attempts + 1):
                try:
                    t = parse(events(w, q))
                except Exception as e:  # noqa: BLE001
                    rec = {"error": f"{type(e).__name__}: {str(e)[:200]}"}
                    continue
                rec = {"queries": [s["query"] for s in t["snippet_searches"]],
                       "snippets": [x for s in t["snippet_searches"] for x in s["snippets"]],
                       "pages": [x for s in t["snippet_searches"] for x in s["pages"]],
                       "pages_read": t["pages_read"], "attempts": n}
                if rec["queries"]:
                    return qid, rec
            rec["skipped_search"] = True                   # Genie One never ran its ontology search on any attempt
            return qid, rec
        with ThreadPoolExecutor(max_workers=4) as ex:
            by_q = dict(ex.map(one, qs))
        result["workspaces"][prof.lower()] = {"host": host, "identity": who, "questions": by_q}
        for qid, r in by_q.items():
            print(f"{prof:<5} {qid:<24} " + ("SKIPPED SEARCH x3 " if r.get("skipped_search") else "") + (r.get("error") or
                  f"snippets={len(r['snippets'])} (on-topic {sum(x['on_topic'] for x in r['snippets'])}) "
                  f"pages={len(r['pages'])} read={len(r['pages_read'])}"))
    json.dump(result, open(dst, "w"), indent=1)
    shutil.copy(dst, os.path.join(ROOT, "src/app/server/benchmark_data/genie_ontology_retrieval.json"))
    print(f"-> {dst}")


if __name__ == "__main__":
    main()
