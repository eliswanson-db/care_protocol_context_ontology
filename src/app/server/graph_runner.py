"""Graph runner: deterministic traversal tools over the published Ontobricks graph (node + edge table), in memory.

networkx-style adjacency lists, no extra dependency (the same idea as a networkx / GraphFrames runner over a node and
edge table). The point is the graph's real advantage: ONE tool call answers a multi-hop question deterministically,
instead of an agent hand-writing self-joins over raw triples.

Loaded: every edge of the published triplestore except the observation layer (hasObservation / ofTest / resultValue
and the Observation nodes' rdf:type -- ~15M rows that no tool here needs). Literal-valued predicates (labels, ages,
thresholds, codes) become node attributes. Node ids are IRIs with the ontology namespace stripped, exactly as they
appear in the retrieved context: "Patient/<uuid>", "icd/E11.22", "rx/314231", "DrugClass/DRUGCLASS-STATIN".

Tools (all read-only, all deterministic):
  find_nodes(text, type=None)                    nodes whose label or id contains the text
  neighbors(node, hops=1, predicates=None)        the edges around a node
  routes(node, predicate, direction="out")        EVERY chain from a node following one predicate (e.g. subClassOf
                                                  up to the roots) -- all routes, not just the shortest
  paths(source, target, max_hops=6)               all simple paths between two nodes; other patients are never
                                                  traversed through (patients are endpoints only)
  match(pattern, select, limit=10)                a graph pattern (motif): [[s, p, o], ...] where s / o are node ids,
                                                  literals or ?variables and p may end in * (0+ hops) or + (1+ hops);
                                                  returns the number of distinct values of `select` plus sample rows
"""
from __future__ import annotations

import json
import re
import time
from collections import defaultdict, deque

NS = "https://care-protocol.example/ontology/"
_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
_SKIP_PREDS = ("hasObservation", "ofTest", "resultValue")
_LITERAL_PREDS = {"label", "ageAtPeriodEnd", "thresholdValue", "icd10Code", "loincCode", "rxnormCode", "valueSetId"}
MAX_ROWS = 50


def _short(x: str) -> str:
    if x.startswith(NS):
        return x[len(NS):]
    if x.startswith("https://care-protocol.example/ontology#"):
        return x.split("#", 1)[1]
    return x


def _pred(p: str) -> str:
    return re.split(r"[#/]", p)[-1]


class Graph:
    def __init__(self, table: str):
        self.table = table
        self.out: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        self.inn: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        self.attrs: dict[str, dict[str, str]] = defaultdict(dict)
        self.types: dict[str, str] = {}
        self.n_edges = 0

    def add(self, s: str, p: str, o: str):
        s, pn = _short(s), _pred(p)
        if pn == "type":
            self.types[s] = _short(o)
            return
        if pn in _LITERAL_PREDS or not (o.startswith("http://") or o.startswith("https://")):
            self.attrs[s][pn] = o
            return
        o = _short(o)
        self.out[s][pn].append(o)
        self.inn[o][pn].append(s)
        self.n_edges += 1

    # ---- helpers -----------------------------------------------------------------------------------------------
    def label(self, n: str) -> str:
        a = self.attrs.get(n, {})
        return a.get("label") or ""

    def node_text(self, n: str) -> str:
        lab = self.label(n)
        return f"{n} ({lab})" if lab else n

    def kind(self, n: str) -> str:
        return self.types.get(n) or n.split("/", 1)[0]

    def exists(self, n: str) -> bool:
        return n in self.out or n in self.inn or n in self.attrs

    # ---- tools -------------------------------------------------------------------------------------------------
    def find_nodes(self, text: str, type: str | None = None, limit: int = 20) -> dict:
        t = text.lower().strip()
        hits = []
        for n in set(self.out) | set(self.inn) | set(self.attrs):
            if type and not n.lower().startswith(type.lower().rstrip("/") + "/") and self.kind(n).lower() != type.lower():
                continue
            if t in n.lower() or t in self.label(n).lower():
                hits.append(n)
        hits.sort(key=lambda n: (n.startswith("Patient/"), len(n)))
        return {"count": len(hits), "rows": [{"node": n, "label": self.label(n), "type": self.kind(n)}
                                             for n in hits[:limit]]}

    def neighbors(self, node: str, hops: int = 1, predicates: list[str] | None = None, limit: int = 200) -> dict:
        self._check(node)
        preds = set(predicates or [])
        seen, frontier, rows = {node}, [node], []
        for _ in range(max(1, min(int(hops), 3))):
            nxt = []
            for n in frontier:
                for p, os in self.out.get(n, {}).items():
                    if preds and p not in preds:
                        continue
                    for o in os:
                        rows.append({"s": n, "p": p, "o": o})
                        if o not in seen and not o.startswith("Patient/"):
                            seen.add(o)
                            nxt.append(o)
                for p, ss in self.inn.get(n, {}).items():
                    if preds and p not in preds:
                        continue
                    for s in ss:
                        if s.startswith("Patient/") and s != node:
                            continue  # never fan out across the whole patient population
                        rows.append({"s": s, "p": p, "o": n})
                        if s not in seen:
                            seen.add(s)
                            nxt.append(s)
            frontier = nxt
        return {"count": len(rows), "rows": rows[:limit],
                "attributes": {k: v for k, v in self.attrs.get(node, {}).items()}}

    def routes(self, node: str, predicate: str, direction: str = "out", max_hops: int = 10) -> dict:
        """Every maximal chain from `node` following `predicate` (out = toward parents for subClassOf)."""
        self._check(node)
        adj = self.out if direction == "out" else self.inn
        chains: list[list[str]] = []

        def walk(path):
            nxt = [m for m in adj.get(path[-1], {}).get(predicate, []) if m not in path]
            if not nxt or len(path) > max_hops:
                chains.append(path)
                return
            for m in nxt:
                walk(path + [m])
        walk([node])
        arrow = f" -[{predicate}]-> " if direction == "out" else f" <-[{predicate}]- "
        return {"count": len(chains), "rows": [{"route": arrow.join(self.node_text(n) for n in c), "end": c[-1],
                                                "hops": len(c) - 1} for c in chains[:MAX_ROWS]]}

    def paths(self, source: str, target: str, max_hops: int = 6, limit: int = 20) -> dict:
        """All simple paths source -> target over edges in either direction; patients other than the endpoints are
        never traversed, so a path can't wander through the population."""
        self._check(source)
        self._check(target)
        found: list[list[tuple[str, str, str]]] = []
        q = deque([(source, [source], [])])
        while q and len(found) < limit:
            n, nodes, steps = q.popleft()
            if len(steps) >= max_hops:
                continue
            nbrs = [(p, o, "->") for p, os in self.out.get(n, {}).items() for o in os] + \
                   [(p, s, "<-") for p, ss in self.inn.get(n, {}).items() for s in ss]
            for p, m, d in nbrs:
                if m in nodes or (m.startswith("Patient/") and m != target):
                    continue
                st = steps + [(p, m, d)]
                if m == target:
                    found.append(st)
                else:
                    q.append((m, nodes + [m], st))
        rows = []
        for st in found:
            txt, prev = self.node_text(source), source
            for p, m, d in st:
                txt += (f" -[{p}]-> " if d == "->" else f" <-[{p}]- ") + self.node_text(m)
                prev = m
            rows.append({"path": txt, "hops": len(st)})
        return {"count": len(rows), "rows": rows}

    def match(self, pattern: list[list[str]], select: str, limit: int = 10) -> dict:
        """Graph pattern (motif) matching with backtracking. `select` is the ?variable to count distinct values of."""
        pats = [tuple(x) for x in pattern]
        if not pats or any(len(x) != 3 for x in pats):
            raise ValueError("pattern must be a list of [subject, predicate, object] triples")
        for s, p, o in pats:
            for term in (s, o):
                if not term.startswith("?") and not self.exists(term):
                    raise ValueError(f"node {term!r} is not in the graph (ids look like icd/E11.22, "
                                     f"DrugClass/DRUGCLASS-STATIN, Patient/<uuid>)")
        select = select.strip()
        if not select.startswith("?"):
            select = "?" + select  # accept "p" for "?p"
        if not any(select in (s, o) for s, _, o in pats):
            raise ValueError(f"select {select!r} is not a variable in the pattern")

        def objs(s, p):
            base, mode = (p[:-1], p[-1]) if p[-1:] in "*+" else (p, "")
            if not mode:
                return self.out.get(s, {}).get(base, [])
            return self._closure(s, base, self.out, mode == "*")

        def subjs(o, p):
            base, mode = (p[:-1], p[-1]) if p[-1:] in "*+" else (p, "")
            if not mode:
                return self.inn.get(o, {}).get(base, [])
            return self._closure(o, base, self.inn, mode == "*")

        results: set[str] = set()
        samples: list[dict] = []
        deadline = time.time() + 60

        def bound(t, b):
            return b.get(t, t) if t.startswith("?") else t

        def solve(rem, b):
            if time.time() > deadline:
                raise TimeoutError("pattern too broad (>60s); anchor it on a specific node")
            if not rem:
                v = b.get(select)
                if v is not None and v not in results:
                    results.add(v)
                    if len(samples) < limit:
                        samples.append(dict(b))
                return
            # most-bound pattern next
            def score(x):
                s, _, o = x
                return (not bound(s, b).startswith("?")) + (not bound(o, b).startswith("?"))
            i = max(range(len(rem)), key=lambda k: score(rem[k]))
            s, p, o = rem[i]
            rest = rem[:i] + rem[i + 1:]
            bs, bo = bound(s, b), bound(o, b)
            if not bs.startswith("?"):
                cands = objs(bs, p)
                if not bo.startswith("?"):
                    if bo in cands:
                        solve(rest, b)
                    return
                for c in cands:
                    solve(rest, {**b, bo: c})
            elif not bo.startswith("?"):
                for c in subjs(bo, p):
                    solve(rest, {**b, bs: c})
            else:
                base = p.rstrip("*+")
                for sn, pm in list(self.out.items()):
                    for c in pm.get(base, []):
                        solve(rest, {**b, bs: sn, bo: c})
        solve(pats, {})
        return {"count": len(results), "select": select,
                "rows": [{k: self.node_text(v) for k, v in r.items()} for r in samples]}

    # ---- internals ---------------------------------------------------------------------------------------------
    def _closure(self, start, pred, adj, include_self):
        seen, out, q = {start}, ([start] if include_self else []), deque([start])
        while q:
            n = q.popleft()
            for m in adj.get(n, {}).get(pred, []):
                if m not in seen:
                    seen.add(m)
                    out.append(m)
                    q.append(m)
        return out

    def _check(self, node: str):
        if not self.exists(node):
            raise ValueError(f"node {node!r} is not in the graph")


TOOLS = {
    "find_nodes": "find_nodes(text, type=None): nodes whose label or id contains text",
    "neighbors": "neighbors(node, hops=1, predicates=None): edges around a node (max 3 hops)",
    "routes": "routes(node, predicate, direction='out'): EVERY chain following one predicate, e.g. "
              "routes('icd/E11.22', 'subClassOf') lists each route up to a root",
    "paths": "paths(source, target, max_hops=6): all simple paths between two nodes",
    "match": "match(pattern, select): count distinct ?select over a pattern of [s, p, o] triples; p may end in * "
             "(0+ hops) or + (1+ hops), e.g. [['?p','hasDiagnosis','?dx'], ['?dx','subClassOf*','icd/N18']]",
}


def call(g: Graph, tool: str, args: dict) -> dict:
    if tool not in TOOLS:
        raise ValueError(f"unknown graph tool {tool!r}; choose one of {sorted(TOOLS)}")
    return getattr(g, tool)(**(args or {}))


def render(result: dict) -> str:
    head = f"{result.get('count')} result(s)" + (f" for {result['select']}" if result.get("select") else "")
    rows = result.get("rows") or []
    body = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows[:MAX_ROWS])
    attrs = result.get("attributes")
    return head + ("\n" + body if body else "") + (f"\nnode attributes: {json.dumps(attrs)}" if attrs else "")


# ---- loading ---------------------------------------------------------------------------------------------------
_CACHE: dict[str, tuple[float, Graph]] = {}


def load(table: str, fetch_all, ttl_s: int = 3600) -> Graph:
    """Load the node/edge layer of `table` (catalog.schema.<base>_graph). `fetch_all(sql) -> iterable of rows`
    must page through large results (see warehouse.fetch_all)."""
    hit = _CACHE.get(table)
    if hit and time.time() - hit[0] < ttl_s:
        return hit[1]
    skip = ", ".join(f"'{NS}{p}'" for p in _SKIP_PREDS)
    sql = (f"SELECT subject, predicate, object FROM {table} WHERE predicate NOT IN ({skip}) "
           f"AND NOT (predicate = '{_RDF_TYPE}' AND (subject LIKE '%/Observation/%' OR subject LIKE '%/obs/%'))")
    g = Graph(table)
    for s, p, o in fetch_all(sql):
        g.add(s, p, o)
    _CACHE[table] = (time.time(), g)
    return g
