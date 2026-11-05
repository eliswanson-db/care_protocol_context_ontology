import { AlertTriangle, Info } from "lucide-react";
import { Fragment, useEffect, useMemo, useState } from "react";
import { api, type A1Runs, type CapabilityMap } from "../api";
import { Collapsible } from "../components/Collapsible";
import { TIER, TierChip } from "../components/TierChip";
import { SIMPLE_APPROACHES, SIMPLE_QIDS, useSettings } from "../settings";

/** Simple mode: the same map cut to the simple questions x approaches, with the bars recounted from those cells. */
function simpleView(m: CapabilityMap): CapabilityMap {
  const arms = m.arms.filter((a) => SIMPLE_APPROACHES.includes(a.id));
  const classes = m.classes
    .map((c) => ({ ...c, questions: c.questions.filter((q) => SIMPLE_QIDS.includes(q.id)) }))
    .filter((c) => c.questions.length);
  const qs = classes.flatMap((c) => c.questions);
  const rollup = m.rollup
    .filter((r) => SIMPLE_APPROACHES.includes(r.arm))
    .map((r) => {
      const v = qs.map((q) => q.verdicts[r.arm]);
      const n = (ks: string[]) => v.filter((x) => ks.includes(x)).length;
      return { ...r, total: v.length, tier1: n(["tier1"]), tier2: n(["tier2"]), answered: n(["tier1", "tier2"]),
        wrong: n(["wrong_answer", "query_failed"]), no_query: n(["no_query", "no_retrieval", "skipped"]),
        tier3: v.length - n(["tier1", "tier2"]), unstable: 0 };
    });
  return { ...m, arms, classes, rollup, floor: undefined };
}

const E2E: Record<string, { label: string; cls: string }> = {
  reached: { label: "right", cls: "bg-success/15 text-success" },
  correct_refusal: { label: "refused ✓", cls: "bg-primary/15 text-primary" },
  diverged: { label: "diverged", cls: "bg-warning/15 text-warning" },
  not_reached: { label: "wrong", cls: "bg-destructive/15 text-destructive" },
  not_applicable: { label: "n/a", cls: "bg-surface-2 text-muted" },
  pending: { label: "pending", cls: "bg-surface-2 text-muted/60" },
};

function Verdict({ v, e2e }: { v: string; e2e?: boolean }) {
  const s = e2e ? E2E[v] ?? { label: v, cls: "bg-surface-2 text-muted" } : { label: TIER[v]?.short ?? v, cls: TIER[v]?.cls ?? "bg-surface-2 text-muted" };
  return <span className={`inline-block rounded px-1.5 py-0.5 text-[11px] font-semibold ${s.cls}`}>{s.label}</span>;
}

// Best-effort arm → retrieval-approach identity color (shared with the Tracer's five lenses).
function armColor(id: string): string {
  const s = id.toLowerCase();
  if (s.includes("closure")) return "var(--lens-closure)";
  if (s.includes("metric") || s === "m0") return "var(--lens-metric_view)";
  if (s.includes("rag")) return "var(--lens-rag)";
  if (s.includes("graph")) return "var(--lens-graph)";
  if (s === "genie_one") return "var(--primary)";
  if (s.includes("genie") || s.includes("a1") || s.includes("on") || s.includes("off"))
    return "var(--lens-genie_ontology)";
  return "var(--primary)";
}

function Bar({ r }: { r: CapabilityMap["rollup"][number] }) {
  const e2e = r.kind === "end_to_end";
  const pct = (n: number) => (r.total ? (n / r.total) * 100 : 0);
  return (
    <div className="flex items-center gap-3">
      <div className="flex w-44 shrink-0 items-center gap-1.5 text-[13px] font-medium">
        <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: armColor(r.arm) }} />
        {r.label}
      </div>
      <div className="relative flex h-7 flex-1 overflow-hidden rounded bg-surface-2">
        {e2e ? (
          <div className="h-full opacity-60" style={{ width: `${pct(r.reached)}%`, background: armColor(r.arm) }} />
        ) : (
          <>
            <div className="h-full" style={{ width: `${pct(r.tier1)}%`, background: armColor(r.arm) }} />
            <div className="h-full opacity-45" style={{ width: `${pct(r.tier2)}%`, background: armColor(r.arm) }} />
          </>
        )}
        <div className="absolute inset-0 flex items-center px-2 text-[12px] font-medium">
          {e2e ? (
            <span>
              {r.reached}/{r.total} right end-to-end{r.diverged ? ` · ${r.diverged} diverged` : ""}
              {r.not_reached ? ` · ${r.not_reached} wrong` : ""}
            </span>
          ) : (
            <span>
              <span className="font-semibold">✓ {r.answered}/{r.total} answered</span>
              <span className="text-muted"> ({r.tier1} in context · {r.tier2} one query) · ✗ {r.wrong} wrong · {r.no_query} couldn't query</span>
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function Ladder({ map }: { map: CapabilityMap }) {
  const ret = map.rollup.filter((r) => r.kind !== "end_to_end");
  const e2e = map.rollup.filter((r) => r.kind === "end_to_end");
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3 text-[11px] font-semibold uppercase tracking-wide text-muted">
        <span>Retrieval alone — answered from what each approach retrieved</span>
        <span className="flex items-center gap-1 normal-case tracking-normal"><span className="h-2.5 w-4 rounded-sm bg-fg/70" /> in context</span>
        <span className="flex items-center gap-1 normal-case tracking-normal"><span className="h-2.5 w-4 rounded-sm bg-fg/30" /> one query from it</span>
      </div>
      {ret.map((r) => <Bar key={r.arm} r={r} />)}
      {map.floor && (
        <div className="flex items-center gap-3 text-[12px] text-muted">
          <div className="w-44 shrink-0 pl-4">No retrieval (floor)</div>
          <div>✓ {map.floor.tier1 + map.floor.tier2}/{map.floor.total} answered — the same agent with nothing retrieved</div>
        </div>
      )}
      {e2e.length > 0 && (
        <>
          <div className="pt-3 text-[11px] font-semibold uppercase tracking-wide text-muted">
            For contrast — Genie One end-to-end (its own retrieval + as many queries as it wants; hand-verified)
          </div>
          {e2e.map((r) => <Bar key={r.arm} r={r} />)}
        </>
      )}
    </div>
  );
}

function Matrix({ map }: { map: CapabilityMap }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full border-collapse text-left text-xs">
        <thead className="bg-surface-2">
          <tr>
            <th className="px-3 py-2 font-semibold">Question</th>
            {map.arms.map((a) => (
              <th key={a.id} className={`px-2 py-2 text-center font-semibold whitespace-nowrap ${a.kind === "end_to_end" ? "border-l-2 border-border bg-surface" : ""}`}>
                {a.label}
                <div className="text-[10px] font-normal text-muted">{a.kind === "end_to_end" ? "answer, hand-verified" : "retrieved context"}</div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {map.classes.map((c) => (
            <Fragment key={c.class_num}>
              <tr className="border-t border-border bg-surface-2/50">
                <td colSpan={map.arms.length + 1} className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-primary">
                  {c.class_num}. {c.class_name}
                </td>
              </tr>
              {c.questions.map((q) => (
                <tr key={q.id} className="border-t border-border align-top hover:bg-surface-2/40">
                  <td className="px-3 py-2">
                    <div className="font-medium">{q.question}</div>
                    <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[10px] text-muted">
                      <span className="rounded bg-surface-2 px-1 py-0.5 font-mono">gold: {q.gold}</span>
                      {q.note ? <span className="italic">· {q.note}</span> : null}
                    </div>
                  </td>
                  {map.arms.map((a) => (
                    <td key={a.id} className={`px-2 py-2 text-center ${a.kind === "end_to_end" ? "border-l-2 border-border" : ""}`}
                      title={q.evidence?.[a.id] ? `Retrieved:\n${q.evidence[a.id].context}${q.evidence[a.id].sql ? `\n\nOne query:\n${q.evidence[a.id].sql}` : ""}` : undefined}>
                      {a.kind === "end_to_end" ? (
                        <Verdict v={q.verdicts[a.id]} e2e />
                      ) : (
                        <TierChip k={q.verdicts[a.id]} short runs={q.evidence?.[a.id]?.tier_runs} stable={q.evidence?.[a.id]?.stable} />
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type WsEv = { identity: string; questions: number; searched: number; snippets: number; on_topic: number; pages: number };

function OnOff({ runs }: { runs: A1Runs }) {
  const { off, on } = runs;
  const ev = runs.snippet_evidence ?? {};
  const ect = ev.ect as WsEv | undefined;
  const dmvm = ev.dmvm as WsEv | undefined;
  const row = (label: string, a?: number | string, b?: number | string) => (
    <tr className="border-t border-border">
      <td className="px-3 py-1.5 text-muted">{label}</td>
      <td className="px-3 py-1.5 text-center font-mono">{a ?? "—"}</td>
      <td className="px-3 py-1.5 text-center font-mono">{b ?? "—"}</td>
    </tr>
  );
  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-xs">
          <thead className="bg-surface-2">
            <tr>
              <th className="px-3 py-2 text-left font-semibold">Genie Ontology retrieval (10 benchmark Qs, as the same user)</th>
              <th className="px-3 py-2 font-semibold">ECT</th>
              <th className="px-3 py-2 font-semibold">DMVM</th>
            </tr>
          </thead>
          <tbody>
            {row("Questions where Genie ran its ontology search", ect && `${ect.searched}/${ect.questions}`, dmvm && `${dmvm.searched}/${dmvm.questions}`)}
            {row("Inferred snippets retrieved", ect?.snippets, dmvm?.snippets)}
            {row("…of which about this demo", ect?.on_topic, dmvm?.on_topic)}
            {row("Ontology Pages ranked", ect?.pages, dmvm?.pages)}
          </tbody>
        </table>
      </div>
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-xs">
          <thead className="bg-surface-2">
            <tr>
              <th className="px-3 py-2 text-left font-semibold">Genie One end-to-end (earlier 20-Q runs)</th>
              <th className="px-3 py-2 font-semibold">ECT</th>
              <th className="px-3 py-2 font-semibold">DMVM</th>
            </tr>
          </thead>
          <tbody>
            {row("Reached gold (auto)", off?.reached_auto, on?.reached_auto)}
            {row("search_knowledge_snippets fired", off?.snippet_search_fired, on?.snippet_search_fired)}
            {row("ontology consulted / cited a Page", off?.ontology_used, on?.ontology_used)}
          </tbody>
        </table>
      </div>
      <div className="flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/5 p-3 text-xs text-fg">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
        <span>{runs.caveat}</span>
      </div>
    </div>
  );
}

export function BenchmarkScorecard() {
  const { simple } = useSettings();
  const [full, setMap] = useState<CapabilityMap | null>(null);
  const map = useMemo(() => (full && simple ? simpleView(full) : full), [full, simple]);
  const [runs, setRuns] = useState<A1Runs | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.capabilityMap(), api.a1Runs()])
      .then(([m, r]) => {
        setMap(m);
        setRuns(r);
      })
      .catch((e) => setError(String(e)));
  }, []);

  if (error) {
    return (
      <div className="m-6 flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
        <AlertTriangle className="h-4 w-4" /> {error}
      </div>
    );
  }
  if (!map || !runs) {
    return (
      <div className="m-6 space-y-3">
        <div className="h-24 animate-pulse rounded-xl bg-surface-2" />
        <div className="h-96 animate-pulse rounded-xl bg-surface-2" />
      </div>
    );
  }

  return (
    <main className="flex-1 overflow-y-auto px-6 py-5">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">When each layer earns its place</h1>
        <p className="mt-1.5 text-[15px] text-muted">
          {simple ? (
            <>Three questions: one where Genie Ontology beats RAG, one where RAG does just as well, and one where the
              Ontobricks graph beats Genie Ontology.{" "}</>
          ) : (<>
          Seven questions, four stories: when Genie Ontology's retrieval beats RAG, when RAG does just as well, when the
          Ontobricks graph beats Genie Ontology, and when the graph looks like it should win but doesn't.{" "}</>)}
          <span className="font-semibold text-success">✓ Answered</span> means the answer was in the retrieved context, or the
          context was enough to write one SQL query that returned it.
        </p>
      </div>

      <div className="space-y-6">
        <Collapsible title="How often each approach's retrieval was enough">
          <Ladder map={map} />
          {!simple && <p className="mt-2 text-[13px] text-muted">
            Genie One is not on the same footing: on ECT it also loads a hand-written HEDIS skill built from this question
            set, reads its conversation memory and table schemas, and runs several queries.
          </p>}
        </Collapsible>

        <Collapsible title={simple ? "The three questions" : "The seven questions"}>
          <div className="mb-2 flex flex-wrap gap-2 text-[11px]">
            {["tier1", "tier2", "wrong_answer", "query_failed", "no_query", "no_retrieval", "skipped"]
              .filter((k) => map.classes.some((c) => c.questions.some((q) => Object.values(q.verdicts).includes(k))))
              .map((k) => (
              <span key={k} className={`rounded px-1.5 py-0.5 font-semibold ${TIER[k].cls}`}>{TIER[k].label}</span>
            ))}
          </div>
          <Matrix map={map} />
          <p className="mt-2 text-[12px] text-muted">
            Each row's note says why it came out that way. Hover a cell to see what that approach retrieved and the query it wrote.
          </p>
        </Collapsible>

        {!simple && <Collapsible title="Ontology ON vs OFF (ADR-0018, observational)" hint="optional detail" defaultOpen={false}>
          <p className="mb-2.5 text-[13px] text-muted">
            Same shared catalog, differing native-ontology density. Machine-observed by driving Genie One headless
            on each workspace.
          </p>
          <OnOff runs={runs} />
        </Collapsible>}
      </div>
    </main>
  );
}
