import { get } from "./api";

// Clinical Study lab API (all routes are bound server-side to demo life_sciences_clinical).
export type Row = Record<string, any>;
export interface Stamped { demo_id: string; execution_run_id: string }

export interface Candidate {
  obs_id: string; source_record_id: string; vsseq: string; visit: string; vsdtc: string; study_day: string | null;
  weight_kg: string | null; role: string; decision: string; reason: string; days_from_target: string | null;
  orres: string | null; raw_unit: string | null; ct_unit: string | null;
}
export interface Citation {
  rule_version: string; protocol_version: string; sap_version: string; document: string; section: string;
  review_state: string; approved_by: string;
}
export interface Trace {
  usubjid: string; endpoint_version: string; result_status: string; exclusion_reason: string | null;
  reference_date: string | null; target_date: string | null; baseline_kg: string | null; followup_kg: string | null;
  pct_change: string | null; calculation: string | null; candidates: Candidate[]; execution_run_id: string;
  citation: Citation; error?: string;
}
export interface Criterion {
  protocol_version: string; eligibility_rule_id: string; criterion_id: string; criterion_type: string;
  outcome: string; evidence: string; path_labels: string; detail: string;
}
export interface Participant extends Stamped {
  usubjid: string; rule_version: string; rule_versions: string[]; demographics: Row | null;
  tracer: { tracer_id: string; title: string } | null; trace: Trace;
  by_version: Record<string, { result_status: string; pct_change: string | null; followup: string | null; exclusion_reason: string | null }>;
  raw_source: Row[];
  rule: { rule: Row; citation: Citation; section_text: { heading: string; text: string } | null; assertions: Row[] };
  eligibility: { usubjid: string; criteria: Criterion[]; population: Row | null };
  provenance: { subject: string; predicate: string; object: string }[];
}
export interface Overview extends Stamped {
  studies: Row[]; study_versions: Row[]; rule_versions: Row[]; endpoint_summary: Row[]; populations: Row[];
  data_quality: Row[]; verification: Row | null;
}
export interface Summary { study_id: string; population: string; by_arm: Row[]; citation: Citation }
export interface Amendment extends Stamped {
  impact: { comparison: string; counts: Record<string, number>; top_sites_recovered: Row[]; affected: Row[]; citations: Citation[]; note: string };
  definition_diff: { a: string; b: string; equivalent: boolean; differences: Row[]; same: string[] };
  summary_r1: Summary; summary_r2: Summary; by_site: Row[]; named_examples: Row[];
}
export interface ConceptNode extends Stamped {
  concept: Row; outgoing: Row[]; incoming: Row[]; ancestors: Row[]; classes: Row[]; mapping: Row | null;
  custom_namespace: Row[];
}
export interface ArenaQ { qid: string; category: string; question: string }
export interface ArenaRun extends Stamped {
  qid: string; question: string; category: string;
  lenses: Record<string, any>;
}
export interface ReadinessComp { id: string; label: string; state: string; detail: string; checked_in_s?: number }
export interface Readiness { demo_id: string; display_name: string; checked_at: string; components: ReadinessComp[]; summary: Record<string, number> }

export interface GenieOneRun {
  qid: string;
  status: "running" | "done" | "error";
  error?: string;
  surface?: string;
  answer?: string;
  latency_s?: number;
  pages?: { name: string; relevance: number | null; demo: string }[];
  pages_by_demo?: Record<string, number>;
  snippets_by_demo?: Record<string, number>;
  top_snippets?: { headline: string; type: string; demo: string }[];
  pages_read?: string[];
  agents?: string[];
  tool_order?: string[];
}

export const ls = {
  overview: () => get<Overview>("/api/ls/overview"),
  tracers: () => get<Stamped & { tracers: Row[] }>("/api/ls/tracers"),
  search: (q: string) => get<Stamped & { participants: Row[] }>(`/api/ls/participants?q=${encodeURIComponent(q)}`),
  participant: (u: string, rv?: string) =>
    get<Participant>(`/api/ls/participant/${encodeURIComponent(u)}${rv ? `?rule_version=${encodeURIComponent(rv)}` : ""}`),
  amendment: (site?: string) => get<Amendment>(`/api/ls/amendment${site ? `?site=${encodeURIComponent(site)}` : ""}`),
  conceptSearch: (q: string) => get<Stamped & { results: Row[] }>(`/api/ls/concepts/search?q=${encodeURIComponent(q)}`),
  concept: (id: string) => get<ConceptNode>(`/api/ls/concepts/node?id=${encodeURIComponent(id)}`),
  rules: () => get<Stamped & { rule_versions: Row[]; assertions: Row[]; documents: Row[] }>("/api/ls/rules"),
  arenaQuestions: () => get<Stamped & { questions: ArenaQ[] }>("/api/ls/arena/questions"),
  arenaRun: (qid: string) => get<ArenaRun>(`/api/ls/arena/run?qid=${qid}`),
  arenaGenie: (qid: string) => get<Stamped & GenieOneRun>(`/api/ls/arena/genie?qid=${qid}`),
};
export const readinessApi = {
  all: (refresh = false) => get<{ demos: Readiness[] }>(`/api/readiness?all_demos=true${refresh ? "&refresh=true" : ""}`),
};
