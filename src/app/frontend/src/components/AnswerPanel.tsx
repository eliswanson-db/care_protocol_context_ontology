import { ChevronRight, CornerDownRight, Sparkles } from "lucide-react";
import type { Claim } from "../api";

const MODE_LABEL: Record<string, string> = {
  metric_view: "Metric View",
  closure: "Closure table",
  genie_ontology: "Genie One + Ontology",
  rag: "A4 Lakebase RAG",
  graph: "Ontobricks graph",
};

export function AnswerPanel({
  question,
  claims,
  activeClaimId,
  onSelect,
  stageTitle,
}: {
  question: string;
  claims: Claim[];
  activeClaimId: string | null;
  onSelect: (id: string | null) => void;
  stageTitle: (key: string) => string;
}) {
  const active = claims.find((c) => c.id === activeClaimId) ?? null;

  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="flex items-center gap-2 text-[12px] font-semibold uppercase tracking-wide text-muted">
        <Sparkles className="h-4 w-4 text-primary" /> Modeled answer
      </div>
      <p className="mt-2 text-base font-semibold">{question}</p>

      <p className="mt-3 text-[18px] leading-8">
        {claims.map((c) => {
          const on = c.id === activeClaimId;
          return (
            <span key={c.id}>
              <span className="text-fg">{c.before}</span>
              <button
                onClick={() => onSelect(on ? null : c.id)}
                className={[
                  "mx-0.5 inline rounded px-1.5 py-0.5 text-[17px] font-semibold transition",
                  on ? "bg-primary text-white" : "bg-primary/12 text-primary hover:bg-primary/20",
                ].join(" ")}
              >
                {c.chip}
              </button>
              {c.suffix ? <span className="text-fg">{c.suffix}</span> : null}
            </span>
          );
        })}
      </p>

      <div className="mt-3 text-[11px] text-muted">
        {active ? "Showing where this claim comes from — follow it back below." : "Click any highlighted claim to trace it back to source."}
      </div>

      {active && (
        <div className="mt-3 space-y-2 rounded-lg border border-primary/30 bg-primary/5 p-3">
          <div className="flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wide text-primary">
            <CornerDownRight className="h-3.5 w-3.5" /> Provenance trail
          </div>
          <div className="flex flex-wrap items-center gap-1 text-xs">
            {active.stage_path.map((k, i) => (
              <span key={k} className="flex items-center gap-1">
                {i > 0 && <ChevronRight className="h-3 w-3 text-muted" />}
                <span className="rounded bg-surface px-1.5 py-0.5 font-medium">{stageTitle(k)}</span>
              </span>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-1.5 pt-1 text-[11px]">
            <span className="font-semibold text-muted">Answerable via:</span>
            {active.modes.length ? (
              active.modes.map((m) => (
                <span key={m} className="rounded bg-surface px-1.5 py-0.5 font-medium text-primary">
                  {MODE_LABEL[m] ?? m}
                </span>
              ))
            ) : (
              <span className="text-muted">raw source datum (no retrieval tool needed)</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
