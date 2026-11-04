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
  onSelect: (pid: string) => void;
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
          aria-label="Show patient list"
          title="Show patient list"
        >
          <Users className="h-[18px] w-[18px]" />
        </button>
        <div className="text-[10px] font-semibold uppercase tracking-wider text-muted [writing-mode:vertical-rl]">
          {tracers.length} patients
        </div>
      </aside>
    );
  }
  return (
    <aside className="w-72 shrink-0 overflow-y-auto border-r border-border bg-surface">
      <div className="flex items-center justify-between px-4 py-3">
        <span className="text-[12px] font-semibold uppercase tracking-wide text-muted">
          Hero patients ({tracers.length})
        </span>
        <button
          onClick={onToggle}
          className="rounded p-1 text-muted hover:bg-surface-2 hover:text-fg"
          aria-label="Collapse patient list"
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
        {tracers.map((t) => {
          const gap = t.status === "NOT_MET";
          const active = t.patient_id === selected;
          return (
            <li key={t.patient_id}>
              <button
                onClick={() => onSelect(t.patient_id)}
                className={`w-full rounded-md border px-3 py-2 text-left transition ${
                  active ? "border-primary bg-surface-2" : "border-transparent hover:bg-surface-2"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[12px] text-muted">{t.patient_id.slice(0, 8)}</span>
                  <span
                    className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                      gap ? "bg-destructive/15 text-destructive" : "bg-success/15 text-success"
                    }`}
                  >
                    {t.status}
                  </span>
                </div>
                <div className="mt-1 flex items-center gap-1.5 text-[13px]">
                  <span className="font-mono font-semibold text-primary">{t.dx_code}</span>
                  <span className="truncate text-muted">{t.dx_desc}</span>
                </div>
                <div className="text-[11px] text-muted">{t.clinic_id} · age {t.age}</div>
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
