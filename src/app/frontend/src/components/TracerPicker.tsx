import { PanelLeftClose, Users } from "lucide-react";
import type { Tracer } from "../api";

export function TracerPicker({
  tracers,
  selected,
  onSelect,
  loading,
  collapsed,
  onToggle,
}: {
  tracers: Tracer[];
  selected: string | null;
  onSelect: (trace: string) => void;
  loading: boolean;
  collapsed: boolean;
  onToggle: () => void;
}) {
  if (collapsed) {
    return (
      <aside className="flex w-12 shrink-0 flex-col items-center gap-3 border-r border-border bg-surface py-3">
        <button
          onClick={onToggle}
          className="flex h-8 w-8 items-center justify-center rounded-md text-muted hover:bg-surface-2 hover:text-fg"
          aria-label="Show traces"
          title="Show traces"
        >
          <Users className="h-[18px] w-[18px]" />
        </button>
        <div className="text-[10px] font-semibold uppercase tracking-wider text-muted [writing-mode:vertical-rl]">
          {tracers.length} traces
        </div>
      </aside>
    );
  }
  return (
    <aside className="w-72 shrink-0 overflow-y-auto border-r border-border bg-surface">
      <div className="flex items-center justify-between px-4 py-3">
        <span className="text-[12px] font-semibold uppercase tracking-wide text-muted">
          Traces ({tracers.length})
        </span>
        <button
          onClick={onToggle}
          className="rounded p-1 text-muted hover:bg-surface-2 hover:text-fg"
          aria-label="Collapse traces"
          title="Collapse"
        >
          <PanelLeftClose className="h-4 w-4" />
        </button>
      </div>
      {loading && (
        <div className="space-y-2 px-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-14 animate-pulse rounded-md bg-surface-2" />
          ))}
        </div>
      )}
      <ul className="space-y-1 px-2 pb-4">
        {tracers.map((t, n) => {
          const active = t.trace === selected;
          return (
            <li key={t.trace}>
              <button
                onClick={() => onSelect(t.trace)}
                className={`w-full rounded-md border px-3 py-2.5 text-left transition ${
                  active ? "border-primary bg-surface-2" : "border-transparent hover:bg-surface-2"
                }`}
              >
                <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">Trace {n + 1}</div>
                <div className="mt-0.5 text-[14px] font-semibold leading-snug">{t.title}</div>
                <div className="mt-1 text-[12.5px] leading-snug text-muted">{t.summary}</div>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  <span className="rounded bg-surface px-1.5 py-0.5 font-mono text-[11px] text-muted">
                    {t.patient_id.slice(0, 8)}
                  </span>
                  {t.chips.map((c) => (
                    <span key={c} className="rounded bg-primary/10 px-1.5 py-0.5 text-[11px] text-primary">{c}</span>
                  ))}
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
