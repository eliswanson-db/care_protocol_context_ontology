import { AlertTriangle, BadgeCheck, CircleHelp } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, type BenchmarkV2, type V2Cell } from "../api";
import { GenieMarkdown } from "../components/GenieMarkdown";
import { TierChip, tierKey } from "../components/TierChip";

// The HEDIS benchmark (plan steps 5-6): 8 locked questions, five retrieval approaches each driven by ONE simple
// agent, and Genie One as the reasoning engine. Every cell opens to what was retrieved, the query, and why it was
// scored the way it was. Nothing is designed to win; each question's prediction is shown next to what happened.

const COLOR: Record<string, string> = {
  metric_view: "var(--lens-metric_view)", closure_sql: "var(--lens-closure)", rag: "var(--lens-rag)",
  genie_ontology: "var(--lens-genie_ontology)", ontobricks: "var(--lens-graph)", genie_one: "var(--primary)",
};

/** Where a demo's benchmark comes from, and how its page describes itself. HEDIS is the default. */
export interface BenchmarkSource {
  load: () => Promise<BenchmarkV2>;
  intro: (horizon: string, n: number) => string;
  subjectRule: string;  // "Patient" / "Participant", for the chosen-by-rule line
}
export const HEDIS_BENCHMARK: BenchmarkSource = {
  load: api.benchmarkV2, subjectRule: "Patient",
  intro: (h, n) => `${n} real analyst questions, all about MY2026 through ${h}.`,
};
export const LS_BENCHMARK: BenchmarkSource = {
  load: api.lsBenchmark, subjectRule: "Participant",
  intro: (h, n) => `${n} real study-team questions, all on data through the ${h} cutoff.`,
};

function GenieOneChip({ c }: { c?: V2Cell }) {
  if (!c || c.tier == null) return <span className="rounded bg-surface-2 px-1.5 py-0.5 text-[11px] text-muted">pending</span>;
  const ok = c.tier === 1;
  const label = ok ? "✓ answered" : c.outcome === "incomplete" ? "✗ incomplete" : c.outcome === "wrong" ? "✗ wrong"
    : c.outcome === "not_found" ? "✗ found none" : "✗ not answered";
  const cls = ok ? "bg-success/20 text-success" : c.outcome === "incomplete" ? "bg-warning/15 text-warning" : "bg-destructive/15 text-destructive";
  return <span className={`inline-block rounded px-1.5 py-0.5 text-[11px] font-semibold ${cls}`}>{label}</span>;
}

const VERDICT: Record<string, { mark: string; cls: string; label: string }> = {
  stated: { mark: "✓", cls: "text-success", label: "stated" },
  missing: { mark: "–", cls: "text-warning", label: "missing" },
  contradicted: { mark: "✗", cls: "text-destructive", label: "contradicted" },
};

function Cell({ armId, c }: { armId: string; c?: V2Cell }) {
  return armId === "genie_one" ? <GenieOneChip c={c} /> : <TierChip k={tierKey(c)} short />;
}

function answered(armId: string, c?: V2Cell) {
  return armId === "genie_one" ? c?.tier === 1 : c?.tier === 1 || c?.tier === 2;
}

function Detail({ q, arm, c, subject }: { q: BenchmarkV2["questions"][number]; arm: BenchmarkV2["arms"][number]; c: V2Cell; subject: string }) {
  const facts = c.facts ?? [];
  return (
    <div className="mt-4 rounded-xl border border-t-[3px] border-border bg-surface p-5" style={{ borderTopColor: COLOR[arm.id] }}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[12px] font-bold uppercase tracking-wider" style={{ color: COLOR[arm.id] }}>{arm.label}</span>
        <span className="text-muted">·</span>
        <span className="text-[13px] font-semibold">{q.id.toUpperCase()}</span>
        <Cell armId={arm.id} c={c} />
        {c.hand_verified ? (
          <span className="inline-flex items-center gap-1 rounded bg-success/10 px-1.5 py-0.5 text-[11px] text-success">
            <BadgeCheck className="h-3.5 w-3.5" /> hand-verified
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 rounded bg-surface-2 px-1.5 py-0.5 text-[11px] text-muted">
            <CircleHelp className="h-3.5 w-3.5" /> judge-scored, not hand-verified yet
          </span>
        )}
      </div>
      <h3 className="mt-2 text-[17px] font-semibold leading-snug">{q.question}</h3>
      {c.override && (
        <p className="mt-2 rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-[13px]">
          <b>Hand check overrides the judge</b> (judge: tier {c.judge_tier}{c.judge_outcome ? `, ${c.judge_outcome.replace("_", " ")}` : ""}): {c.override}
        </p>
      )}
      {c.hand_note && !c.override && (
        <p className="mt-2 rounded-md border border-border bg-surface-2 px-3 py-2 text-[13px]"><b>Hand check:</b> {c.hand_note}</p>
      )}
      {q.hero_rule && <p className="mt-1 text-[12.5px] text-muted">{subject} chosen by rule: {q.hero_rule}.</p>}

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <section>
          <div className="text-[11px] font-bold uppercase tracking-wider text-muted">Predicted before the run</div>
          <p className="mt-1 text-[13.5px]">
            {c.prediction ?? (arm.kind === "end_to_end"
              ? "No prediction recorded: the Genie One column was added after the questions were locked."
              : "—")}
          </p>
          {arm.kind !== "end_to_end" && (
            <>
              <div className="mt-3 text-[11px] font-bold uppercase tracking-wider text-muted">What it retrieved</div>
              <p className="mt-1 text-[13.5px]">{c.retrieved || "—"}</p>
            </>
          )}
          {c.reason && (
            <>
              <div className="mt-3 text-[11px] font-bold uppercase tracking-wider text-muted">Why this score</div>
              <p className="mt-1 text-[13.5px]">{c.reason}</p>
            </>
          )}
          {c.declined_reason && (
            <>
              <div className="mt-3 text-[11px] font-bold uppercase tracking-wider text-muted">Why the agent wrote no query</div>
              <p className="mt-1 text-[13.5px]">“{c.declined_reason}”</p>
            </>
          )}
        </section>
        <section>
          <div className="text-[11px] font-bold uppercase tracking-wider text-muted">Expected facts (gold) and the judgment</div>
          <ul className="mt-1 space-y-2">
            {q.expected_facts.map((f, i) => {
              const j = facts[i];
              const best = j?.in_context?.ok ? j.in_context : (j?.in_result ?? j?.in_context);
              const v = VERDICT[best?.verdict ?? (best?.ok ? "stated" : "missing")];
              const where = j?.in_context?.ok ? "in what it retrieved" : j?.in_result ? "in the query result" :
                arm.kind === "end_to_end" ? "in its answer" : "in what it retrieved";
              return (
                <li key={i} className="rounded-md border border-border bg-surface-2 px-3 py-2 text-[13px]">
                  <span className={`font-bold ${v.cls}`}>{v.mark}</span> {f}
                  <div className="mt-1 text-[12px] text-muted"><span className={v.cls}>{v.label} {where}</span>
                    {best?.rationale ? ` · ${best.rationale}` : ""}</div>
                  {best?.quote && <div className="mt-1 border-l-2 border-border pl-2 text-[12px] italic text-muted">“{best.quote}”</div>}
                </li>
              );
            })}
          </ul>
        </section>
      </div>

      {c.answer && (
        <section className="mt-4">
          <div className="text-[11px] font-bold uppercase tracking-wider text-muted">Genie One's answer</div>
          <div className="mt-1 max-h-96 overflow-auto rounded-md bg-surface-2 p-3 text-[13px]">
            <GenieMarkdown md={c.answer.replace(/<!--[\s\S]*?-->/g, "")} />
          </div>
          {!!c.genie_sql?.length && (
            <details className="mt-2">
              <summary className="cursor-pointer text-[12.5px] text-muted">SQL Genie One ran ({c.genie_sql.length})</summary>
              {c.genie_sql.map((s, i) => (
                <pre key={i} className="mt-1 max-h-60 overflow-auto rounded-md bg-surface-2 p-3 text-[12px]">{s}</pre>
              ))}
            </details>
          )}
        </section>
      )}

      {arm.kind !== "end_to_end" && (c.sql || c.sql_error) && (
        <section className="mt-4">
          <div className="text-[11px] font-bold uppercase tracking-wider text-muted">
            {`The one query (${c.interface})`}
          </div>
          {c.sql && <pre className="mt-1 max-h-60 overflow-auto rounded-md bg-surface-2 p-3 text-[12px]">{c.sql}</pre>}
          {c.sql_error && <p className="mt-1 text-[12.5px] text-destructive">{c.sql_error}</p>}
          {c.sql_result && <pre className="mt-1 max-h-48 overflow-auto rounded-md bg-surface-2 p-3 text-[12px]">{c.sql_result}</pre>}
        </section>
      )}
    </div>
  );
}

export function Benchmark({ source = HEDIS_BENCHMARK }: { source?: BenchmarkSource }) {
  const [d, setD] = useState<BenchmarkV2 | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sel, setSel] = useState<{ q: string; a: string } | null>(null);

  useEffect(() => {
    source.load().then(setD).catch((e) => setErr(String(e)));
  }, [source]);

  const totals = useMemo(() => {
    if (!d) return {};
    return Object.fromEntries(d.arms.map((a) => [a.id, d.questions.filter((q) => answered(a.id, q.cells[a.id])).length]));
  }, [d]);

  if (err) return <div className="m-6 text-sm text-destructive">{err}</div>;
  if (!d) return <div className="m-6 h-40 animate-pulse rounded-xl bg-surface-2" />;
  if (!d.available) return <div className="m-6 text-sm text-muted">No benchmark results are bundled with this build.</div>;

  const selQ = sel && d.questions.find((q) => q.id === sel.q);
  const selA = sel && d.arms.find((a) => a.id === sel.a);

  return (
    <main className="min-w-0 flex-1 overflow-y-auto px-6 py-5">
      <div className="text-[12px] font-bold uppercase tracking-wider text-primary">Benchmark</div>
      <h1 className="mt-1 text-[26px] font-bold leading-tight tracking-tight">Which context answers which question?</h1>
      <p className="mt-1.5 max-w-4xl text-[14.5px] text-muted">
        {source.intro(d.meta.data_horizon, d.questions.length)} The five retrieval approaches each
        get the same simple agent: it reads what the approach retrieved and may make one query in that approach's own
        interface. Genie One, a multi-step agent, answers on its own. Nothing is designed to win; click any cell for what
        was retrieved, the query, and why it scored as it did.
      </p>
      <div className="mt-3 flex flex-wrap gap-2 text-[12px]">
        {d.meta.mode === "test" && (
          <span className="inline-flex items-center gap-1 rounded-md bg-warning/15 px-2 py-1 text-warning">
            <AlertTriangle className="h-3.5 w-3.5" /> Test mode: 1 run per cell (final runs use 3)
          </span>
        )}
        <span className="rounded-md bg-surface-2 px-2 py-1 text-muted">
          Gold = hand-verified answer key, never in any approach's context
        </span>
        <span className="rounded-md bg-surface-2 px-2 py-1 text-muted">Agent {d.meta.agent} · judge {d.meta.judge}</span>
      </div>

      <div className="mt-5 overflow-x-auto rounded-xl border border-border bg-surface">
        <table className="w-full border-collapse text-left text-[13px]">
          <thead>
            <tr className="border-b border-border">
              <th className="px-3 py-2.5 font-semibold text-muted">Question</th>
              {d.arms.map((a) => (
                <th key={a.id} className={`px-3 py-2.5 font-semibold ${a.kind === "end_to_end" ? "border-l border-border" : ""}`}
                  style={{ color: COLOR[a.id] }}>
                  {a.label}
                  <div className="text-[10.5px] font-normal text-muted">{a.kind === "end_to_end" ? "reasoning engine" : "simple agent"}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {d.questions.map((q) => (
              <tr key={q.id} className="border-b border-border/60">
                <td className="px-3 py-2" title={q.question}>
                  <span className="mr-1.5 font-mono text-[12px] text-muted">{q.id}</span>
                  {q.short ?? q.question}
                </td>
                {d.arms.map((a) => {
                  const active = sel?.q === q.id && sel?.a === a.id;
                  return (
                    <td key={a.id} className={`px-3 py-2 ${a.kind === "end_to_end" ? "border-l border-border" : ""}`}>
                      <button onClick={() => setSel(active ? null : { q: q.id, a: a.id })}
                        className={`rounded-md p-0.5 ${active ? "ring-2 ring-primary" : "hover:bg-surface-2"}`}>
                        <Cell armId={a.id} c={q.cells[a.id]} />
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
            <tr>
              <td className="px-3 py-2.5 text-[12px] font-semibold text-muted">Answered</td>
              {d.arms.map((a) => (
                <td key={a.id} className={`px-3 py-2.5 font-semibold ${a.kind === "end_to_end" ? "border-l border-border" : ""}`}>
                  {totals[a.id]} of {d.questions.length}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-[12px] text-muted">
        ✓ in context = every expected fact was in what the approach retrieved · ✓ one query = the agent's one query
        returned the rest · ✗ incomplete = some facts stated, one missing · ✗ found none = its query ran but stated none ·
        ✗ wrong = it contradicts an expected fact ·
        ✗ no query = it retrieved something, but the agent couldn't write its one query (it says why) · ✗ nothing = it
        retrieved nothing. Genie One: ✓ when its own answer states every expected fact. Hover a question for its full
        text.
      </p>

      {selQ && selA && <Detail q={selQ} arm={selA} c={selQ.cells[selA.id]} subject={source.subjectRule} />}
    </main>
  );
}
