import { AlertTriangle, Loader2 } from "lucide-react";
import type { ReactNode } from "react";

export function Card({ title, sub, children, className = "", right }: { title?: ReactNode; sub?: ReactNode; children: ReactNode; className?: string; right?: ReactNode }) {
  return (
    <section className={`rounded-lg border border-border bg-surface p-4 ${className}`}>
      {(title || right) && (
        <div className="mb-2 flex items-start justify-between gap-3">
          <div>
            {title && <h3 className="text-[13px] font-semibold uppercase tracking-wide text-muted">{title}</h3>}
            {sub && <div className="mt-0.5 text-[12px] text-muted">{sub}</div>}
          </div>
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

const TONE: Record<string, string> = {
  good: "border-success/40 bg-success/10 text-success",
  bad: "border-destructive/40 bg-destructive/10 text-destructive",
  warn: "border-warning/40 bg-warning/10 text-warning",
  info: "border-primary/40 bg-primary/10 text-primary",
  muted: "border-border bg-surface-2 text-muted",
};
export function Chip({ tone = "muted", children, title }: { tone?: keyof typeof TONE; children: ReactNode; title?: string }) {
  return (
    <span title={title} className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md border px-1.5 py-0.5 text-[11px] font-medium ${TONE[tone]}`}>
      {children}
    </span>
  );
}

export function toneFor(v: string | null | undefined): keyof typeof TONE {
  if (!v) return "muted";
  if (["DERIVED", "SELECTED", "MET", "NOT_TRIGGERED", "ready", "approved", "PASS", "Y", "CONSISTENT", "true"].includes(v)) return "good";
  if (["EXCLUDED", "TRIGGERED", "NOT_MET", "failed", "FAIL", "rejected"].includes(v) || v.startsWith("NO_") || v.startsWith("NOT_IN")) return "bad";
  if (["ELIGIBLE_NOT_SELECTED", "manual_action_required", "candidate", "superseded", "ENROLLED_BUT_RULE_INELIGIBLE", "NOT_EVALUABLE"].includes(v)) return "warn";
  if (["planned", "pending_sync", "provisioning"].includes(v)) return "info";
  return "muted";
}

export function Table<T extends object>({ rows, cols, onRow, highlight, max = 500 }: {
  rows: T[]; cols: { key: string; label: string; render?: (r: any) => ReactNode; className?: string }[];
  onRow?: (r: any) => void; highlight?: (r: any) => boolean; max?: number;
}) {
  if (!rows.length) return <div className="py-2 text-[12px] text-muted">No rows.</div>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[12px]">
        <thead>
          <tr className="border-b border-border text-left text-muted">
            {cols.map((c) => <th key={c.key} className="px-2 py-1.5 font-semibold">{c.label}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, max).map((r, i) => (
            <tr key={i} onClick={onRow ? () => onRow(r) : undefined}
              className={`border-b border-border/60 ${onRow ? "cursor-pointer hover:bg-surface-2" : ""} ${highlight?.(r) ? "bg-primary/5" : ""}`}>
              {cols.map((c) => (
                <td key={c.key} className={`px-2 py-1.5 align-top ${c.className ?? ""}`}>{c.render ? c.render(r) : fmt((r as Record<string, unknown>)[c.key])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > max && <div className="py-1 text-[11px] text-muted">{rows.length - max} more rows not shown.</div>}
    </div>
  );
}

export function fmt(v: any): ReactNode {
  if (typeof v === "string" && v.startsWith("[") && v.endsWith("]")) {
    try { v = JSON.parse(v); } catch { /* not a JSON array: show as is */ }
  }
  if (v === null || v === undefined || v === "" || (Array.isArray(v) && v.length === 0)) return <span className="text-muted">—</span>;
  if (Array.isArray(v)) return v.join(", ");
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export const num = (v: any, d = 1) => (v === null || v === undefined || v === "" ? "—" : Number(v).toFixed(d));
export const pct = (v: any, d = 1) => (v === null || v === undefined || v === "" ? "—" : `${(Number(v) * 100).toFixed(d)}%`);

export function Loading({ what = "Loading" }: { what?: string }) {
  return <div className="flex items-center gap-2 p-6 text-sm text-muted"><Loader2 className="h-4 w-4 animate-spin" /> {what}…</div>;
}
export function ErrorBox({ error }: { error: string }) {
  return (
    <div className="m-4 flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> <span>{error}</span>
    </div>
  );
}
export function Code({ children }: { children: ReactNode }) {
  return <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-surface-2 p-2 font-mono text-[11px] leading-snug">{children}</pre>;
}
