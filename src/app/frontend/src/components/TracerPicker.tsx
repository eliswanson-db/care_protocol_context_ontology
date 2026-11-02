import type { Tracer } from "../api";

export function TracerPicker({
  tracers,
  selected,
  onSelect,
  loading,
}: {
  tracers: Tracer[];
  selected: string | null;
  onSelect: (pid: string) => void;
  loading: boolean;
}) {
  return (
    <aside className="w-72 shrink-0 overflow-y-auto border-r border-border bg-surface">
      <div className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted">
        Hero patients ({tracers.length})
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
                  <span className="font-mono text-xs text-muted">{t.patient_id.slice(0, 8)}</span>
                  <span
                    className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                      gap ? "bg-destructive/15 text-destructive" : "bg-success/15 text-success"
                    }`}
                  >
                    {t.status}
                  </span>
                </div>
                <div className="mt-1 flex items-center gap-1.5 text-xs">
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
