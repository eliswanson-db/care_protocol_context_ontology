import { AlertTriangle, Clock, Loader2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, type A1Runs, type ArenaContext, type CapabilityMap, type CapQuestion, type CtxDoc, type Scored } from "../api";
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

// The five retrieval approaches, in the shared order: each card scores ONLY what that approach retrieves
// (same question, same fixed agent, same judges) — `arm` is the retrieval_eval provider.
const APPROACHES = [
  { id: "metric_view", arm: "metric_view", label: "Metric View", how: "MEASURE() over a certified metric view" },
  { id: "closure", arm: "closure_sql", label: "Closure / governed SQL", how: "fixed-shape SQL over closure, edge and gold tables" },
  { id: "genie_ontology", arm: "genie_ontology", label: "Genie Ontology", how: "Genie's own retriever: inferred snippets + Pages (ECT, recorded)" },
  { id: "rag", arm: "rag", label: "RAG", how: "passage search over the care-protocol documents" },
  { id: "graph", arm: "ontobricks", label: "Ontobricks graph", how: "entity-linked typed edges from the live graph" },
] as const;

const LENS: Record<string, string> = {
  metric_view: "var(--lens-metric_view)",
  closure: "var(--lens-closure)",
  genie_ontology: "var(--lens-genie_ontology)",
  rag: "var(--lens-rag)",
  graph: "var(--lens-graph)",
};

function AgentVerdict({ s }: { s?: Scored }) {
  if (!s) return <span className="rounded bg-surface-2 px-1.5 py-0.5 text-[11px] text-muted">not scored yet</span>;
  return (
    <span className="flex flex-wrap items-center gap-1">
      <span className={`rounded px-1.5 py-0.5 text-[11px] font-semibold ${s.sufficient ? "bg-success/15 text-success" : "bg-destructive/15 text-destructive"}`}>
        {s.sufficient ? "context sufficient ✓" : s.n_docs ? "context insufficient" : "retrieved nothing"}
      </span>
    </span>
  );
}

function OntologyDoc({ d }: { d: CtxDoc }) {
  const m = d.metadata;
  if (m.kind === "page")
    return (
      <div className="rounded-md border border-border bg-surface-2 p-2.5">
        <div className="text-[12.5px] font-semibold">Page · {m.page}</div>
        <div className="mt-0.5 text-[11px] text-muted">matched on: {(m.matched_on || []).join(", ")}</div>
        <GenieMarkdown md={(m.body || "").replace(/^>\s?/gm, "")}
          className="mt-1.5 max-h-36 space-y-1 overflow-auto text-[12px] leading-5 text-fg/85" />
      </div>
    );
  return (
    <div className="rounded-md border border-border bg-surface-2 p-2.5">
      <div className="flex flex-wrap items-center gap-1.5 text-[12.5px] font-semibold">
        Metric view · {m.asset}
        {m.certified && <span className="rounded bg-success/15 px-1.5 py-0.5 text-[10px] font-semibold text-success">✓ certified</span>}
        {m.clinical_domain && <span className="rounded bg-primary/15 px-1.5 py-0.5 text-[10px] font-semibold text-primary">Clinical Domain</span>}
      </div>
      <div className="mt-0.5 text-[11px] text-muted">matched on: {(m.matched_on || []).join(", ")}</div>
      <div className="mt-1.5 max-h-36 overflow-auto font-mono text-[11px] leading-5 text-fg/85">{d.page_content}</div>
    </div>
  );
}

function GraphDocs({ docs: raw }: { docs: CtxDoc[] }) {
  const linked = raw[0]?.metadata?.linked_entities as string[] | undefined;
  // display order only: cross-vocabulary guideline edges, then the is-a hierarchy, then patient membership
  const rank = (d: CtxDoc) => (d.metadata.tier !== "guideline" ? 2 : d.metadata.predicate === "subClassOf" ? 1 : 0);
  const docs = [...raw].sort((a, b) => rank(a) - rank(b));
  return (
    <div className="space-y-1.5">
      {linked && <div className="text-[11px] text-muted">linked entities: <span className="font-mono">{linked.join(", ")}</span></div>}
      <div className="max-h-72 overflow-auto rounded-md border border-border">
        <table className="w-full text-left text-[11px]">
          <thead className="sticky top-0 bg-surface-2 text-muted"><tr>
            <th className="px-2 py-1 font-semibold">subject</th><th className="px-2 py-1 font-semibold">predicate</th>
            <th className="px-2 py-1 font-semibold">object</th><th className="px-2 py-1 font-semibold">tier</th>
          </tr></thead>
          <tbody>
            {docs.map((d, i) => (
              <tr key={i} className="border-t border-border">
                <td className="whitespace-nowrap px-2 py-1 font-mono">{d.metadata.subject}</td>
                <td className="whitespace-nowrap px-2 py-1 font-mono text-primary">{d.metadata.predicate}</td>
                <td className="whitespace-nowrap px-2 py-1 font-mono">{d.metadata.object}</td>
                <td className="whitespace-nowrap px-2 py-1 text-muted">{d.metadata.tier}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Flag({ on, label, tone }: { on: boolean; label: string; tone: "ok" | "warn" }) {
  if (!on) return null;
  return (
    <span className={`rounded px-1 py-0.5 text-[9.5px] font-semibold ${tone === "ok" ? "bg-success/15 text-success" : "bg-warning/15 text-warning"}`}>
      {label}
    </span>
  );
}

function GenieOntologyColumn({ sides, color }: { sides: ArenaContext["ontology"]; color: string }) {
  const wss = Object.keys(sides);
  const [ws, setWs] = useState(wss.includes("ect") ? "ect" : wss[0]);
  const side = sides[ws];
  if (!side) return null;
  const snips = side.docs.filter((d) => d.metadata.kind === "snippet");
  const pages = side.docs.filter((d) => d.metadata.kind === "page");
  const onTopic = snips.filter((d) => d.metadata.on_topic).length;
  return (
    <div className="flex flex-col rounded-xl border border-t-[3px] border-border bg-surface p-3" style={{ borderTopColor: color }}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: color }} />
        <span className="text-[14px] font-semibold">Genie Ontology</span>
        <span className="ml-auto"><AgentVerdict s={side.scored} /></span>
      </div>
      <p className="mt-1 text-[12px] leading-snug text-muted">
        Genie's own knowledge retriever — the snippet search Genie One runs — returning inferred snippets and ranked
        Pages, plus the Page bodies it read. Genie One's answer and SQL are not included.
      </p>
      <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px]">
        {wss.map((w) => (
          <button key={w} onClick={() => setWs(w)}
            className={`rounded-md border px-2 py-0.5 font-semibold ${w === ws ? "border-primary bg-primary/15 text-primary" : "border-border text-muted hover:text-fg"}`}>
            {w.toUpperCase()}
          </button>
        ))}
        <span className="text-muted">recorded {side.recorded_at?.slice(0, 10)} as {side.identity} on {side.host}</span>
      </div>
      {side.queries?.length > 0 && (
        <div className="mt-1.5 text-[11px] text-muted">search: <span className="italic">“{side.queries.join("”, “")}”</span></div>
      )}
      {side.skipped_search ? (
        <div className="mt-2 rounded-md border border-warning/40 bg-warning/10 px-2.5 py-2 text-[12px]">
          Genie One didn't run its ontology search for this question on this workspace (3 attempts) — it answered from
          conversation memory and SQL instead. So there is no Genie Ontology retrieval to show here, which is itself a finding:
          Genie decides per question whether to consult the ontology.
        </div>
      ) : side.error ? (
        <div className="mt-2 rounded-md border border-destructive/40 bg-destructive/10 px-2 py-1.5 text-[12px] text-destructive">{side.error}</div>
      ) : (
        <div className="mt-2 space-y-3">
          <section>
            <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">
              Inferred snippets ({snips.length}{snips.length ? `, ${onTopic} about this demo` : ""})
            </div>
            {snips.length === 0 ? (
              <div className="rounded-md border border-dashed border-border bg-surface-2 px-2.5 py-2 text-[12px] text-muted">
                Genie's snippet search returned no inferred snippets for this question here.
              </div>
            ) : (
              <div className="max-h-80 space-y-1.5 overflow-auto">
                {snips.map((d, i) => (
                  <details key={i} className="rounded-md border border-border bg-surface-2 px-2.5 py-1.5">
                    <summary className="cursor-pointer text-[12px] leading-snug">
                      <span className="font-medium">{d.metadata.headline}</span>
                      <span className="ml-1.5 inline-flex flex-wrap items-center gap-1 align-middle">
                        <Flag on={!!d.metadata.on_topic} label="this demo" tone="ok" />
                        <Flag on={!d.metadata.on_topic} label="other project" tone="warn" />
                        <Flag on={!!d.metadata.stale} label="stale source" tone="warn" />
                      </span>
                      <div className="mt-0.5 text-[10.5px] text-muted">
                        {d.metadata.type} · relevance {d.metadata.relevance} · from {d.metadata.source}
                      </div>
                    </summary>
                    <div className="mt-1.5 text-[11.5px] leading-5 text-fg/85">{d.metadata.content}</div>
                  </details>
                ))}
              </div>
            )}
          </section>
          <section>
            <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">Ontology Pages ({pages.length})</div>
            <div className="space-y-1.5">
              {pages.map((d, i) => (
                <details key={i} className="rounded-md border border-border bg-surface-2 px-2.5 py-1.5">
                  <summary className="cursor-pointer text-[12px]">
                    <span className="font-medium">{d.metadata.page}</span>
                    <span className="ml-1.5 text-[10.5px] text-muted">{d.metadata.domain} · relevance {d.metadata.relevance}</span>
                    {d.metadata.body && <span className="ml-1.5 rounded bg-primary/15 px-1 py-0.5 text-[9.5px] font-semibold text-primary">read in full</span>}
                    <div className="mt-0.5 text-[11px] text-muted">{d.metadata.description}</div>
                  </summary>
                  {d.metadata.body && (
                    <GenieMarkdown md={d.metadata.body} className="mt-1.5 max-h-48 space-y-1 overflow-auto text-[12px] leading-5 text-fg/85" />
                  )}
                </details>
              ))}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function RetrievalColumn({ title, subtitle, color, side, empty }: {
  title: string; subtitle: string; color: string;
  side: { docs: CtxDoc[]; latency_s: number; error?: string; scored?: Scored }; empty: string;
}) {
  const isGraph = side.docs[0]?.metadata?.kind === "triple";
  return (
    <div className="flex flex-col rounded-xl border border-t-[3px] border-border bg-surface p-3" style={{ borderTopColor: color }}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: color }} />
        <span className="text-[14px] font-semibold">{title}</span>
        <span className="ml-auto"><AgentVerdict s={side.scored} /></span>
      </div>
      <p className="mt-1 text-[12px] leading-snug text-muted">{subtitle}</p>
      <div className="mt-2 text-[10.5px] text-muted">
        <span className="rounded bg-primary/15 px-1.5 py-0.5 font-semibold text-primary">live · {side.docs.length} retrieved</span>
        <span className="ml-1.5">{side.latency_s}s</span>
      </div>
      <div className="mt-2 flex-1 space-y-2">
        {side.error ? (
          <div className="rounded-md border border-destructive/40 bg-destructive/10 px-2 py-1.5 text-[12px] text-destructive">{side.error}</div>
        ) : side.docs.length === 0 ? (
          <div className="rounded-md border border-dashed border-border bg-surface-2 px-2.5 py-3 text-[12px] text-muted">{empty}</div>
        ) : isGraph ? (
          <GraphDocs docs={side.docs} />
        ) : (
          side.docs.map((d, i) => <OntologyDoc key={i} d={d} />)
        )}
      </div>
    </div>
  );
}

export function RetrievalArena() {
  const [map, setMap] = useState<CapabilityMap | null>(null);
  const [runs, setRuns] = useState<A1Runs | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sel, setSel] = useState<string | null>(null);

  const [ctx, setCtx] = useState<ArenaContext | null>(null);
  const [ctxErr, setCtxErr] = useState<string | null>(null);
  useEffect(() => {
    if (!sel) return;
    let live = true;
    setCtx(null); setCtxErr(null);
    api.arenaContext(sel)
      .then((r) => live && setCtx(r))
      .catch((e) => live && setCtxErr(String(e)));
    return () => { live = false; };
  }, [sel]);

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
              <Collapsible title="Five approaches, one question"
                hint="is the retrieved context alone enough to answer? one judge, every approach">
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
                  {APPROACHES.map((a) => {
                    const c = LENS[a.id];
                    const sc = ctx?.scored_all?.[a.arm];
                    return (
                      <div key={a.id} style={{ borderTopColor: c }}
                        className="flex flex-col rounded-xl border border-t-[3px] border-border bg-surface p-3">
                        <div className="flex items-center gap-2">
                          <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: c }} />
                          <span className="text-[13.5px] font-semibold leading-tight">{a.label}</span>
                        </div>
                        <div className="mt-1 text-[11px] leading-snug text-muted">{a.how}</div>
                        <div className="mt-2">
                          {!ctx ? (
                            <span className="rounded bg-surface-2 px-1.5 py-0.5 text-[11px] text-muted">loading…</span>
                          ) : !sc ? (
                            <span className="rounded bg-surface-2 px-1.5 py-0.5 text-[11px] text-muted">not scored</span>
                          ) : (
                            <span className={`rounded px-1.5 py-0.5 text-[11.5px] font-semibold ${sc.sufficient ? "bg-success/15 text-success" : "bg-destructive/15 text-destructive"}`}>
                              {sc.sufficient ? "context sufficient ✓" : sc.n_docs ? "context insufficient" : "retrieved nothing"}
                            </span>
                          )}
                        </div>
                        {sc && (
                          <>
                            <div className="mt-1.5 text-[10.5px] text-muted">{sc.n_docs} item{sc.n_docs === 1 ? "" : "s"} retrieved</div>
                            {sc.n_docs > 0 && sc.context && (
                              <details className="mt-2 text-[11px]">
                                <summary className="cursor-pointer font-semibold text-primary">What it retrieved</summary>
                                <pre className="mt-1 max-h-56 overflow-auto whitespace-pre-wrap rounded bg-surface-2 p-2 font-mono text-[10.5px] leading-4">{sc.context}</pre>
                              </details>
                            )}
                          </>
                        )}
                      </div>
                    );
                  })}
                </div>
                <p className="mt-2.5 text-[12px] text-muted">
                  Each approach retrieves with its own method, and a judge ({ctx?.scored_meta?.judge ?? "—"}) decides whether that
                  retrieved context alone holds every fact the gold answer needs. Structured approaches retrieve by running their best governed query where their representation can express
                  the question, and nothing where it can't. Genie One's end-to-end answer (retrieval + its own SQL) is scored
                  separately below.
                </p>
              </Collapsible>

              <Collapsible title="Retrieval — Genie Ontology vs the graph"
                hint="what each knowledge layer returns for this question, side by side">
                {!ctx && !ctxErr && (
                  <div className="flex items-center gap-2 text-[13px] text-muted">
                    <Loader2 className="h-4 w-4 animate-spin" /> Retrieving from the Genie Ontology and the live graph…
                  </div>
                )}
                {ctxErr && <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-[12px] text-destructive">{ctxErr}</div>}
                {ctx && (
                  <>
                    <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                      <GenieOntologyColumn sides={ctx.ontology} color={LENS.genie_ontology} />
                      <RetrievalColumn title="Ontobricks graph" color={LENS.graph} side={ctx.graph}
                        subtitle={`Clinical terms in the question linked to graph nodes, then their typed one-hop edges from ${ctx.graph.graph_table.split(".").pop()} (live).`}
                        empty="No clinical entity in the question links to a graph node — the graph holds no operational or temporal data." />
                    </div>
                    <p className="mt-2.5 text-[12px] text-muted">
                      Retrieval only, side by side. Genie Ontology's retrieval is identity-scoped (the app's service principal
                      gets fewer snippets), so it is recorded as a user on each workspace; the graph is queried live. The verdict
                      is the same judge as above: is the retrieved context alone sufficient? Neither layer holds computed
                      numbers — turning a definition into a count is Genie One's SQL step, below.
                    </p>
                  </>
                )}
              </Collapsible>

              <Collapsible title="Genie One end-to-end" hint="the product front door: its own retrieval + SQL, recorded run" defaultOpen={false}>
                <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                  <div className="flex flex-col rounded-xl border border-t-[3px] border-border bg-surface p-3" style={{ borderTopColor: LENS.genie_ontology }}>
                    <div className="flex items-center gap-2">
                      <span className="text-[14px] font-semibold">Genie One's answer</span>
                      <span className="ml-auto"><Verdict v={q.verdicts.genie_ontology} /></span>
                    </div>
                    {off && off.answer ? (
                      <>
                        <GenieMarkdown md={off.answer} className="mt-2 max-h-72 space-y-1 overflow-auto rounded-md border border-border bg-surface-2 p-2.5 text-[12px] leading-5 text-fg/90" />
                        <div className="mt-2 flex items-center gap-1 text-[11px] text-muted"><Clock className="h-3 w-3" />{off.latency_s}s</div>
                      </>
                    ) : (
                      <div className="mt-2 rounded-md border border-dashed border-border bg-surface-2 px-2 py-3 text-[12px] text-muted">No recorded Genie answer for this question.</div>
                    )}
                  </div>
                  <div className="flex flex-col rounded-xl border border-border bg-surface p-3">
                    <div className="text-[14px] font-semibold">What Genie One retrieved on this run</div>
                    {ctx?.genie_one?.tool_calls ? (
                      <dl className="mt-2 grid grid-cols-[9rem_1fr] gap-x-3 gap-y-1.5 text-[12.5px]">
                        <dt className="text-muted">Pages cited</dt><dd>{(ctx.genie_one.pages_cited || []).join(", ") || "—"}</dd>
                        <dt className="text-muted">Snippet searches</dt><dd className="italic">{(ctx.genie_one.snippet_searches || []).map((x) => `"${x}"`).join("; ") || "—"}</dd>
                        <dt className="text-muted">Governed tables</dt><dd className="font-mono text-[11.5px]">{(ctx.genie_one.tables_queried || []).join(", ") || "—"}</dd>
                        <dt className="text-muted">Work</dt><dd>{ctx.genie_one.tool_calls} tool calls · {ctx.genie_one.sql_queries} SQL queries{ctx.genie_one.used_ontobricks_mcp ? " · used the Ontobricks MCP" : ""}</dd>
                        <dt className="text-muted">Recording</dt><dd className="font-mono text-[11.5px]">{ctx.genie_one.snapshot}</dd>
                      </dl>
                    ) : (
                      <div className="mt-2 text-[12px] text-muted">{ctx ? "No recorded trail for this question." : "Loading…"}</div>
                    )}
                    <p className="mt-3 text-[11.5px] text-muted">
                      Genie One retrieves from the same ontology (Pages, certified metric views, snippets), then writes and runs
                      SQL — that last step is what turns a definition into a number.
                    </p>
                  </div>
                </div>
              </Collapsible>

              <p className="text-[12px] text-muted">
                The five cards use one rubric: metric view / closure / Genie One are hand-verified (Genie One = the authoritative
                recorded run); RAG and graph are scored as retrieval-as-context. The retrieval section compares the two knowledge
                layers like-for-like; Genie One's answer is end-to-end and non-deterministic, as-of the recording.
              </p>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
