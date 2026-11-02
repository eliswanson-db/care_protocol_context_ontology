import { ChevronDown, Circle, Clock } from "lucide-react";
import { useState } from "react";
import type { Stage } from "../api";

function DataView({ data }: { data: unknown }) {
  if (data === null || data === undefined) return <span className="text-muted">—</span>;
  const rows = Array.isArray(data) ? data : [data];
  if (rows.length === 0) return <span className="text-muted">no rows</span>;
  const keys = Object.keys(rows[0] as Record<string, unknown>);
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full text-left text-xs">
        <thead className="bg-surface-2 text-muted">
          <tr>
            {keys.map((k) => (
              <th key={k} className="px-2 py-1 font-medium">{k}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-border">
              {keys.map((k) => {
                const v = (r as Record<string, unknown>)[k];
                return (
                  <td key={k} className="px-2 py-1 font-mono">
                    {v === null || v === undefined ? <span className="text-muted">null</span> : String(v)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const STATUS_STYLE: Record<Stage["status"], { ring: string; chip: string; label: string }> = {
  live: { ring: "border-primary/50", chip: "bg-primary/15 text-primary", label: "live" },
  page: { ring: "border-primary/50", chip: "bg-primary/15 text-primary", label: "ontology" },
  wired_next: { ring: "border-border border-dashed", chip: "bg-surface-2 text-muted", label: "wired next" },
};

export function StageCard({ stage, index, last }: { stage: Stage; index: number; last: boolean }) {
  const dim = stage.status === "wired_next";
  const [open, setOpen] = useState(stage.status !== "wired_next");
  const s = STATUS_STYLE[stage.status];
  const hasData = stage.data !== null && stage.data !== undefined &&
    (!Array.isArray(stage.data) || stage.data.length > 0);

  return (
    <div className="relative pl-8">
      {!last && <div className="absolute left-[11px] top-7 h-full w-px bg-border" />}
      <div className="absolute left-0 top-3">
        {dim ? <Clock className="h-[22px] w-[22px] text-muted" /> : <Circle className="h-[22px] w-[22px] fill-primary/20 text-primary" />}
      </div>
      <div className={`mb-3 rounded-lg border bg-surface ${s.ring} ${dim ? "opacity-70" : ""}`}>
        <button onClick={() => setOpen((o) => !o)} className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-semibold text-muted">{String(index + 1).padStart(2, "0")}</span>
              <span className="font-semibold">{stage.title}</span>
              <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${s.chip}`}>{s.label}</span>
            </div>
            <div className="mt-0.5 text-xs text-primary">{stage.semantic_concept}</div>
          </div>
          <ChevronDown className={`mt-1 h-4 w-4 shrink-0 text-muted transition ${open ? "rotate-180" : ""}`} />
        </button>
        {open && (
          <div className="space-y-2 border-t border-border px-4 py-3">
            <p className="text-xs text-muted">{stage.note}</p>
            {stage.status === "wired_next" ? (
              <div className="rounded-md border border-dashed border-border bg-surface-2 px-3 py-2 text-xs text-muted">
                Not yet plumbed into the app — this hop exists in the build (see roadmap) and renders here next.
              </div>
            ) : hasData ? (
              <DataView data={stage.data} />
            ) : (
              <div className="rounded-md border border-border bg-surface-2 px-3 py-2 text-xs text-muted">
                No data at this layer for this patient.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
