import {
  AlertTriangle,
  BookOpen,
  ChevronDown,
  Database,
  FileText,
  Loader2,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useState } from "react";
import type { GenieResult } from "../api";

export type GenieStatus = "idle" | "loading" | "done" | "error";

const CITE_ICON: Record<string, typeof Database> = {
  snippet_search: Sparkles,
  knowledge_page: BookOpen,
  page: BookOpen,
  metric_view: Database,
  table: Database,
};

const CITE_LABEL: Record<string, string> = {
  snippet_search: "ontology snippet search",
  knowledge_page: "ontology Page",
  page: "ontology Page",
  metric_view: "metric view",
  table: "table",
};

export function GenieLive({
  status,
  result,
  error,
  onAsk,
}: {
  status: GenieStatus;
  result: GenieResult | null;
  error: string | null;
  onAsk: () => void;
}) {
  const [showSql, setShowSql] = useState(false);

  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Sparkles className="h-4 w-4 text-primary" />
        <span className="text-xs font-semibold uppercase tracking-wide text-muted">Genie One — live</span>
        {result && (
          <span
            className={`ml-1 flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-semibold ${
              result.ontology_used ? "bg-success/15 text-success" : "bg-surface-2 text-muted"
            }`}
          >
            <ShieldCheck className="h-3 w-3" />
            {result.ontology_used ? "ontology consulted" : "no ontology signal"}
          </span>
        )}
        {result && (
          <span className="rounded bg-surface-2 px-1.5 py-0.5 text-[10px] text-muted">{result.latency_s}s · arm {result.arm}</span>
        )}
        <button
          onClick={onAsk}
          disabled={status === "loading"}
          className="ml-auto flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
        >
          {status === "loading" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
          {status === "done" ? "Ask again" : "Ask Genie One"}
        </button>
      </div>

      {status === "idle" && (
        <p className="mt-3 text-sm text-muted">
          Fire a real Genie One call for this patient — natural language over the whole chain. It reasons on the
          governed metric view and the Genie Ontology, then answers in English with citations. Watch whether it
          consults the ontology (the ADR-0018 ON/OFF signal).
        </p>
      )}

      {status === "loading" && (
        <div className="mt-3 flex items-center gap-2 text-sm text-muted">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          Genie One is reasoning over the metric view + ontology… this can take ~1 minute.
        </div>
      )}

      {status === "error" && (
        <div className="mt-3 flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      {status === "done" && result && (
        <div className="mt-3 space-y-3">
          <div className="rounded-lg border border-border bg-surface-2 p-3 text-xs">
            <div className="mb-1 font-semibold text-muted">Question asked</div>
            <div className="text-fg">{result.question}</div>
          </div>

          <div className="whitespace-pre-wrap rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm leading-6">
            {result.answer || "(no answer text returned)"}
          </div>

          {result.citations.length > 0 && (
            <div>
              <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">How it answered — citations</div>
              <div className="flex flex-wrap gap-1.5">
                {result.citations.map((c, i) => {
                  const Icon = CITE_ICON[c.kind] ?? FileText;
                  return (
                    <span
                      key={i}
                      className="flex items-center gap-1 rounded border border-border bg-surface px-2 py-1 text-[11px]"
                      title={c.detail}
                    >
                      <Icon className="h-3 w-3 text-primary" />
                      <span className="font-medium">{CITE_LABEL[c.kind] ?? c.kind}</span>
                    </span>
                  );
                })}
              </div>
            </div>
          )}

          {result.generated_sql && (
            <div className="rounded-lg border border-border">
              <button
                onClick={() => setShowSql((s) => !s)}
                className="flex w-full items-center justify-between px-3 py-2 text-left text-xs font-semibold text-muted"
              >
                <span className="flex items-center gap-1.5">
                  <Database className="h-3.5 w-3.5" /> Generated SQL
                </span>
                <ChevronDown className={`h-4 w-4 transition ${showSql ? "rotate-180" : ""}`} />
              </button>
              {showSql && (
                <pre className="overflow-x-auto border-t border-border px-3 py-2 text-[11px] leading-relaxed">
                  <code>{result.generated_sql}</code>
                </pre>
              )}
            </div>
          )}

          <p className="text-[11px] text-muted">
            AI-generated over synthetic data — verify before any clinical use. Ran as {result.ran_as}.
          </p>
        </div>
      )}
    </div>
  );
}
