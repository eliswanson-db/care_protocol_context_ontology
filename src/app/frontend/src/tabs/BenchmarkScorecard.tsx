import { AlertTriangle, Info } from "lucide-react";
import { Fragment, useEffect, useState } from "react";
import { api, type A1Runs, type CapabilityMap } from "../api";
import { Collapsible } from "../components/Collapsible";

// Retrieval columns: is the retrieved context alone sufficient (same judge as the Arena).
// Genie One column: hand-verified end-to-end answer (retrieval + its own SQL).
const VERDICT: Record<string, { label: string; cls: string }> = {
  reached: { label: "sufficient", cls: "bg-success/15 text-success" },
  not_reached: { label: "insufficient", cls: "bg-destructive/15 text-destructive" },
  no_retrieval: { label: "nothing retrieved", cls: "bg-surface-2 text-muted" },
  pending: { label: "pending", cls: "bg-surface-2 text-muted/60" },
};
const E2E: Record<string, { label: string; cls: string }> = {
  reached: { label: "right", cls: "bg-success/15 text-success" },
  correct_refusal: { label: "refused ✓", cls: "bg-primary/15 text-primary" },
  diverged: { label: "diverged", cls: "bg-warning/15 text-warning" },
  not_reached: { label: "wrong", cls: "bg-destructive/15 text-destructive" },
  not_applicable: { label: "n/a", cls: "bg-surface-2 text-muted" },
  pending: { label: "pending", cls: "bg-surface-2 text-muted/60" },
};

function Verdict({ v, e2e }: { v: string; e2e?: boolean }) {
  const s = (e2e ? E2E : VERDICT)[v] ?? { label: v, cls: "bg-surface-2 text-muted" };
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
  const pct = r.total ? Math.round((r.reached / r.total) * 100) : 0;
  return (
    <div className="flex items-center gap-3">
      <div className="flex w-44 shrink-0 items-center gap-1.5 text-[13px] font-medium">
        <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: armColor(r.arm) }} />
        {r.label}
      </div>
      <div className="relative h-7 flex-1 overflow-hidden rounded bg-surface-2">
        <div className={`h-full rounded ${e2e ? "opacity-60" : ""}`} style={{ width: `${pct}%`, background: armColor(r.arm) }} />
        <div className="absolute inset-0 flex items-center px-2 text-[12px] font-medium">
          {e2e ? (
            <span>
              {r.reached}/{r.total} right end-to-end{r.diverged ? ` · ${r.diverged} diverged` : ""}
              {r.not_reached ? ` · ${r.not_reached} wrong` : ""}
            </span>
          ) : (
            <span>
              {r.reached}/{r.total} context sufficient
              {r.not_reached ? ` · ${r.not_reached} insufficient` : ""}
              {r.no_retrieval ? ` · ${r.no_retrieval} retrieved nothing` : ""}
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
      <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">Retrieval alone — is the context sufficient?</div>
      {ret.map((r) => <Bar key={r.arm} r={r} />)}
      {e2e.length > 0 && (
        <>
          <div className="pt-3 text-[11px] font-semibold uppercase tracking-wide text-muted">
            For contrast — Genie One end-to-end (its retrieval + the SQL it writes; hand-verified)
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
                <div className="text-[10px] font-normal text-muted">{a.kind === "end_to_end" ? "answer, hand-verified" : "context alone"}</div>
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
                      <span>min: {q.min_approach}</span>
                      {q.note ? <span className="italic">· {q.note}</span> : null}
                    </div>
                  </td>
                  {map.arms.map((a) => (
                    <td key={a.id} className={`px-2 py-2 text-center ${a.kind === "end_to_end" ? "border-l-2 border-border" : ""}`}
                      title={q.evidence?.[a.id] ? `Retrieved:\n${q.evidence[a.id]}` : undefined}>
                      <Verdict v={q.verdicts[a.id]} e2e={a.kind === "end_to_end"} />
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
  const [map, setMap] = useState<CapabilityMap | null>(null);
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
          The five retrieval approaches on the same 10 questions, scored on one basis — the same one the Arena uses:
          <span className="font-semibold text-fg"> is the context this approach retrieves, on its own, enough to answer?</span>{" "}
          One judge ({map.scored_by?.judge?.replace("databricks:/", "") ?? "LLM judge"}) reads only the retrieved context and the
          question. Genie One's end-to-end answer sits in a separate column for contrast.
        </p>
      </div>

      <div className="space-y-6">
        <Collapsible title="Ablation ladder — reach by arm">
          <Ladder map={map} />
          <p className="mt-2 text-[13px] text-muted">
            Closure/edge tables carry most questions because they hand back precomputed answers. Metric views carry the
            KPIs they define. Genie Ontology's retrieval returns definitions (snippets and Pages), not the computed
            values, so on its own it rarely suffices. Genie One gets most of them right because it writes SQL on top of
            that retrieval.
          </p>
        </Collapsible>

        <Collapsible title="Capability map — question × arm">
          <div className="mb-2 flex flex-wrap gap-2 text-[11px]">
            {Object.entries(VERDICT).map(([k, v]) => (
              <span key={k} className={`rounded px-1.5 py-0.5 font-semibold ${v.cls}`}>{v.label}</span>
            ))}
          </div>
          <Matrix map={map} />
          <p className="mt-2 text-[12px] text-muted">
            Retrieval columns come from the judged retrieval eval (<span className="font-mono">retrieval_eval_arena.json</span>):
            each approach's real retrieval for the question, live where it can be (metric views, closure SQL, RAG,
            the Ontobricks triplestore) and recorded for Genie Ontology (its own snippet search on ECT). Hover a cell
            to see what was retrieved. <span className="font-semibold text-fg">nothing retrieved</span> means the approach
            returned no context for that question.
          </p>
          <div className="mt-3 flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/5 p-3 text-[12.5px] leading-snug text-fg">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
            <span>
              <span className="font-semibold">What the misses mean.</span> The graph's entity-linked triples carry typed
              definitions (<span className="font-mono">contraindicatedWhen</span>, <span className="font-mono">hasThreshold</span>),
              which is enough for the metformin/eGFR rule. But a set of triples isn't a count or a rate, so it fails the
              aggregate questions. A graph <span className="italic">query</span> (a COUNT traversal) would be a different
              approach. Genie Ontology's snippets are on-topic on ECT but describe how to compute an answer, not the answer
              itself. The exception is the rationale-path question, where the definitions <span className="italic">are</span>{" "}
              the answer. Neither result is a verdict on Genie One, which adds SQL; see its separate column.
            </span>
          </div>
        </Collapsible>

        <Collapsible title="Ontology ON vs OFF (ADR-0018, observational)" hint="optional detail" defaultOpen={false}>
          <p className="mb-2.5 text-[13px] text-muted">
            Same shared catalog, differing native-ontology density. Machine-observed by driving Genie One headless
            on each workspace.
          </p>
          <OnOff runs={runs} />
        </Collapsible>
      </div>
    </main>
  );
}
