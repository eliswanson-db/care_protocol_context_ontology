import {
  BookOpen,
  Database,
  FileText,
  GitMerge,
  Loader2,
  Share2,
  ShieldCheck,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import type { GenieResult, OntobricksResult, RagResult, RetrievalLens, RetrievalResult } from "../api";
import { GenieMarkdown } from "./GenieMarkdown";

export type LiveStatus = "idle" | "loading" | "done" | "error";
export interface LiveArm<T> {
  status: LiveStatus;
  result: T | null;
  error: string | null;
  onAsk: () => void;
}

const ICON: Record<string, LucideIcon> = {
  metric_view: Database,
  closure: GitMerge,
  genie_ontology: Sparkles,
  rag: BookOpen,
  graph: Share2,
};

// The fixed, consistent order the five lenses always render in (deck + benchmark order).
const ORDER = ["metric_view", "closure", "genie_ontology", "rag", "graph"] as const;

// Static fallback metadata so the cards render with labels before /retrieval resolves.
const META: Record<string, { label: string; resolves_at: string; question: string; good_at: string; blind_to: string }> = {
  metric_view: {
    label: "Metric View",
    resolves_at: "build-time",
    question: "What governed rate does this patient roll into?",
    good_at: "One certified number; exact & auditable.",
    blind_to: "Why THIS patient — it's a pre-modeled aggregate.",
  },
  closure: {
    label: "Closure table",
    resolves_at: "query-time join",
    question: "Why is this patient in the cohort? (subsumption)",
    good_at: "Correct membership at any depth (E11.21 ⊑ E11).",
    blind_to: "No narrative; hierarchy must be pre-built.",
  },
  genie_ontology: {
    label: "Genie One + Ontology",
    resolves_at: "LLM at query-time",
    question: "Is this patient GSD-compliant, and why? (in English)",
    good_at: "Ask in English; grounds in Pages/metric views + cites.",
    blind_to: "Non-deterministic; may write a wrong join.",
  },
  rag: {
    label: "A4 Lakebase RAG",
    resolves_at: "retrieval at query-time",
    question: "What passage defines the rule behind this status?",
    good_at: "Exact narrative passage + provenance; row-secured.",
    blind_to: "Prose, not computation; can't count a cohort.",
  },
  graph: {
    label: "Ontobricks graph",
    resolves_at: "live traversal · clinicaldomain_v2",
    question: "Trace the typed, cross-vocabulary edges around this patient.",
    good_at: "Typed, multi-hop, cross-vocab paths a closure join can't express.",
    blind_to: "Overkill for a single is-a rollup; scans ~55M triples.",
  },
};

const CITE_LABEL: Record<string, string> = {
  snippet_search: "ontology snippet",
  knowledge_page: "ontology Page",
  page: "ontology Page",
  metric_view: "metric view",
  table: "table",
};

function Shell({
  id,
  resolvesAt,
  question,
  latency,
  active,
  dim,
  children,
  goodAt,
  blindTo,
}: {
  id: string;
  resolvesAt: string;
  question: string;
  latency?: number | null;
  active: boolean;
  dim: boolean;
  children: React.ReactNode;
  goodAt: string;
  blindTo: string;
}) {
  const Icon = ICON[id] ?? Database;
  const label = META[id]?.label ?? id;
  const c = `var(--lens-${id})`;
  return (
    <div
      style={{ borderTopColor: dim ? undefined : c }}
      className={[
        "flex min-h-[15rem] flex-col rounded-xl border border-t-[3px] bg-surface p-3.5 transition",
        active ? "border-primary ring-2 ring-primary/40" : "border-border",
        dim ? "opacity-30" : "",
      ].join(" ")}
    >
      <div className="flex items-center gap-2">
        <span
          className="flex h-8 w-8 items-center justify-center rounded-lg"
          style={{ background: `color-mix(in srgb, ${c} 20%, transparent)`, color: c }}
        >
          <Icon className="h-[18px] w-[18px]" />
        </span>
        <span className="text-[15px] font-semibold leading-tight">{label}</span>
        {latency != null && (
          <span className="ml-auto rounded bg-surface-2 px-1.5 py-0.5 text-[10px] font-medium text-muted">{latency}s</span>
        )}
      </div>
      <div
        className="mt-2 rounded px-1.5 py-1 text-[10px] font-bold uppercase tracking-wide"
        style={{ background: `color-mix(in srgb, ${c} 13%, transparent)`, color: c }}
      >
        {resolvesAt}
      </div>
      <p className="mt-2 text-[12.5px] italic leading-snug text-fg/80">{question}</p>
      <div className="mt-2.5 flex-1">{children}</div>
      <dl className="mt-3 space-y-1 border-t border-border pt-2.5 text-[11.5px] leading-snug">
        <div className="flex gap-1.5">
          <dt className="font-bold text-success">✓</dt>
          <dd className="text-muted">{goodAt}</dd>
        </div>
        <div className="flex gap-1.5">
          <dt className="font-bold text-destructive">✗</dt>
          <dd className="text-muted">{blindTo}</dd>
        </div>
      </dl>
    </div>
  );
}

/** The one place a number becomes a visual: the governed GSD rate as a hero stat + bar. */
function StatTile({ rows }: { rows: Record<string, unknown>[] }) {
  const r = rows[0];
  if (!r) return <span className="text-[12px] text-muted">no rows</span>;
  const raw = Number(r.rate);
  const pct = Number.isFinite(raw) ? Math.round(raw * 100) : null;
  const c = "var(--lens-metric_view)";
  return (
    <div>
      <div className="flex items-end gap-2">
        <span className="text-4xl font-bold leading-none tracking-tight" style={{ color: c }}>
          {pct != null ? `${pct}%` : "—"}
        </span>
        <span className="pb-0.5 text-[12px] text-muted">GSD rate · {String(r.clinic)}</span>
      </div>
      <div className="mt-2.5 h-2.5 overflow-hidden rounded-full bg-surface-2">
        <div className="h-full rounded-full" style={{ width: `${pct ?? 0}%`, background: c }} />
      </div>
      <div className="mt-2 text-[12px] font-medium text-muted">
        <span className="font-mono text-fg">{String(r.compliant)}</span> compliant of{" "}
        <span className="font-mono text-fg">{String(r.eligible)}</span> eligible · MY {String(r.measurement_year)}
      </div>
    </div>
  );
}

function MiniTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (!rows.length) return <span className="text-[11px] text-muted">no rows</span>;
  const keys = Object.keys(rows[0]);
  return (
    <div className="max-h-44 overflow-auto rounded-md border border-border">
      <table className="w-full text-left text-[11px]">
        <thead className="sticky top-0 bg-surface-2 text-muted">
          <tr>
            {keys.map((k) => (
              <th key={k} className="whitespace-nowrap px-2 py-1.5 font-semibold">{k}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 6).map((r, i) => (
            <tr key={i} className="border-t border-border">
              {keys.map((k) => (
                <td key={k} className="whitespace-nowrap px-2 py-1.5 font-mono tabular-nums">
                  {r[k] === null || r[k] === undefined ? <span className="text-muted">·</span> : String(r[k])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > 6 && <div className="px-2 py-1 text-[10px] text-muted">+{rows.length - 6} more rows</div>}
    </div>
  );
}

function AskButton({ status, idle, busy, onAsk }: { status: LiveStatus; idle: string; busy: string; onAsk: () => void }) {
  return (
    <button
      onClick={onAsk}
      disabled={status === "loading"}
      className="flex w-full items-center justify-center gap-1.5 rounded-md bg-primary px-2 py-1.5 text-[11px] font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
    >
      {status === "loading" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
      {status === "loading" ? busy : idle}
    </button>
  );
}

function GenieBody({ arm }: { arm: LiveArm<GenieResult> }) {
  if (arm.status === "error")
    return <div className="rounded-md border border-destructive/40 bg-destructive/10 px-2 py-1.5 text-[11px] text-destructive">{arm.error}</div>;
  if (arm.status !== "done" || !arm.result)
    return <AskButton status={arm.status} idle="Ask Genie One ▸" busy="Asking… (~1 min)" onAsk={arm.onAsk} />;
  const r = arm.result;
  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-center gap-1">
        <span
          className={`flex items-center gap-1 rounded px-1.5 py-0.5 text-[9px] font-semibold ${
            r.ontology_used ? "bg-success/15 text-success" : "bg-surface-2 text-muted"
          }`}
        >
          <ShieldCheck className="h-3 w-3" />
          {r.ontology_used ? "ontology consulted" : "no ontology signal"}
        </span>
      </div>
      {r.answer ? <GenieMarkdown md={r.answer} /> : <div className="text-[11.5px] text-muted">(no answer text)</div>}
      {r.citations.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {r.citations.slice(0, 5).map((c, i) => (
            <span key={i} className="rounded border border-border bg-surface px-1.5 py-0.5 text-[9px]" title={c.detail}>
              {CITE_LABEL[c.kind] ?? c.kind}
            </span>
          ))}
        </div>
      )}
      <button onClick={arm.onAsk} className="text-[10px] font-semibold text-primary hover:underline">Ask again</button>
    </div>
  );
}

function RagBody({ arm }: { arm: LiveArm<RagResult> }) {
  if (arm.status === "error")
    return <div className="rounded-md border border-destructive/40 bg-destructive/10 px-2 py-1.5 text-[11px] text-destructive">{arm.error}</div>;
  if (arm.status !== "done" || !arm.result)
    return <AskButton status={arm.status} idle="Retrieve passages ▸" busy="Retrieving…" onAsk={arm.onAsk} />;
  const r = arm.result;
  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-center gap-1 text-[9px]">
        <span className="rounded bg-primary/15 px-1.5 py-0.5 font-semibold text-primary">
          {r.mode === "hybrid" ? "hybrid" : "lexical · BM25"}
        </span>
        <span className="rounded bg-surface-2 px-1.5 py-0.5 text-muted">doc-level RLS</span>
      </div>
      {r.results.length === 0 ? (
        <div className="text-[11px] text-muted">No authorized passages matched.</div>
      ) : (
        <ol className="max-h-40 space-y-1 overflow-auto">
          {r.results.slice(0, 4).map((p, i) => (
            <li key={`${p.document_id}-${i}`} className="rounded-md border border-border bg-surface p-1.5">
              <div className="flex items-center gap-1 text-[11px] font-semibold">
                <FileText className="h-3 w-3 shrink-0 text-primary" />
                <span className="truncate">{p.title}</span>
              </div>
              <div className="text-[9px] text-primary">{p.section_path}{p.page_start != null ? ` · p${p.page_start}` : ""}</div>
            </li>
          ))}
        </ol>
      )}
      <button onClick={arm.onAsk} className="text-[10px] font-semibold text-primary hover:underline">Retrieve again</button>
    </div>
  );
}

function GraphBody({ arm }: { arm: LiveArm<OntobricksResult> }) {
  if (arm.status === "error")
    return <div className="rounded-md border border-destructive/40 bg-destructive/10 px-2 py-1.5 text-[11px] text-destructive">{arm.error}</div>;
  if (arm.status !== "done" || !arm.result)
    return <AskButton status={arm.status} idle="Query the graph ▸" busy="Traversing 55M triples…" onAsk={arm.onAsk} />;
  const r = arm.result;
  const rows = [...r.patient_triples, ...r.care_triples];
  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-center gap-1 text-[9px]">
        <span className="rounded bg-primary/15 px-1.5 py-0.5 font-semibold text-primary">live traversal</span>
        <span className="rounded bg-surface-2 px-1.5 py-0.5 text-muted">{rows.length} edges · clinicaldomain_v2</span>
      </div>
      {rows.length === 0 ? (
        <div className="text-[11px] text-muted">No triples returned.</div>
      ) : (
        <div className="max-h-44 overflow-auto rounded-md border border-border">
          <table className="w-full text-left text-[10.5px]">
            <thead className="sticky top-0 bg-surface-2 text-muted">
              <tr>
                <th className="px-1.5 py-1 font-semibold">subject</th>
                <th className="px-1.5 py-1 font-semibold">predicate</th>
                <th className="px-1.5 py-1 font-semibold">object</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((t, i) => (
                <tr key={i} className="border-t border-border">
                  <td className="whitespace-nowrap px-1.5 py-1 font-mono">{t.subject}</td>
                  <td className="whitespace-nowrap px-1.5 py-1 font-mono text-primary">{t.predicate}</td>
                  <td className="whitespace-nowrap px-1.5 py-1 font-mono">{t.object}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <button onClick={arm.onAsk} className="text-[10px] font-semibold text-primary hover:underline">Query again</button>
    </div>
  );
}

export function RetrievalRow({
  retrieval,
  activeModes,
  genie,
  rag,
  graph,
}: {
  retrieval: RetrievalResult | null;
  activeModes: Set<string>;
  genie: LiveArm<GenieResult>;
  rag: LiveArm<RagResult>;
  graph: LiveArm<OntobricksResult>;
}) {
  const hasActive = activeModes.size > 0;
  const byId = new Map<string, RetrievalLens>();
  (retrieval?.deterministic_lenses ?? []).forEach((l) => byId.set(l.id, l));

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5">
      {ORDER.map((id) => {
        const active = activeModes.has(id);
        const dim = hasActive && !active;
        const det = byId.get(id);
        const meta = META[id];
        const resolvesAt = det?.resolves_at ?? meta.resolves_at;
        const question = det?.question ?? meta.question;
        const goodAt = det?.good_at ?? meta.good_at;
        const blindTo = det?.blind_to ?? meta.blind_to;

        let body: React.ReactNode;
        let latency: number | null | undefined;
        if (id === "genie_ontology") {
          body = <GenieBody arm={genie} />;
          latency = genie.result?.latency_s;
        } else if (id === "rag") {
          body = <RagBody arm={rag} />;
          latency = rag.result?.latency_s;
        } else if (id === "graph") {
          body = <GraphBody arm={graph} />;
          latency = graph.result?.latency_s;
        } else if (det && id === "metric_view") {
          body = <StatTile rows={det.answer_rows} />;
          latency = det.latency_s;
        } else if (det) {
          body = <MiniTable rows={det.answer_rows} />;
          latency = det.latency_s;
        } else {
          body = <div className="h-16 animate-pulse rounded-md bg-surface-2" />;
        }

        return (
          <Shell
            key={id}
            id={id}
            resolvesAt={resolvesAt}
            question={question}
            latency={latency}
            active={active}
            dim={dim}
            goodAt={goodAt}
            blindTo={blindTo}
          >
            {body}
          </Shell>
        );
      })}
    </div>
  );
}
