import { AlertTriangle, Info } from "lucide-react";
import { Fragment, useEffect, useState } from "react";
import { api, type A1Runs, type CapabilityMap } from "../api";
import { Collapsible } from "../components/Collapsible";

const VERDICT: Record<string, { label: string; cls: string }> = {
  reached: { label: "reached", cls: "bg-success/15 text-success" },
  correct_refusal: { label: "refused ✓", cls: "bg-primary/15 text-primary" },
  diverged: { label: "diverged", cls: "bg-warning/15 text-warning" },
  not_reached: { label: "missed", cls: "bg-destructive/15 text-destructive" },
  not_applicable: { label: "n/a", cls: "bg-surface-2 text-muted" },
  pending: { label: "pending", cls: "bg-surface-2 text-muted/60" },
};

function Verdict({ v }: { v: string }) {
  const s = VERDICT[v] ?? { label: v, cls: "bg-surface-2 text-muted" };
  return <span className={`inline-block rounded px-1.5 py-0.5 text-[11px] font-semibold ${s.cls}`}>{s.label}</span>;
}

// Best-effort arm → retrieval-approach identity color (shared with the Tracer's five lenses).
function armColor(id: string): string {
  const s = id.toLowerCase();
  if (s.includes("closure")) return "var(--lens-closure)";
  if (s.includes("metric") || s === "m0") return "var(--lens-metric_view)";
  if (s.includes("rag")) return "var(--lens-rag)";
  if (s.includes("graph")) return "var(--lens-graph)";
  if (s.includes("genie") || s.includes("a1") || s.includes("on") || s.includes("off"))
    return "var(--lens-genie_ontology)";
  return "var(--primary)";
}

function Ladder({ map }: { map: CapabilityMap }) {
  return (
    <div className="space-y-2">
      {map.rollup.map((r) => {
        const pending = r.applicable === 0;
        const pct = pending ? 0 : Math.round((r.reached / r.applicable) * 100);
        return (
          <div key={r.arm} className="flex items-center gap-3">
            <div className="flex w-32 shrink-0 items-center gap-1.5 text-[13px] font-medium">
              <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: armColor(r.arm) }} />
              {r.label}
            </div>
            <div className="relative h-7 flex-1 overflow-hidden rounded bg-surface-2">
              <div className="h-full rounded" style={{ width: `${pct}%`, background: armColor(r.arm) }} />
              <div className="absolute inset-0 flex items-center px-2 text-[12px] font-medium">
                {pending ? (
                  <span className="text-muted">pending — awaiting DMVM verdicts</span>
                ) : (
                  <span>
                    {r.reached}/{r.applicable} reached
                    {r.diverged ? ` · ${r.diverged} diverged` : ""}
                    {r.not_reached ? ` · ${r.not_reached} missed` : ""}
                  </span>
                )}
              </div>
            </div>
          </div>
        );
      })}
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
              <th key={a.id} className="px-2 py-2 text-center font-semibold whitespace-nowrap">{a.label}</th>
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
                    <td key={a.id} className="px-2 py-2 text-center">
                      <Verdict v={q.verdicts[a.id]} />
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

function OnOff({ runs }: { runs: A1Runs }) {
  const { off, on } = runs;
  const row = (label: string, a?: number, b?: number) => (
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
              <th className="px-3 py-2 text-left font-semibold">Observational signal (20 Qs)</th>
              <th className="px-3 py-2 font-semibold">A1 off (ECT, ~200 snippets)</th>
              <th className="px-3 py-2 font-semibold">A1 on (DMVM, ~1,100 snippets)</th>
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
          The five retrieval approaches on the same hard questions, by capability class — one rubric per cell, a
          correct refusal counts as correct. The variable-shape rationale path (class 8) is reached only by the graph.
        </p>
      </div>

      <div className="space-y-6">
        <Collapsible title="Ablation ladder — reach by arm">
          <Ladder map={map} />
          <p className="mt-2 text-[13px] text-muted">
            Metric views answer only the baked KPIs; the closure/edge layer does the subsumption + multi-hop work;
            Genie One orchestrating those reaches the most. None reach the graph-native class without a graph.
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
            One rubric across all five approaches. <span className="font-semibold text-fg">Metric view, closure and
            Genie + Ontology</span> are hand-verified (Genie = the authoritative A1-off run); <span className="font-semibold text-fg">RAG</span> carries
            the designed-capability verdict. The <span className="font-semibold text-fg">Ontobricks graph</span> column is
            <span className="font-semibold text-fg"> live-measured</span> — every cell is a real traversal of the published
            <span className="font-mono"> clinicaldomain_v2</span> triplestore (~55M triples), scored by the same judge.
          </p>
          <div className="mt-3 flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/5 p-3 text-[12.5px] leading-snug text-fg">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
            <span>
              <span className="font-semibold">How to read the graph column.</span> This scores the graph as a{" "}
              <span className="font-semibold">retrieval/context source</span> — retrieve triples, let one fixed agent
              reason over them — apples-to-apples with RAG. Its lift is <span className="font-semibold">typed,
              cross-vocabulary edges</span>: the definitions (<span className="font-mono">contraindicatedWhen</span>,{" "}
              <span className="font-mono">hasThreshold</span>), the multi-hop <span className="font-semibold">rationale
              path</span> no other arm could assemble, and the <span className="font-semibold">correct refusal</span> of a
              class the ontology doesn't define. It misses the aggregate <span className="font-semibold">counts</span> —
              not because the edges are absent (every membership triple is there) but because a retrieved triple set
              isn't aggregated, whereas closure injects a precomputed SQL scalar. A graph <span className="italic">query</span>{" "}
              (a COUNT traversal) would reach those too.
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
