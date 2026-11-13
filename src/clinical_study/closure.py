"""Transitive closures for the life-sciences KB hierarchies, computed in Python (SYNTHETIC demo; ADR-0022).

The hierarchies are small (hundreds to a few thousand nodes), so a driver-side BFS is exact and takes
seconds. The iterative Spark join in src/semantic/build_closure.py grows its lineage every level and ran for
over an hour on MONDO/MeSH depth (fine for the shallow HEDIS ICD subset, which keeps using it).

Same output contract as build_closure.py: one row per (ancestor, descendant) at the SHORTEST distance, a
depth-0 self row for every node, and relationship_path recording the edge types crossed.
"""

from __future__ import annotations

from collections import defaultdict, deque


def closure_rows(hier: list[dict]) -> list[dict]:
    """hier rows: code, parent_code (None for roots), name, relationship."""
    names, children = {}, defaultdict(list)
    for r in hier:
        names.setdefault(r["code"], r.get("name"))
        if r.get("parent_code"):
            names.setdefault(r["parent_code"], None)
            children[r["parent_code"]].append((r["code"], r.get("relationship") or ""))
    for v in children.values():
        v.sort()
    out = []
    for a in sorted(names):
        seen = {a: (0, "")}
        q = deque([a])
        while q:
            x = q.popleft()
            d, path = seen[x]
            for c, rel in children.get(x, []):
                if c not in seen:
                    seen[c] = (d + 1, rel if not path else f"{path}>{rel}")
                    q.append(c)
        for desc, (d, path) in seen.items():
            out.append(
                {
                    "ancestor_code": a,
                    "ancestor_name": names.get(a),
                    "descendant_code": desc,
                    "descendant_name": names.get(desc),
                    "depth": d,
                    "relationship_path": path,
                }
            )
    return out


def validate(hier: list[dict], rows: list[dict]) -> list[str]:
    errs = []
    keys = [(r["ancestor_code"], r["descendant_code"]) for r in rows]
    if len(keys) != len(set(keys)):
        errs.append("duplicate (ancestor, descendant) keys")
    nodes = {r["code"] for r in hier} | {r["parent_code"] for r in hier if r.get("parent_code")}
    selfs = {
        r["ancestor_code"] for r in rows if r["depth"] == 0 and r["ancestor_code"] == r["descendant_code"]
    }
    if nodes - selfs:
        errs.append(f"{len(nodes - selfs)} nodes without a self row")
    d1 = {(r["ancestor_code"], r["descendant_code"]) for r in rows if r["depth"] == 1}
    missing = [
        (r["parent_code"], r["code"])
        for r in hier
        if r.get("parent_code") and (r["parent_code"], r["code"]) not in d1
    ]
    if missing:
        errs.append(f"{len(missing)} direct edges not at depth 1")
    return errs
