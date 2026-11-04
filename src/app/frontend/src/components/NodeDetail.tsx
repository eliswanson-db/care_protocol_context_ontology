import { AlertTriangle, ChevronDown, ChevronRight, Database, Loader2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Stage, type StageDetail, type StageSection } from "../api";
import { GenieMarkdown } from "./GenieMarkdown";

// Same phase accent the card uses, so the click-in reads as "this layer".
const TIER: Record<string, string> = {
  protocol: "var(--tier-protocol)", bronze: "var(--tier-bronze)", silver: "var(--tier-silver)",
  closure: "var(--tier-silver)", cohort: "var(--tier-silver)", gold: "var(--tier-gold)",
  metric: "var(--tier-gold)", page: "var(--tier-page)", ontobricks: "var(--tier-page)",
  raw: "var(--tier-protocol)", rag: "var(--tier-page)", closure_ret: "var(--tier-page)",
};

function Bold({ text }: { text: string }) {
  return (
    <>
      {text.split(/(\*\*[^*]+\*\*)/g).map((t, i) =>
        t.startsWith("**") ? <strong key={i} className="font-semibold text-fg">{t.slice(2, -2)}</strong> : <span key={i}>{t}</span>)}
    </>
  );
}

function cell(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  const s = String(v);
  return /^\d{4}-\d{2}-\d{2}T/.test(s) ? s.slice(0, 10) : s;
}

function Table({ rows, empty }: { rows: Record<string, unknown>[]; empty?: string }) {
  if (!rows.length) return <div className="rounded-md border border-dashed border-border px-3 py-2 text-[13px] text-muted">{empty ?? "No rows."}</div>;
  const cols = Object.keys(rows[0]);
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full text-left text-[12.5px]">
        <thead className="bg-surface-2 text-muted">
          <tr>{cols.map((c) => <th key={c} className="whitespace-nowrap px-2.5 py-1.5 font-semibold">{c}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-border">
              {cols.map((c) => (
                <td key={c} className="max-w-[22rem] truncate px-2.5 py-1.5 font-mono tabular-nums" title={cell(r[c])}>
                  {cell(r[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Section({ s, accent }: { s: StageSection; accent: string }) {
  let body: React.ReactNode = null;
  switch (s.kind) {
    case "quote":
      body = (
        <blockquote className="rounded-r-md border-l-4 bg-surface-2 px-4 py-3 text-[14.5px] leading-relaxed"
          style={{ borderColor: accent }}>{s.text}</blockquote>
      );
      break;
    case "kv":
      body = (
        <dl className="grid grid-cols-[minmax(10rem,auto)_1fr] gap-x-4 gap-y-1.5 text-[13.5px]">
          {Object.entries(s.data ?? {}).map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-muted">{k}</dt>
              <dd className="font-medium">{cell(v)}</dd>
            </div>
          ))}
        </dl>
      );
      break;
    case "table":
      body = <Table rows={s.rows ?? []} empty={s.empty} />;
      break;
    case "triples":
      body = (
        <Table rows={(s.rows ?? []).map((t) => ({ subject: t.subject, predicate: t.predicate, object: t.object }))}
          empty={s.empty} />
      );
      break;
    case "chain":
      body = (
        <div className="flex flex-wrap items-center gap-1.5">
          {(s.nodes ?? []).map((n, i) => (
            <div key={i} className="flex items-center gap-1.5">
              {i > 0 && <span className="text-[15px] font-bold text-muted">⊑</span>}
              <div className="rounded-lg border px-3 py-1.5" style={{ borderColor: accent }}>
                <div className="font-mono text-[14px] font-bold">{n.code}</div>
                <div className="max-w-[16rem] truncate text-[11px] text-muted" title={n.name}>{n.name}</div>
              </div>
            </div>
          ))}
        </div>
      );
      break;
    case "doc":
      body = (
        <article className="max-h-[30rem] space-y-2.5 overflow-auto rounded-md border border-border bg-surface-2 px-5 py-4 text-[13.5px] leading-relaxed">
          {(s.blocks ?? []).map((b, i) => {
            if (b.type === "h") return <h4 key={i} className="pt-1 text-[15px] font-bold tracking-tight">{b.text}</h4>;
            if (b.type === "p") return <p key={i} className="text-fg/85"><Bold text={b.text ?? ""} /></p>;
            if (b.type === "rule")
              return (
                <div key={i} className="rounded-md border-l-4 px-3 py-2"
                  style={{ borderColor: accent, background: b.highlight ? `color-mix(in srgb, ${accent} 16%, transparent)` : undefined }}>
                  <Bold text={b.text ?? ""} />
                  {b.highlight && <span className="ml-2 text-[11px] font-semibold uppercase tracking-wide" style={{ color: accent }}>← Step 3 trigger</span>}
                </div>
              );
            const [head, ...rows] = b.rows ?? [];
            return (
              <div key={i} className="overflow-x-auto rounded-md border border-border bg-surface">
                <table className="w-full text-left text-[12.5px]">
                  <thead className="bg-surface-2 text-muted">
                    <tr>{(head ?? []).map((h, j) => <th key={j} className="px-2.5 py-1.5 font-semibold">{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {rows.map((r, j) => {
                      const hi = (b.highlight_rows ?? []).includes(j + 1);
                      return (
                        <tr key={j} className="border-t border-border"
                          style={hi ? { background: `color-mix(in srgb, ${accent} 16%, transparent)` } : undefined}>
                          {r.map((c, k) => <td key={k} className="px-2.5 py-1.5 align-top"><Bold text={c} /></td>)}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            );
          })}
        </article>
      );
      break;
    case "path":
      body = (
        <div className="flex flex-wrap items-center gap-y-2">
          {(s.steps ?? []).map((st, i) => (
            <div key={i} className="flex items-center">
              <div className="rounded-lg border-2 bg-surface px-3 py-1.5" style={{ borderColor: accent }}>
                <div className="font-mono text-[13px] font-bold">{st.node}</div>
                {st.name && <div className="max-w-[13rem] truncate text-[11px] text-muted" title={st.name}>{st.name}</div>}
              </div>
              {st.edge && (
                <div className="flex flex-col items-center px-1.5">
                  <span className="font-mono text-[11px] font-semibold" style={{ color: accent }}>{st.edge}</span>
                  <span className="text-[15px] leading-none text-muted">→</span>
                </div>
              )}
            </div>
          ))}
        </div>
      );
      break;
    case "code":
      body = <pre className="overflow-x-auto rounded-md bg-surface-2 px-3 py-2.5 text-[12.5px] leading-relaxed"><code>{s.text}</code></pre>;
      break;
    case "markdown":
      body = (
        <GenieMarkdown md={(s.text ?? "").replace(/^>\s?/gm, "")}
          className="max-h-72 space-y-1.5 overflow-auto rounded-md border border-border bg-surface-2 p-3 text-[13.5px] leading-6 text-fg/90" />
      );
      break;
    case "chips":
      body = (
        <div className="flex flex-wrap gap-1.5">
          {(s.items ?? []).map((c) => (
            <span key={c} className="rounded border border-border bg-surface-2 px-2 py-0.5 font-mono text-[12px]">{c}</span>
          ))}
        </div>
      );
      break;
  }
  return (
    <section>
      <div className="mb-1.5 text-[12px] font-semibold uppercase tracking-wide text-muted">{s.label}</div>
      {body}
    </section>
  );
}

export function NodeDetail({ stage, patientId, onClose }: { stage: Stage; patientId: string; onClose: () => void }) {
  const [d, setD] = useState<StageDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [showSql, setShowSql] = useState(false);
  const accent = TIER[stage.key] ?? "var(--primary)";

  useEffect(() => {
    let live = true;
    setD(null); setErr(null); setShowSql(false);
    api.stage(patientId, stage.key)
      .then((r) => live && setD(r))
      .catch((e) => live && setErr(String(e)));
    return () => { live = false; };
  }, [patientId, stage.key]);

  return (
    <div className="mt-3 rounded-xl border border-t-[3px] border-border bg-surface p-5" style={{ borderTopColor: accent }}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[17px] font-bold tracking-tight">{d?.title ?? stage.title}</div>
          <div className="mt-0.5 text-[13.5px] text-muted">{d?.what ?? stage.semantic_concept}</div>
        </div>
        <button onClick={onClose} className="rounded p-1 text-muted hover:text-fg" aria-label="Close detail">
          <X className="h-5 w-5" />
        </button>
      </div>

      {!d && !err && (
        <div className="mt-4 flex items-center gap-2 text-[14px] text-muted">
          <Loader2 className="h-4 w-4 animate-spin" style={{ color: accent }} />
          Retrieving this patient's {stage.key === "ontobricks" ? "edges from the live triplestore (~5s)" : "data at this layer"}…
        </div>
      )}
      {err && (
        <div className="mt-4 flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-[13px] text-destructive">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {err}
        </div>
      )}

      {d && (
        <div className="mt-4 space-y-5">
          <div className="rounded-lg px-4 py-3 text-[15px] font-medium leading-snug"
            style={{ background: `color-mix(in srgb, ${accent} 12%, transparent)` }}>
            {d.takeaway}
          </div>

          {d.warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-2 rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-[13px]">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" /> <span>{w}</span>
            </div>
          ))}

          {d.sections.map((s, i) => <Section key={i} s={s} accent={accent} />)}

          <div className="border-t border-border pt-3">
            <button onClick={() => setShowSql((v) => !v)} className="flex items-center gap-1.5 text-[13px] font-semibold text-muted hover:text-fg">
              {showSql ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              <Database className="h-3.5 w-3.5" /> How this was retrieved ({d.queries.length} {d.queries.length === 1 ? "query" : "queries"} · {d.latency_s}s)
            </button>
            {d.source && <div className="mt-1 pl-6 font-mono text-[11.5px] text-muted">{d.source}</div>}
            {showSql && (
              <div className="mt-2 space-y-2.5 pl-6">
                {d.queries.map((q, i) => (
                  <div key={i}>
                    <div className="text-[12px] font-semibold">{q.label}</div>
                    <pre className="mt-1 overflow-x-auto rounded-md bg-surface-2 px-3 py-2 text-[11.5px] leading-relaxed"><code>{q.sql}</code></pre>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
