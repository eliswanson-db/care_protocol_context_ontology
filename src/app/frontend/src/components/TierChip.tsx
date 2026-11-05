// One visual vocabulary for the three retrieval tiers, shared by the Arena and the Scorecard.
//   1 — the answer is in the retrieved context
//   2 — the retrieved context gives what's needed for ONE SQL query that returns the answer (query run, result judged)
//   3 — neither
export const TIER: Record<string, { label: string; short: string; cls: string }> = {
  tier1: { label: "1 · answer in context", short: "1 · in context", cls: "bg-success/15 text-success" },
  tier2: { label: "2 · one query from context", short: "2 · one query", cls: "bg-primary/15 text-primary" },
  tier3: { label: "3 · not enough", short: "3 · not enough", cls: "bg-destructive/15 text-destructive" },
  no_retrieval: { label: "3 · retrieved nothing", short: "3 · nothing", cls: "bg-surface-2 text-muted" },
  skipped: { label: "Genie skipped its search", short: "search skipped", cls: "bg-warning/15 text-warning" },
  pending: { label: "not scored", short: "pending", cls: "bg-surface-2 text-muted/60" },
};

export function tierKey(s?: { tier?: number | null; n_docs?: number; skipped_search?: boolean } | null): string {
  if (!s || s.tier == null) return "pending";
  if (s.tier === 3 && s.skipped_search) return "skipped";
  if (s.tier === 3 && !s.n_docs) return "no_retrieval";
  return `tier${s.tier}`;
}

export function TierChip({ k, short, runs, stable }: { k: string; short?: boolean; runs?: number[] | null; stable?: boolean | null }) {
  const t = TIER[k] ?? { label: k, short: k, cls: "bg-surface-2 text-muted" };
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      <span className={`inline-block rounded px-1.5 py-0.5 text-[11px] font-semibold ${t.cls}`}>{short ? t.short : t.label}</span>
      {stable === false && runs && runs.length > 1 ? (
        <span className="rounded bg-warning/10 px-1 py-0.5 text-[10px] text-warning" title="The tier differed across runs; the majority is shown.">
          varied: {runs.join("·")}
        </span>
      ) : null}
    </span>
  );
}
