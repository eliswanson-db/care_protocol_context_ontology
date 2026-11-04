export interface Meta {
  arm: string;
  catalog: string;
  measurement_year: number;
  context_release: string;
  synthetic: boolean;
  disclaimer: string;
}

export interface Tracer {
  patient_id: string;
  status: string;
  gap_reason: string | null;
  clinic_id: string;
  age: string;
  dx_code: string;
  dx_desc: string;
}

export interface StageSection {
  label: string;
  kind: "quote" | "kv" | "table" | "chain" | "triples" | "code" | "markdown" | "chips" | "path";
  text?: string;
  data?: Record<string, unknown>;
  rows?: Record<string, unknown>[];
  nodes?: { code: string; name: string; depth: number | string }[];
  items?: string[];
  steps?: { node: string; name: string; edge: string }[];
  empty?: string;
}
export interface StageDetail {
  key: string;
  title: string;
  patient_id: string;
  what: string;
  takeaway: string;
  source: string | null;
  sections: StageSection[];
  queries: { label: string; sql: string }[];
  warnings: string[];
  latency_s: number;
}

export interface Stage {
  key: string;
  title: string;
  semantic_concept: string;
  status: "live" | "page" | "doc" | "wired_next";
  data: unknown;
  note: string;
}

export interface Claim {
  id: string;
  before: string;
  chip: string;
  suffix?: string;
  kind: "verdict" | "evidence" | "code" | "subsumption" | "rate" | "definition";
  stage_path: string[];
  modes: string[];
}

export interface Answer {
  question: string;
  claims: Claim[];
}

export interface Journey {
  patient_id: string;
  measurement_year: number;
  stages: Stage[];
  answer: Answer;
}

export interface GenieCitation {
  kind: string;
  detail: string;
}

export interface GenieResult {
  patient_id: string;
  question: string;
  answer: string;
  generated_sql: string | null;
  tool_names: string[];
  ontology_used: boolean;
  citations: GenieCitation[];
  arm: string;
  surface: string;
  ran_as: string;
  latency_s: number;
}

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json() as Promise<T>;
}

export interface RagPassage {
  document_id: string;
  title: string;
  section_path: string;
  page_start: number | null;
  source: string;
  measurement_year: number | null;
  content: string;
  score: number | null;
}

export interface RagResult {
  patient_id: string;
  question: string;
  mode: string;
  semantic_pending: boolean;
  search_ext: boolean;
  embedded_chunks: number;
  ran_as: string;
  results: RagPassage[];
  latency_s: number;
}

export interface RetrievalProvenance {
  kind: string;
  detail: string;
}
export interface RetrievalLens {
  id: string;
  label: string;
  resolves_at: string;
  question: string;
  answer_rows: Record<string, unknown>[];
  provenance: RetrievalProvenance[];
  good_at: string;
  blind_to: string;
  latency_s: number;
}
export interface LiveLens {
  id: string;
  label: string;
  deferred: true;
  endpoint: string;
  resolves_at: string;
  question: string;
  good_at: string;
  blind_to: string;
}
export interface RetrievalResult {
  patient_id: string;
  measurement_year: number;
  eligible_measures: string[];
  deterministic_lenses: RetrievalLens[];
  live_lenses: LiveLens[];
}

export interface OntTriple {
  subject: string;
  predicate: string;
  object: string;
}
export interface OntobricksResult {
  patient_id: string;
  source: string;
  table: string;
  patient_triples: OntTriple[];
  care_triples: OntTriple[];
  latency_s: number;
}
export interface OntobricksCareEdges {
  source: string;
  table: string;
  triples: OntTriple[];
  latency_s: number;
}

export interface CapArm {
  id: string;
  label: string;
}
export interface CapQuestion {
  id: string;
  question: string;
  gold: string;
  min_approach: string;
  note: string;
  verdicts: Record<string, string>;
}
export interface CapClass {
  class_num: string;
  class_name: string;
  questions: CapQuestion[];
}
export interface CapRollup {
  arm: string;
  label: string;
  reached: number;
  diverged: number;
  not_reached: number;
  not_applicable: number;
  pending: number;
  applicable: number;
  total: number;
}
export interface CapabilityMap {
  arms: CapArm[];
  classes: CapClass[];
  rollup: CapRollup[];
  a1_on_source: string | null;
}

export interface A1ArmSignals {
  snapshot: string;
  n: number;
  reached_auto: number;
  snippet_search_fired: number;
  ontology_used: number;
  by_id: Record<string, { answer_ok: boolean | null; ontology_used: boolean; tool_names: string[]; latency_s: number; answer: string }>;
}
export interface A1Runs {
  off: A1ArmSignals | null;
  on: A1ArmSignals | null;
  caveat: string;
}

export interface DriftRate { clinic_id: string; rate: string; triggers: string }
export interface DriftFinding {
  clinic_id: string; severity: string; month: string;
  trailing_rate: string; baseline: string; delta: string; baseline_n: string;
  censored: boolean; narrative: string;
}
export interface DriftTraj { month: string; triggers: string; rate: string }
export interface DriftTransition { clinic_id: string; change_type: string; transition_date: string; recovery_days: string; narrative: string }
export interface DriftCaseMix { clinic_id: string; complication_share: string; patients: string }
export interface Drift {
  measurement_year: number;
  annual_ranking: DriftRate[];
  annual_worst: DriftRate | null;
  findings: DriftFinding[];
  worst: DriftFinding | null;
  worst_clinic: string | null;
  worst_annual_rank: number | null;
  trajectory: DriftTraj[];
  transition: DriftTransition | null;
  casemix: DriftCaseMix[];
}

export interface OntNode { id: string; label: string; kind: string; degree: number }
export interface OntEdge { subject: string; predicate: string; object: string; value: string | null; source: string }
export interface OntologyGraph { nodes: OntNode[]; edges: OntEdge[]; predicates: string[] }

export const api = {
  meta: () => get<Meta>("/api/meta"),
  tracers: () => get<{ measurement_year: number; tracers: Tracer[] }>("/api/tracers"),
  journey: (pid: string) => get<Journey>(`/api/patient/${pid}/journey`),
  stage: (pid: string, key: string) => get<StageDetail>(`/api/patient/${pid}/stage/${key}`),
  genie: (pid: string) => get<GenieResult>(`/api/patient/${pid}/genie`),
  rag: (pid: string) => get<RagResult>(`/api/patient/${pid}/rag`),
  retrieval: (pid: string) => get<RetrievalResult>(`/api/patient/${pid}/retrieval`),
  ontobricks: (pid: string) => get<OntobricksResult>(`/api/patient/${pid}/ontobricks`),
  ontobricksCareEdges: () => get<OntobricksCareEdges>("/api/ontobricks/care_edges"),
  capabilityMap: () => get<CapabilityMap>("/api/benchmark/capability_map"),
  a1Runs: () => get<A1Runs>("/api/benchmark/a1_runs"),
  drift: () => get<Drift>("/api/drift"),
  ontology: () => get<OntologyGraph>("/api/ontology/graph"),
};
