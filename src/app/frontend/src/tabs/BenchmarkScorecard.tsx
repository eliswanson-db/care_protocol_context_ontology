import { AlertTriangle, Info } from "lucide-react";
import { Fragment, useEffect, useState } from "react";
import { api, type A1Runs, type CapabilityMap } from "../api";

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
  return <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-semibold ${s.cls}`}>{s.label}</span>;
}

function Ladder({ map }: { map: CapabilityMap }) {
  return (
    <div className="space-y-2">
      {map.rollup.map((r) => {
        const pending = r.applicable === 0;
        const pct = pending ? 0 : Math.round((r.reached / r.applicable) * 100);
        return (
          <div key={r.arm} className="flex items-center gap-3">
            <div className="w-28 shrink-0 text-xs font-medium">{r.label}</div>
            <div className="relative h-6 flex-1 overflow-hidden rounded bg-surface-2">
              <div className="h-full rounded bg-primary/70" style={{ width: `${pct}%` }} />
              <div className="absolute inset-0 flex items-center px-2 text-[11px] font-medium">
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
      <div className="mb-5">
        <h1 className="text-lg font-semibold">When each layer earns its place</h1>
        <p className="mt-1 text-sm text-muted">
          Accuracy on hard questions, by capability class. The hand-verified matrix is authoritative; a
          correct refusal counts as correct. Graph-native class 8 is unreached by every non-graph arm.
        </p>
      </div>

      <section className="mb-7">
        <h2 className="mb-2 text-sm font-semibold">Ablation ladder — reach by arm</h2>
        <Ladder map={map} />
        <p className="mt-2 text-xs text-muted">
          Metric views answer only the baked KPIs; the closure/edge layer does the subsumption + multi-hop work;
          Genie One orchestrating those reaches the most. None reach the graph-native class without a graph.
        </p>
      </section>

      <section className="mb-7">
        <h2 className="mb-2 text-sm font-semibold">Capability map — question × arm</h2>
        <div className="mb-2 flex flex-wrap gap-2 text-[10px]">
          {Object.entries(VERDICT).map(([k, v]) => (
            <span key={k} className={`rounded px-1.5 py-0.5 font-semibold ${v.cls}`}>{v.label}</span>
          ))}
        </div>
        <Matrix map={map} />
      </section>

      <section className="mb-7">
        <h2 className="mb-1 text-sm font-semibold">Ontology ON vs OFF (ADR-0018, observational)</h2>
        <p className="mb-2 text-xs text-muted">
          Same shared catalog, differing native-ontology density. Machine-observed by driving Genie One headless
          on each workspace.
        </p>
        <OnOff runs={runs} />
      </section>
    </main>
  );
}
