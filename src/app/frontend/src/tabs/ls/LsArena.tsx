import { Bot, Database, GitCompare, Network, Search, Wrench } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { ls, type ArenaQ, type ArenaRun } from "../../lsApi";
import { Card, Chip, Code, ErrorBox, Loading, Table, toneFor } from "./ui";

function Lens({ title, icon, color, children, state }: { title: string; icon: ReactNode; color: string; children: ReactNode; state?: ReactNode }) {
  return (
    <div className="flex flex-col rounded-lg border border-border bg-surface" style={{ borderTop: `3px solid ${color}` }}>
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
        <div className="flex items-center gap-1.5 text-[13px] font-semibold">{icon}{title}</div>
        {state}
      </div>
      <div className="min-h-0 flex-1 p-3 text-[12px]">{children}</div>
    </div>
  );
}

function SqlRows({ l }: { l: any }) {
  if (!l) return null;
  if (l.not_applicable) return <div className="text-muted">Not applicable: {l.not_applicable}.</div>;
  if (l.error) return <><Code>{l.sql}</Code><div className="mt-1 text-destructive">{l.error}</div></>;
  return (
    <>
      <Table rows={l.rows} cols={Object.keys(l.rows[0] ?? {}).map((k) => ({ key: k, label: k }))} max={12} />
      <details className="mt-1"><summary className="cursor-pointer text-[11px] text-muted">SQL ({l.latency_s}s)</summary><Code>{l.sql}</Code></details>
    </>
  );
}

// The answer in one or two lines; the full tool output stays one click away.
function summarize(tool: string, r: any): ReactNode {
  const n = (v: any, d = 1) => (v === null || v === undefined ? "—" : Number(v).toFixed(d));
  switch (tool) {
    case "endpoint_summary":
      return <>{r.by_arm.map((a: any) => `${a.arm}: mean ${n(a.mean_pct_change, 2)}% (n=${a.derived} of ${a.fas} FAS)`).join(" · ")}<span className="text-muted"> · {r.endpoint_version}</span></>;
    case "participant_trace":
      return <>{r.usubjid} under {r.endpoint_version}: <b>{r.result_status}</b>{r.pct_change != null ? ` ${n(r.pct_change, 2)}%` : ""}{r.exclusion_reason ? ` (${r.exclusion_reason})` : ""}</>;
    case "amendment_impact":
      return <>R1 → R2: {r.counts.became} became derivable, {r.counts.changed_selection} changed selected record, {r.counts.more_candidates} gained candidates (of {r.counts.compared})</>;
    case "compare_endpoints":
      return <><b>{r.equivalent ? "Equivalent" : "Not equivalent"}</b>{r.differences.length ? ": differ in " + r.differences.map((d: any) => d.parameter).join(", ") : ""}</>;
    case "rule_status":
      return <>Executable: {r.executable_rules.map((x: any) => `${x.endpoint_version} ±${x.window_half_width_days} d`).join(", ")}. Not executable: {r.statements.filter((x: any) => x.review_state !== "approved").map((x: any) => `±${x.value} (${x.review_state}, ${x.document_id})`).join(", ") || "none"}</>;
    case "rule_definition":
      return <>{r.citation.rule_version}: {r.citation.document} §{r.citation.section} ({r.citation.review_state})</>;
    case "dataset_mapping":
      return <>{r.mappings.map((m: any) => m.variable.replace("SDTM:", "")).join(", ")} <span className="text-muted">where {r.filter}</span></>;
    case "class_membership":
      return <>{r.concept_id} is <b>{r.member ? "a member" : "not a member"}</b> of {r.class_id}{r.via_roots?.length ? ` (is_a* ${r.via_roots.map((v: any) => v.root_label ?? v.root).join(", ")})` : ""}</>;
    case "contraindication_check":
      return <>{r.label}: <b>{r.contraindicated_for_class ? `contraindicated (MED-RT CI_with for ${r.drugs.join(", ")})` : "not contraindicated"}</b></>;
    case "eligibility_explain":
      return <>{r.usubjid}: {r.criteria.filter((c: any) => !["MET", "NOT_TRIGGERED"].includes(c.outcome)).map((c: any) => `${c.criterion_id} ${c.outcome}`).join(", ") || "all criteria met"}</>;
    default:
      return <span className="text-muted">see tool output</span>;
  }
}

function A6({ l }: { l: any }) {
  const r = l.route;
  if (["abstain", "clarify", "genie_fallback"].includes(r.tool))
    return (
      <div>
        <Chip tone={r.tool === "abstain" ? "warn" : "info"}>{r.tool}{r.reason ? ` · ${r.reason}` : ""}</Chip>
        <div className="mt-1.5">{r.note}</div>
      </div>
    );
  return (
    <div>
      <div className="mb-1 flex flex-wrap gap-1"><Chip tone="info">{r.tool}</Chip><span className="font-mono text-[11px] text-muted">{JSON.stringify(r.kwargs)}</span></div>
      <div className="text-[12.5px] leading-snug">{summarize(r.tool, l.result)}</div>
      <details className="mt-1">
        <summary className="cursor-pointer text-[11px] text-muted">tool output ({l.latency_s}s · fixed reviewed SQL, whitelisted inputs)</summary>
        <Code>{JSON.stringify(l.result, null, 1).slice(0, 3500)}</Code>
      </details>
    </div>
  );
}

function Genie({ qid }: { qid: string }) {
  const [g, setG] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  if (g) return (
    <div>
      <div className="whitespace-pre-wrap leading-snug">{g.answer || "(no text answer)"}</div>
      {g.sql?.length > 0 && <details className="mt-1"><summary className="cursor-pointer text-[11px] text-muted">generated SQL</summary><Code>{g.sql.join("\n\n")}</Code></details>}
      <div className="mt-1 text-[11px] text-muted">{g.surface} · {g.latency_s}s</div>
    </div>
  );
  return (
    <div>
      <button disabled={busy} onClick={() => { setBusy(true); ls.arenaGenie(qid).then(setG).catch((e) => setErr(String(e))).finally(() => setBusy(false)); }}
        className="rounded-md border border-border px-2 py-1 text-[12px] hover:border-primary">{busy ? "Asking Genie… (~30 s)" : "Ask the Study Analytics Genie agent ▸"}</button>
      {err && <div className="mt-1 text-destructive">{err}</div>}
      <div className="mt-1 text-[11px] text-muted">LLM-generated SQL over the same governed tables; asked live, labelled AI-generated.</div>
    </div>
  );
}

function Gated({ l, what }: { l: any; what: string }) {
  return (
    <div>
      <div className="leading-snug">{l.detail}</div>
      <div className="mt-1 text-[11px] text-muted">{what}</div>
    </div>
  );
}

export function LsArena() {
  const [qs, setQs] = useState<ArenaQ[]>([]);
  const [qid, setQid] = useState("ls_q8");
  const [run, setRun] = useState<ArenaRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { ls.arenaQuestions().then((r) => setQs(r.questions)).catch((e) => setError(String(e))); }, []);
  useEffect(() => {
    let live = true;
    setRun(null);
    setError(null);
    ls.arenaRun(qid).then((r) => live && setRun(r)).catch((e) => live && setError(String(e)));
    return () => { live = false; };
  }, [qid]);
  return (
    <div className="flex min-h-0 flex-1">
      <aside className="w-80 shrink-0 overflow-y-auto border-r border-border bg-surface p-3">
        <div className="mb-1 text-[11px] font-semibold uppercase text-muted">Questions (one per category)</div>
        {qs.map((q) => (
          <button key={q.qid} onClick={() => setQid(q.qid)} className={`mb-0.5 block w-full rounded px-1.5 py-1.5 text-left hover:bg-surface-2 ${q.qid === qid ? "bg-primary/10" : ""}`}>
            <div className="text-[10.5px] font-semibold uppercase tracking-wide text-muted">{q.category.replace(/_/g, " ")}</div>
            <div className="text-[12px] leading-snug">{q.question}</div>
          </button>
        ))}
      </aside>
      <main className="min-w-0 flex-1 space-y-3 overflow-y-auto p-4">
        {error && <ErrorBox error={error} />}
        {!run && !error && <Loading what="Running the question through each lens" />}
        {run && (
          <>
            <Card title={run.category.replace(/_/g, " ")}><div className="text-base font-semibold">{run.question}</div>
              <div className="mt-1 text-[11.5px] text-muted">Every lens gets the same facts (ADR-0025); differences come from how each retrieves. Scoring arrives with the Phase 7 benchmark.</div>
            </Card>
            <div className="grid gap-3 lg:grid-cols-2 2xl:grid-cols-3">
              <Lens title="Governed tools (A6)" icon={<Wrench className="h-4 w-4" />} color="var(--primary)"><A6 l={run.lenses.a6_tools} /></Lens>
              <Lens title="Metric view" icon={<Database className="h-4 w-4" />} color="var(--lens-metric_view)"><SqlRows l={run.lenses.metric_view} /></Lens>
              <Lens title="Closure tables" icon={<GitCompare className="h-4 w-4" />} color="var(--lens-closure)"><SqlRows l={run.lenses.closure} /></Lens>
              <Lens title="Genie agent (A2)" icon={<Bot className="h-4 w-4" />} color="var(--lens-genie_ontology)"><Genie qid={run.qid} /></Lens>
              <Lens title="Knowledge graph (Ontobricks)" icon={<Network className="h-4 w-4" />} color="var(--lens-graph)"
                state={<Chip tone={toneFor(run.lenses.graph.state)}>{run.lenses.graph.state}</Chip>}>
                <Gated l={run.lenses.graph} what="Traversal over the published triplestore (same facts as kb_edge)." />
              </Lens>
              <Lens title="RAG (Lakebase)" icon={<Search className="h-4 w-4" />} color="var(--lens-rag)"
                state={<Chip tone={toneFor(run.lenses.rag.state)}>{run.lenses.rag.state}</Chip>}>
                <Gated l={run.lenses.rag} what="Hybrid search over documents + one reference entry per KB concept." />
              </Lens>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
