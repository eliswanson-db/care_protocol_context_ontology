import {
  BookOpen,
  ChevronRight,
  Database,
  FileText,
  Gauge,
  Layers,
  Network,
  Share2,
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
  ontobricks: Share2,
};

// Short, human labels for the card face. Full title + description live in the click-in detail.
const SHORT: Record<string, string> = {
  protocol: "Care protocol",
  bronze: "Raw EHR code",
  silver: "Conformed condition",
  closure: "ICD-10 subsumption",
  cohort: "Cohort denominator",
  gold: "Patient evidence",
  metric: "Governed metric view",
  page: "Genie Ontology",
  ontobricks: "Ontobricks graph",
};

// One short line of what happens at this hop — a little context without re-stating the click-in detail.
const DETAIL: Record<string, string> = {
  protocol: "defines who's eligible + the thresholds",
  bronze: "raw rows as landed (SNOMED, text values)",
  silver: "mapped to ICD-10, values typed",
  closure: "subcode rolls up to its value-set root",
  cohort: "membership earned by subsumption, not a list",
  gold: "per-patient evidence — facts, no verdict",
  metric: "certified rule → MET / NOT_MET, live",
  page: "the Page + metadata Genie grounds on",
  ontobricks: "live triples + subClassOf* closure",
};

// Left-to-right PHASES; stages inside a phase stack vertically. One accent color per phase.
const PHASES: { key: string; label: string; color: string; stages: string[] }[] = [
  { key: "source", label: "Source", color: "var(--tier-protocol)", stages: ["protocol"] },
  { key: "bronze", label: "Bronze", color: "var(--tier-bronze)", stages: ["bronze"] },
  { key: "silver", label: "Silver", color: "var(--tier-silver)", stages: ["silver", "closure", "cohort"] },
  { key: "gold", label: "Gold · serving", color: "var(--tier-gold)", stages: ["gold", "metric"] },
  { key: "ontology", label: "Ontology", color: "var(--tier-page)", stages: ["page", "ontobricks"] },
];

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
      return d?.evidence_datetime ? `A1c ${d.evidence_value}%` : "no A1c in MY";
    case "metric": {
      const r = d?.rate;
      const n = typeof r === "number" ? r : Number(r);
      const pct = Number.isFinite(n) ? `${n <= 1 ? Math.round(n * 100) : Math.round(n)}%` : "—";
      return `${(d?.patient_status as string) ?? "—"} · clinic ${pct}`;
    }
    case "page":
      return "GSD Page";
    case "ontobricks":
      return "live graph";
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
  const byKey = new Map(stages.map((s) => [s.key, s]));

  return (
    <div className="flex items-stretch gap-1">
      {PHASES.map((ph, pi) => {
        const c = ph.color;
        const phaseStages = ph.stages.map((k) => byKey.get(k)).filter(Boolean) as Stage[];
        return (
          <div key={ph.key} className="flex min-w-0 flex-1 items-stretch">
            <div className="flex min-w-0 flex-1 flex-col">
              <div className="mb-1.5 text-[11px] font-bold uppercase tracking-wider" style={{ color: c }}>
                {ph.label}
              </div>
              <div className="flex flex-col gap-1.5">
                {phaseStages.map((st) => {
                  const Icon = ICONS[st.key] ?? FileText;
                  const inPath = activePath.has(st.key);
                  const dim = hasPath && !inPath;
                  const selected = selectedKey === st.key;
                  const val = summary(st);
                  // Status-bearing chips (gold measure verdict) use reserved status color, not the tier accent.
                  const chipC =
                    st.key === "metric" && /^(MET|NOT_MET)/.test(val) ? (val.startsWith("MET") ? "var(--success)" : "var(--destructive)") : c;
                  return (
                    <button
                      key={st.key}
                      onClick={() => onSelect(st.key)}
                      style={{ borderLeftColor: dim ? undefined : c }}
                      className={[
                        "flex flex-col rounded-lg border border-l-[3px] bg-surface px-3 py-2.5 text-left transition",
                        selected ? "border-primary ring-2 ring-primary/40" : "border-border",
                        dim ? "opacity-30" : "hover:border-primary/60",
                      ].join(" ")}
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md"
                          style={{ background: `color-mix(in srgb, ${c} 22%, transparent)`, color: c }}
                        >
                          <Icon className="h-4 w-4" />
                        </span>
                        <span className="min-w-0 text-[13.5px] font-semibold leading-tight">{SHORT[st.key] ?? st.title}</span>
                      </div>
                      <div className="mt-1.5 text-[11px] leading-snug text-muted">{DETAIL[st.key] ?? st.semantic_concept}</div>
                      <div
                        className="mt-2 truncate rounded px-2 py-1 font-mono text-[12.5px] font-semibold"
                        style={{ background: `color-mix(in srgb, ${chipC} 14%, transparent)`, color: chipC }}
                        title={val}
                      >
                        {val}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
            {pi < PHASES.length - 1 && (
              <div className="flex items-center px-0.5 text-muted">
                <ChevronRight className="h-5 w-5" />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
