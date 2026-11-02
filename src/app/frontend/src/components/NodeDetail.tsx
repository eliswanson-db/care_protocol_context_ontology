import { X } from "lucide-react";
import type { Stage } from "../api";
import { DataTable } from "./DataTable";

export function NodeDetail({ stage, onClose }: { stage: Stage; onClose: () => void }) {
  const hasData =
    stage.data !== null &&
    stage.data !== undefined &&
    (!Array.isArray(stage.data) || stage.data.length > 0);
  return (
    <div className="mt-3 rounded-xl border border-primary/40 bg-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold">{stage.title}</div>
          <div className="mt-0.5 text-xs text-primary">{stage.semantic_concept}</div>
        </div>
        <button onClick={onClose} className="rounded p-1 text-muted hover:text-fg" aria-label="Close detail">
          <X className="h-4 w-4" />
        </button>
      </div>
      <p className="mt-2 text-xs text-muted">{stage.note}</p>
      <div className="mt-3">
        {hasData ? (
          <DataTable data={stage.data} />
        ) : (
          <div className="rounded-md border border-border bg-surface-2 px-3 py-2 text-xs text-muted">
            No data at this layer for this patient.
          </div>
        )}
      </div>
    </div>
  );
}
