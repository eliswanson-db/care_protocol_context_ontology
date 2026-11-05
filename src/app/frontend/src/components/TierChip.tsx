// One visual vocabulary for the retrieval verdicts, shared by the Arena and the Scorecard.
// A cell is ANSWERED if the retrieved context either states the answer (tier 1) or lets the agent write one query
// that returns it (tier 2). Otherwise it says WHY it wasn't.
export const TIER: Record<string, { label: string; short: string; cls: string; ok?: boolean }> = {
  tier1: { label: "✓ Answered — in the retrieved context", short: "✓ in context", cls: "bg-success/20 text-success", ok: true },
  tier2: { label: "✓ Answered — one query from the context", short: "✓ one query", cls: "bg-success/10 text-success", ok: true },
  wrong_answer: { label: "✗ Query ran, wrong answer", short: "✗ wrong answer", cls: "bg-destructive/15 text-destructive" },
  query_failed: { label: "✗ Query failed", short: "✗ query failed", cls: "bg-destructive/15 text-destructive" },
  no_query: { label: "✗ Not enough to write a query", short: "✗ no query", cls: "bg-surface-2 text-muted" },
  no_retrieval: { label: "✗ Retrieved nothing", short: "✗ nothing", cls: "bg-surface-2 text-muted" },
  skipped: { label: "– Genie skipped its search", short: "– skipped", cls: "bg-warning/15 text-warning" },
  pending: { label: "not scored", short: "pending", cls: "bg-surface-2 text-muted/60" },
};

export function tierKey(s?: { tier?: number | null; n_docs?: number; skipped_search?: boolean; sql?: string | null; sql_error?: string | null } | null): string {
  if (!s || s.tier == null) return "pending";
  if (s.tier === 1 || s.tier === 2) return `tier${s.tier}`;
  if (s.skipped_search) return "skipped";
  if (!s.n_docs) return "no_retrieval";
  if (!s.sql) return "no_query";
  return s.sql_error ? "query_failed" : "wrong_answer";
}

export function TierChip({ k, short, runs, stable }: { k: string; short?: boolean; runs?: number[] | null; stable?: boolean | null }) {
  const t = TIER[k] ?? { label: k, short: k, cls: "bg-surface-2 text-muted" };
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      <span className={`inline-block rounded px-1.5 py-0.5 text-[11px] font-semibold ${t.cls}`}>{short ? t.short : t.label}</span>
      {stable === false && runs && runs.length > 1 ? (
        <span className="rounded bg-warning/10 px-1 py-0.5 text-[10px] text-warning" title="The tier differed across runs; the majority is shown.">
          varied
        </span>
      ) : null}
    </span>
  );
}
