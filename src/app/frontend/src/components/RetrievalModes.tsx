import { BookOpen, Database, GitMerge, Share2, Sparkles, type LucideIcon } from "lucide-react";

export interface ModeDef {
  id: string;
  label: string;
  icon: LucideIcon;
  mode: string;
  value: string;
  impact: string;
  live: boolean;
}

export const MODES: ModeDef[] = [
  {
    id: "m0_metric_view",
    label: "Metric View SQL",
    icon: Database,
    mode: "Governed SQL aggregate over a Unity Catalog metric view",
    value: "One source of truth for the KPI — the same number everywhere",
    impact: "Exact & auditable, but the metric must be pre-modeled",
    live: true,
  },
  {
    id: "closure_sql",
    label: "Closure SQL",
    icon: GitMerge,
    mode: "Recursive subsumption join over the ICD-10 closure table",
    value: "Subcodes roll up to the value-set root (E11.21 → E11)",
    impact: "Correct cohort membership a flat code list would miss",
    live: true,
  },
  {
    id: "genie",
    label: "Genie One + Ontology",
    icon: Sparkles,
    mode: "Natural language → Genie One, grounded by inferred snippets + Pages",
    value: "Anyone asks in English and gets the governed answer + citation",
    impact: "Democratizes access; quality tracks snippet / Page density",
    live: true,
  },
  {
    id: "rag",
    label: "A4 Lakebase RAG",
    icon: BookOpen,
    mode: "Hybrid BM25 + vector retrieval over care-protocol docs (doc-level RLS)",
    value: "Returns the exact protocol passage behind the rule",
    impact: "Grounds the answer in the source document; row-secured",
    live: false,
  },
  {
    id: "graph",
    label: "A5 Ontobricks graph",
    icon: Share2,
    mode: "Traversal over an explicit OWL / SNOMED subsumption graph",
    value: "Relationships become navigable and multi-hop",
    impact: "Makes the implicit hierarchy explicit & queryable",
    live: false,
  },
];

export function RetrievalModes({
  activeModes,
  onAskGenie,
  genieBusy,
  onAskRag,
  ragBusy,
}: {
  activeModes: Set<string>;
  onAskGenie?: () => void;
  genieBusy?: boolean;
  onAskRag?: () => void;
  ragBusy?: boolean;
}) {
  const hasActive = activeModes.size > 0;
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {MODES.map((m) => {
        const on = activeModes.has(m.id);
        const dim = hasActive && !on;
        const Icon = m.icon;
        const action =
          m.id === "genie" && onAskGenie
            ? { onClick: onAskGenie, busy: !!genieBusy, idle: "Ask ▸ fires a live call", busyLabel: "Asking…" }
            : m.id === "rag" && onAskRag
            ? { onClick: onAskRag, busy: !!ragBusy, idle: "Retrieve ▸ live passages", busyLabel: "Retrieving…" }
            : null;
        return (
          <div
            key={m.id}
            className={[
              "flex flex-col rounded-xl border bg-surface p-3 transition",
              on ? "border-primary ring-2 ring-primary/40" : "border-border",
              dim ? "opacity-35" : "",
            ].join(" ")}
          >
            <div className="flex items-center gap-2">
              <span className={`flex h-7 w-7 items-center justify-center rounded-lg ${on || !hasActive ? "bg-primary/15 text-primary" : "bg-surface-2 text-muted"}`}>
                <Icon className="h-4 w-4" />
              </span>
              <span className="text-xs font-semibold leading-tight">{m.label}</span>
              <span
                className={`ml-auto rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase ${
                  m.live ? "bg-success/15 text-success" : "bg-surface-2 text-muted"
                }`}
              >
                {m.live ? "live" : "next"}
              </span>
            </div>
            {action && (
              <button
                onClick={action.onClick}
                disabled={action.busy}
                className="mt-2 rounded-md bg-primary px-2 py-1 text-[11px] font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
              >
                {action.busy ? action.busyLabel : action.idle}
              </button>
            )}
            <dl className="mt-2 space-y-1.5 text-[11px] leading-snug">
              <div>
                <dt className="font-semibold text-muted">MODE</dt>
                <dd>{m.mode}</dd>
              </div>
              <div>
                <dt className="font-semibold text-muted">VALUE</dt>
                <dd>{m.value}</dd>
              </div>
              <div>
                <dt className="font-semibold text-muted">IMPACT</dt>
                <dd>{m.impact}</dd>
              </div>
            </dl>
          </div>
        );
      })}
    </div>
  );
}
