import {
  BookOpen,
  ChevronRight,
  Database,
  FileText,
  Gauge,
  Layers,
  Network,
  Target,
  Users,
  type LucideIcon,
} from "lucide-react";
import type { Stage } from "../api";

const ICONS: Record<string, LucideIcon> = {
  protocol: FileText,
  bronze: Database,
  silver: Layers,
  closure: Network,
  cohort: Users,
  gold: Target,
  metric: Gauge,
  page: BookOpen,
};

function first(data: unknown): Record<string, unknown> | null {
  if (Array.isArray(data)) return (data[0] as Record<string, unknown>) ?? null;
  if (data && typeof data === "object") return data as Record<string, unknown>;
  return null;
}

/** One-line instance value for this patient at this hop — the datum, not the schema. */
function summary(stage: Stage): string {
  const d = first(stage.data);
  switch (stage.key) {
    case "protocol":
      return "GSD spec (PDF)";
    case "bronze":
    case "silver":
      return (d?.icd10_code as string) ?? "—";
    case "closure":
      return d ? `${d.descendant_code} ⊑ ${d.ancestor_code}` : "—";
    case "cohort":
      return d?.in_cohort ? "in denominator" : "excluded";
    case "gold":
      return (d?.status as string) ?? "—";
    case "metric": {
      const r = d?.rate;
      const n = typeof r === "number" ? r : Number(r);
      if (!Number.isFinite(n)) return "—";
      return `${n <= 1 ? Math.round(n * 100) : Math.round(n)}% rate`;
    }
    case "page":
      return "GSD Page";
    default:
      return "—";
  }
}

export function FlowDiagram({
  stages,
  activePath,
  selectedKey,
  onSelect,
}: {
  stages: Stage[];
  activePath: Set<string>;
  selectedKey: string | null;
  onSelect: (key: string) => void;
}) {
  const hasPath = activePath.size > 0;
  return (
    <div className="flex flex-wrap items-stretch gap-y-3">
      {stages.map((st, i) => {
        const Icon = ICONS[st.key] ?? FileText;
        const inPath = activePath.has(st.key);
        const dim = hasPath && !inPath;
        const selected = selectedKey === st.key;
        return (
          <div key={st.key} className="flex items-stretch">
            <button
              onClick={() => onSelect(st.key)}
              className={[
                "flex w-40 flex-col rounded-xl border bg-surface px-3 py-2.5 text-left transition",
                selected ? "border-primary ring-2 ring-primary/40" : inPath ? "border-primary/70" : "border-border",
                inPath ? "shadow-[0_0_0_3px] shadow-primary/10" : "",
                dim ? "opacity-35" : "hover:border-primary/60",
              ].join(" ")}
            >
              <div className="flex items-center justify-between">
                <span
                  className={`flex h-7 w-7 items-center justify-center rounded-lg ${
                    inPath || !hasPath ? "bg-primary/15 text-primary" : "bg-surface-2 text-muted"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                </span>
                <span className="text-[10px] font-semibold text-muted">
                  {String(i + 1).padStart(2, "0")}
                </span>
              </div>
              <div className="mt-2 text-xs font-semibold leading-tight">{st.title}</div>
              <div className="mt-1 text-[10px] leading-snug text-primary">{st.semantic_concept}</div>
              <div className="mt-2 truncate rounded bg-surface-2 px-1.5 py-1 font-mono text-[11px]" title={summary(st)}>
                {summary(st)}
              </div>
            </button>
            {i < stages.length - 1 && (
              <div className="flex items-center px-1 text-muted">
                <ChevronRight className={`h-4 w-4 ${dim ? "opacity-35" : ""}`} />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
