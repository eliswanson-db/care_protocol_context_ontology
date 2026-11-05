import { AlertTriangle, Info } from "lucide-react";
import { Fragment, useEffect, useState } from "react";
import { api, type A1Runs, type CapabilityMap } from "../api";
import { Collapsible } from "../components/Collapsible";
import { TIER, TierChip } from "../components/TierChip";

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
              {r.tier1} answer in context · {r.tier2} via one query · {r.tier3} neither
              {r.skipped ? ` (${r.skipped} search skipped)` : ""}
              {r.unstable ? <span className="ml-1.5 text-warning">· {r.unstable} varied across runs</span> : null}
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
        <span>Retrieval alone — of {map.floor?.total ?? 10} questions</span>
        <span className="flex items-center gap-1 normal-case tracking-normal"><span className="h-2.5 w-4 rounded-sm bg-fg/70" /> tier 1: answer in context</span>
        <span className="flex items-center gap-1 normal-case tracking-normal"><span className="h-2.5 w-4 rounded-sm bg-fg/30" /> tier 2: one query from context</span>
      </div>
      {ret.map((r) => <Bar key={r.arm} r={r} />)}
      {map.floor && (
        <div className="flex items-center gap-3 text-[12px] text-muted">
          <div className="w-44 shrink-0 pl-4">No retrieval (floor)</div>
          <div>{map.floor.tier1} in context · {map.floor.tier2} via one query — the same agent with an empty context</div>
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
                      <span>min: {q.min_approach}</span>
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
          The five retrieval approaches on the same {map.floor?.total ?? ""} questions, each scored only on the context it retrieves, in three tiers:{" "}
          <span className="font-semibold text-fg">1</span> the answer is in that context;{" "}
          <span className="font-semibold text-fg">2</span> the context gives what's needed for one SQL query that returns the answer (we run it);{" "}
          <span className="font-semibold text-fg">3</span> neither. Same tiers as the Arena. Genie One's end-to-end answer sits in a separate column for contrast.
        </p>
      </div>

      <div className="space-y-6">
        <Collapsible title="Ablation ladder — reach by arm">
          <Ladder map={map} />
          <p className="mt-2 text-[13px] text-muted">
            Tier 2 is a deliberately narrow test: one query, written only from names that appear in the retrieved context,
            with no schema given and no retries. Genie One is not held to that limit: it explores, then runs several
            queries. That is the gap between the two parts of this chart.
          </p>
        </Collapsible>

        <Collapsible title="Capability map — question × arm">
          <div className="mb-2 flex flex-wrap gap-2 text-[11px]">
            {["tier1", "tier2", "tier3", "no_retrieval", "skipped"].map((k) => (
              <span key={k} className={`rounded px-1.5 py-0.5 font-semibold ${TIER[k].cls}`}>{TIER[k].label}</span>
            ))}
          </div>
          <Matrix map={map} />
          <p className="mt-2 text-[12px] text-muted">
            What each approach retrieves: <span className="font-semibold text-fg">metric view</span> = the YAML definitions of the 3
            certified metric views most relevant to the question; <span className="font-semibold text-fg">closure / edge</span> = the
            terminology table cards plus the rows the question's linked entities hit (same entity linker as the graph);{" "}
            <span className="font-semibold text-fg">Genie Ontology</span> = its own snippet search + Pages, recorded on ECT;{" "}
            <span className="font-semibold text-fg">RAG</span> = top-5 Lakebase passages; <span className="font-semibold text-fg">graph</span> = the
            subgraph up to 3 hops around the linked entities in the live triplestore. Tier 1 is judged one gold fact at a time; tier 2's
            query is executed and its rows judged. {map.scored_by?.repeats ?? 3} runs per cell, majority shown; hover a cell
            for what was retrieved and the query.
          </p>
          <div className="mt-3 flex items-start gap-2 rounded-lg border border-border bg-surface-2/60 p-3 text-[12.5px] leading-snug text-fg">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
            <span>
              <span className="font-semibold">What this run surfaced (2026-11-05).</span>{" "}
              Five questions were built so the closure / edge tables wouldn't suffice (they hold no patient data and no
              measure business logic), and closure is tier 3 on all five. The graph reached its two through one query each:
              the patient's gaps and the 198-patient statin-contraindication cohort. Its context lists the gap edges, but
              a missing gap edge doesn't assert compliance, so that one is tier 2, not tier 1. Genie Ontology on ECT
              answered all three definition questions from its own retrieval; DMVM answered two, from the Pages, since its
              snippets there come from other projects. Given its own schema, the graph's single query also hit the
              subsumption counts (1,881 and 1,651), because the graph carries the patient layer.{" "}
              <span className="font-semibold">Limits seen:</span> the graph has no ACE/ARB drug-class edges (it reported
              0 of 10 cardiorenal patients on ACE/ARB; the answer is 8). It has no value-set versions (its vintage 0 is right but
              not grounded) and no names for drugs or codes. Genie Ontology's snippets cite pre-Nov-4 columns and locations, and{" "}
              <span className="font-mono">protocol_drift_metrics</span> has no UC comment, so it wasn't retrieved.
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
