import { AlertTriangle, BookOpen, FileText, Loader2, Lock } from "lucide-react";
import type { RagResult } from "../api";

export type RagStatus = "idle" | "loading" | "done" | "error";

export function RagLive({
  status,
  result,
  error,
  onAsk,
}: {
  status: RagStatus;
  result: RagResult | null;
  error: string | null;
  onAsk: () => void;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="flex flex-wrap items-center gap-2">
        <BookOpen className="h-4 w-4 text-primary" />
        <span className="text-xs font-semibold uppercase tracking-wide text-muted">A4 Lakebase RAG — live</span>
        {result && (
          <span className="flex items-center gap-1 rounded bg-primary/15 px-1.5 py-0.5 text-[10px] font-semibold text-primary">
            {result.mode === "hybrid" ? "hybrid · BM25 + vector" : "lexical · BM25"}
          </span>
        )}
        {result?.semantic_pending && (
          <span className="rounded bg-warning/15 px-1.5 py-0.5 text-[10px] font-semibold text-warning">
            semantic half pending embeddings
          </span>
        )}
        {result && (
          <span className="flex items-center gap-1 rounded bg-surface-2 px-1.5 py-0.5 text-[10px] text-muted">
            <Lock className="h-3 w-3" /> doc-level RLS
          </span>
        )}
        {result && (
          <span className="rounded bg-surface-2 px-1.5 py-0.5 text-[10px] text-muted">
            {result.latency_s}s · {result.search_ext ? "Lakebase Search" : "pg fallback"}
          </span>
        )}
        <button
          onClick={onAsk}
          disabled={status === "loading"}
          className="ml-auto flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
        >
          {status === "loading" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <BookOpen className="h-3.5 w-3.5" />}
          {status === "done" ? "Retrieve again" : "Retrieve protocol passages"}
        </button>
      </div>

      {status === "idle" && (
        <p className="mt-3 text-sm text-muted">
          Retrieve the care-protocol passages that DEFINE the rule behind this patient's status — e.g. what
          HbA1c evidence the GSD numerator accepts. Real passages with document / section / page provenance,
          filtered in-database to the documents this identity is authorized to see.
        </p>
      )}

      {status === "loading" && (
        <div className="mt-3 flex items-center gap-2 text-sm text-muted">
          <Loader2 className="h-4 w-4 animate-spin text-primary" /> Retrieving authorized passages from Lakebase…
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
            <div className="mb-1 font-semibold text-muted">Query</div>
            <div className="text-fg">{result.question}</div>
          </div>

          {result.results.length === 0 ? (
            <div className="rounded-md border border-border bg-surface-2 px-3 py-2 text-xs text-muted">
              No authorized passages matched.
            </div>
          ) : (
            <ol className="space-y-2">
              {result.results.map((p, i) => (
                <li key={`${p.document_id}-${i}`} className="rounded-lg border border-border bg-surface p-3">
                  <div className="flex items-start gap-2">
                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded bg-primary/15 text-[10px] font-semibold text-primary">
                      {i + 1}
                    </span>
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5 text-sm font-semibold">
                        <FileText className="h-3.5 w-3.5 shrink-0 text-primary" />
                        <span className="truncate">{p.title}</span>
                      </div>
                      <div className="mt-0.5 text-[11px] text-primary">
                        {p.section_path}
                        {p.page_start != null ? ` · p${p.page_start}` : ""}
                        {p.measurement_year != null ? ` · MY${p.measurement_year}` : ""}
                      </div>
                      <p className="mt-1.5 text-xs leading-5 text-fg">{p.content}</p>
                      {p.source && <div className="mt-1.5 text-[10px] italic text-muted">{p.source}</div>}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          )}

          <p className="text-[11px] text-muted">
            Document-level RLS enforced in Lakebase — ran as {result.ran_as}.
            {result.semantic_pending
              ? " Lexical/BM25 only until rag.chunks embeddings are backfilled; then this auto-upgrades to hybrid."
              : ""}
          </p>
        </div>
      )}
    </div>
  );
}
