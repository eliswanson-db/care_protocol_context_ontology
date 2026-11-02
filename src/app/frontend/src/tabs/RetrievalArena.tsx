import { AlertTriangle, Clock, Database, GitMerge, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, type A1Runs, type CapabilityMap, type CapQuestion } from "../api";

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
  return <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${s.cls}`}>{s.label}</span>;
}

const SQL_ARMS = [
  { id: "m0_metric_view", label: "M0 · metric view", icon: Database, resolves: "build-time (baked into the metric view)" },
  { id: "closure_sql", label: "Closure SQL", icon: GitMerge, resolves: "query-time (join the closure / edge table)" },
] as const;

export function RetrievalArena() {
  const [map, setMap] = useState<CapabilityMap | null>(null);
  const [runs, setRuns] = useState<A1Runs | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sel, setSel] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.capabilityMap(), api.a1Runs()])
      .then(([m, r]) => {
        setMap(m);
        setRuns(r);
        setSel(m.classes[1]?.questions[0]?.id ?? m.classes[0]?.questions[0]?.id ?? null);
      })
      .catch((e) => setError(String(e)));
  }, []);

  const flat = useMemo(() => {
    if (!map) return [] as (CapQuestion & { class_name: string })[];
    return map.classes.flatMap((c) => c.questions.map((q) => ({ ...q, class_name: c.class_name })));
  }, [map]);

  if (error)
    return (
      <div className="m-6 flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
        <AlertTriangle className="h-4 w-4" /> {error}
      </div>
    );
  if (!map || !runs)
    return <div className="m-6 h-96 animate-pulse rounded-xl bg-surface-2" />;

  const q = flat.find((x) => x.id === sel);
  const off = runs.off?.by_id[sel ?? ""];
  const on = runs.on?.by_id[sel ?? ""];

  return (
    <div className="flex min-h-0 flex-1">
      <aside className="w-72 shrink-0 overflow-y-auto border-r border-border bg-surface">
        <div className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted">
          Benchmark questions ({flat.length})
        </div>
        <ul className="space-y-1 px-2 pb-4">
          {flat.map((x) => (
            <li key={x.id}>
              <button
                onClick={() => setSel(x.id)}
                className={`w-full rounded-md border px-3 py-2 text-left text-xs transition ${
                  x.id === sel ? "border-primary bg-surface-2" : "border-transparent hover:bg-surface-2"
                }`}
              >
                <div className="font-medium leading-snug">{x.question}</div>
                <div className="mt-0.5 text-[10px] text-muted">{x.class_name} · min: {x.min_approach}</div>
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <main className="min-w-0 flex-1 overflow-y-auto px-6 py-5">
        {q && (
          <>
            <div className="mb-4">
              <h1 className="text-lg font-semibold">{q.question}</h1>
              <p className="mt-1 text-sm text-muted">
                <span className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-xs">gold: {q.gold}</span>{" "}
                · min approach: {q.min_approach}
                {q.note ? <span className="italic"> · {q.note}</span> : null}
              </p>
            </div>

            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {SQL_ARMS.map((a) => {
                const Icon = a.icon;
                return (
                  <div key={a.id} className="rounded-xl border border-border bg-surface p-3">
                    <div className="flex items-center gap-2">
                      <Icon className="h-4 w-4 text-primary" />
                      <span className="text-sm font-semibold">{a.label}</span>
                      <span className="ml-auto"><Verdict v={q.verdicts[a.id]} /></span>
                    </div>
                    <div className="mt-2 text-xs text-muted">Resolves at {a.resolves}.</div>
                  </div>
                );
              })}

              {[
                { id: "a1_off", label: "A1 off (ECT, ~200 snippets)", rec: off },
                { id: "a1_on", label: "A1 on (DMVM, ~1,100 snippets)", rec: on },
              ].map((arm) => (
                <div key={arm.id} className="rounded-xl border border-border bg-surface p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Sparkles className="h-4 w-4 text-primary" />
                    <span className="text-sm font-semibold">{arm.label}</span>
                    <span className="ml-auto"><Verdict v={q.verdicts[arm.id]} /></span>
                  </div>
                  {arm.rec ? (
                    <>
                      <div className="mt-2 max-h-56 overflow-y-auto whitespace-pre-wrap rounded-md border border-border bg-surface-2 p-2 text-xs leading-5">
                        {arm.rec.answer || "(no answer text)"}
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[10px]">
                        <span className="flex items-center gap-1 text-muted"><Clock className="h-3 w-3" />{arm.rec.latency_s}s</span>
                        <span className={`rounded px-1.5 py-0.5 font-semibold ${arm.rec.ontology_used ? "bg-success/15 text-success" : "bg-surface-2 text-muted"}`}>
                          {arm.rec.ontology_used ? "ontology consulted" : "no ontology signal"}
                        </span>
                        {(arm.rec.tool_names || []).slice(0, 6).map((t, i) => (
                          <span key={i} className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-muted">{t}</span>
                        ))}
                      </div>
                    </>
                  ) : (
                    <div className="mt-2 rounded-md border border-dashed border-border bg-surface-2 px-2 py-3 text-xs text-muted">
                      No snapshot answer for this question on this arm.
                    </div>
                  )}
                </div>
              ))}
            </div>

            <p className="mt-4 text-[11px] text-muted">
              SQL arms (M0 / closure) show the hand-verified verdict — they return result rows, not prose. The
              Genie One arms show the recorded answer + observable tool calls + latency from the dated A1 run
              snapshots (non-deterministic; as-of). a1_on verdicts are pending hand-verification.
            </p>
          </>
        )}
      </main>
    </div>
  );
}
