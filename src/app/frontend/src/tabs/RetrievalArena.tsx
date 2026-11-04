import { AlertTriangle, Clock } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, type A1Runs, type CapabilityMap, type CapQuestion, type OntobricksCareEdges } from "../api";
import { Collapsible } from "../components/Collapsible";
import { GenieMarkdown } from "../components/GenieMarkdown";

const VERDICT: Record<string, { label: string; cls: string }> = {
  reached: { label: "right", cls: "bg-success/15 text-success" },
  correct_refusal: { label: "refused ✓", cls: "bg-primary/15 text-primary" },
  diverged: { label: "diverged", cls: "bg-warning/15 text-warning" },
  not_reached: { label: "wrong", cls: "bg-destructive/15 text-destructive" },
  not_applicable: { label: "n/a", cls: "bg-surface-2 text-muted" },
  pending: { label: "pending", cls: "bg-surface-2 text-muted/60" },
};

function Verdict({ v }: { v: string }) {
  const s = VERDICT[v] ?? { label: v, cls: "bg-surface-2 text-muted" };
  return <span className={`rounded px-1.5 py-0.5 text-[11px] font-semibold ${s.cls}`}>{s.label}</span>;
}

// The five retrieval approaches, in the shared order, each with its identity color + how it resolves.
const APPROACHES = [
  { id: "metric_view", label: "Metric View", resolves: "build-time (baked into the metric view)" },
  { id: "closure", label: "Closure", resolves: "query-time (join the closure / edge table)" },
  { id: "genie_ontology", label: "Genie + Ontology", resolves: "LLM over governed metadata + Pages" },
  { id: "rag", label: "RAG", resolves: "hybrid retrieval over the protocol docs" },
  { id: "graph", label: "Ontobricks graph", resolves: "graph traversal (modeled)" },
] as const;

const LENS: Record<string, string> = {
  metric_view: "var(--lens-metric_view)",
  closure: "var(--lens-closure)",
  genie_ontology: "var(--lens-genie_ontology)",
  rag: "var(--lens-rag)",
  graph: "var(--lens-graph)",
};

export function RetrievalArena() {
  const [map, setMap] = useState<CapabilityMap | null>(null);
  const [runs, setRuns] = useState<A1Runs | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sel, setSel] = useState<string | null>(null);

  const [obStatus, setObStatus] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [ob, setOb] = useState<OntobricksCareEdges | null>(null);
  const [obError, setObError] = useState<string | null>(null);
  const queryGraph = () => {
    setObStatus("loading");
    setObError(null);
    api.ontobricksCareEdges()
      .then((r) => { setOb(r); setObStatus("done"); })
      .catch((e) => { setObError(String(e)); setObStatus("error"); });
  };

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

  return (
    <div className="flex min-h-0 flex-1">
      <aside className="w-72 shrink-0 overflow-y-auto border-r border-border bg-surface">
        <div className="px-4 py-3 text-[12px] font-semibold uppercase tracking-wide text-muted">
          Benchmark questions ({flat.length})
        </div>
        <ul className="space-y-1 px-2 pb-4">
          {flat.map((x) => (
            <li key={x.id}>
              <button
                onClick={() => setSel(x.id)}
                className={`w-full rounded-md border px-3 py-2 text-left text-[13px] transition ${
                  x.id === sel ? "border-primary bg-surface-2" : "border-transparent hover:bg-surface-2"
                }`}
              >
                <div className="font-medium leading-snug">{x.question}</div>
                <div className="mt-0.5 text-[11px] text-muted">{x.class_name} · min: {x.min_approach}</div>
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <main className="min-w-0 flex-1 overflow-y-auto px-6 py-5">
        {q && (
          <>
            <div className="mb-5">
              <h1 className="text-2xl font-bold tracking-tight">{q.question}</h1>
              <p className="mt-1.5 flex flex-wrap items-center gap-2 text-[14px] text-muted">
                <span className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[13px]">gold: {q.gold}</span>
                <span>min approach: <span className="font-semibold text-fg">{q.min_approach}</span></span>
                {q.note ? <span className="italic">· {q.note}</span> : null}
              </p>
            </div>

            <div className="space-y-6">
              <Collapsible title="Five approaches, one question">
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
                  {APPROACHES.map((a) => {
                    const c = LENS[a.id];
                    return (
                      <div
                        key={a.id}
                        style={{ borderTopColor: c }}
                        className="flex flex-col rounded-xl border border-t-[3px] border-border bg-surface p-3"
                      >
                        <div className="flex items-center gap-2">
                          <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: c }} />
                          <span className="text-[13.5px] font-semibold leading-tight">{a.label}</span>
                        </div>
                        <div className="mt-2"><Verdict v={q.verdicts[a.id]} /></div>
                        <div className="mt-2 text-[11.5px] leading-snug text-muted">{a.resolves}</div>
                      </div>
                    );
                  })}
                </div>
              </Collapsible>

              <Collapsible title="Genie + Ontology vs the graph" hint="the two reasoning engines, side by side">
                <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                  <div className="flex flex-col rounded-xl border border-t-[3px] border-border bg-surface p-3" style={{ borderTopColor: LENS.genie_ontology }}>
                    <div className="flex items-center gap-2">
                      <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: LENS.genie_ontology }} />
                      <span className="text-[14px] font-semibold">Genie + Ontology</span>
                      <span className="ml-auto"><Verdict v={q.verdicts.genie_ontology} /></span>
                    </div>
                    {off && off.answer ? (
                      <>
                        <div className="mt-2">
                          <GenieMarkdown md={off.answer} className="max-h-60 space-y-1 overflow-auto rounded-md border border-border bg-surface-2 p-2.5 text-[12px] leading-5 text-fg/90" />
                        </div>
                        <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px]">
                          <span className="flex items-center gap-1 text-muted"><Clock className="h-3 w-3" />{off.latency_s}s</span>
                          <span className={`rounded px-1.5 py-0.5 font-semibold ${off.ontology_used ? "bg-success/15 text-success" : "bg-surface-2 text-muted"}`}>
                            {off.ontology_used ? "ontology consulted" : "no ontology signal"}
                          </span>
                          {(off.tool_names || []).slice(0, 6).map((t, i) => (
                            <span key={i} className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-muted">{t}</span>
                          ))}
                        </div>
                      </>
                    ) : (
                      <div className="mt-2 rounded-md border border-dashed border-border bg-surface-2 px-2 py-3 text-[12px] text-muted">
                        No recorded Genie answer for this question.
                      </div>
                    )}
                  </div>

                  <div className="flex flex-col rounded-xl border border-t-[3px] border-border bg-surface p-3" style={{ borderTopColor: LENS.graph }}>
                    <div className="flex items-center gap-2">
                      <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: LENS.graph }} />
                      <span className="text-[14px] font-semibold">Ontobricks graph</span>
                      <span className="ml-auto"><Verdict v={q.verdicts.graph} /></span>
                    </div>
                    <p className="mt-2 text-[13px] leading-5 text-fg/85">
                      Live traversal over the published <span className="font-mono">clinicaldomain_v2</span> triplestore — the typed,
                      cross-vocabulary knowledge edges a closure join can't express.
                    </p>
                    <div className="mt-2">
                      {obStatus === "error" ? (
                        <div className="rounded-md border border-destructive/40 bg-destructive/10 px-2 py-1.5 text-[12px] text-destructive">{obError}</div>
                      ) : obStatus !== "done" || !ob ? (
                        <button
                          onClick={queryGraph}
                          disabled={obStatus === "loading"}
                          className="rounded-md bg-primary px-3 py-1.5 text-[12px] font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
                        >
                          {obStatus === "loading" ? "Traversing ~55M triples…" : "Query the graph ▸"}
                        </button>
                      ) : (
                        <div className="space-y-1.5">
                          <div className="flex flex-wrap items-center gap-1.5 text-[10px]">
                            <span className="rounded bg-primary/15 px-1.5 py-0.5 font-semibold text-primary">live · {ob.triples.length} edges</span>
                            <span className="rounded bg-surface-2 px-1.5 py-0.5 text-muted">{ob.latency_s}s · {ob.source}</span>
                          </div>
                          <div className="max-h-56 overflow-auto rounded-md border border-border">
                            <table className="w-full text-left text-[11px]">
                              <thead className="sticky top-0 bg-surface-2 text-muted"><tr>
                                <th className="px-2 py-1 font-semibold">subject</th>
                                <th className="px-2 py-1 font-semibold">predicate</th>
                                <th className="px-2 py-1 font-semibold">object</th>
                              </tr></thead>
                              <tbody>
                                {ob.triples.map((t, i) => (
                                  <tr key={i} className="border-t border-border">
                                    <td className="whitespace-nowrap px-2 py-1 font-mono">{t.subject}</td>
                                    <td className="whitespace-nowrap px-2 py-1 font-mono text-primary">{t.predicate}</td>
                                    <td className="whitespace-nowrap px-2 py-1 font-mono">{t.object}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </Collapsible>

              <p className="text-[12px] text-muted">
                One rubric across all five. Metric view / closure / Genie are hand-verified (Genie = the authoritative
                recorded run); RAG / graph carry the designed-capability verdict from the ground-truth hypotheses. The
                Genie answer shown is a recorded run — non-deterministic, as-of.
              </p>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
