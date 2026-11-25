import { getActiveDemo } from "./demo";

export interface Meta {
  demo_id: string;
  display_name: string;
  arm: string;
  catalog: string;
  measurement_year?: number;
  context_release: string;
  synthetic: boolean;
  disclaimer: string;
}

// One of the three traces (server/traces.py): a piece of information + the hero patient it is followed through.
export interface Tracer {
  trace: string;
  title: string;
  summary: string;
  patient_id: string;
  chips: string[];
  question: string;
}

export interface StageSection {
  label: string;
  kind: "quote" | "kv" | "table" | "chain" | "triples" | "code" | "markdown" | "chips" | "path" | "doc";
  text?: string;
  data?: Record<string, unknown>;
  rows?: Record<string, unknown>[];
  nodes?: { code: string; name: string; depth: number | string }[];
  items?: string[];
  steps?: { node: string; name: string; edge: string }[];
  blocks?: { type: "h" | "p" | "table" | "rule"; text?: string; rows?: string[][]; highlight_rows?: number[]; highlight?: boolean }[];
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
  pending?: boolean;
}

export interface CtxDoc {
  page_content: string;
  metadata: Record<string, any>;
}
export interface Scored {
  tier: 1 | 2 | 3 | null;
  tier_runs?: number[];
  stable?: boolean;
  sufficient: boolean;
  query_correct?: boolean;
  sql?: string | null;
  sql_result?: string | null;
  sql_error?: string | null;
  skipped_search?: boolean;
  n_docs: number;
  context?: string;
  interface?: string;
  query?: { kind: "sql" | "tool"; sql?: string; tool?: string; args?: Record<string, unknown> } | null;
  facts?: { fact: string; in_context: Judged; in_result: Judged | null }[];
  reason?: string;
  retrieved?: string;
}
export interface Judged { ok: boolean; rationale: string }
export interface ArenaContext {
  qid: string;
  question: string;
  ontology: Record<string, { docs: CtxDoc[]; error?: string; queries: string[]; skipped_search?: boolean; host: string; identity: string;
    recorded_at: string; scored?: Scored; genie_one_answer?: string | null }>;
  graph: { docs: CtxDoc[]; latency_s: number; error?: string; graph_table: string; scored?: Scored };
  closed_book?: Scored;
  scored_all?: Record<string, Scored>;
  scored_meta?: { agent: string; judge: string; repeats?: number };
  genie_one: {
    snapshot?: string; pages_cited?: string[]; snippet_searches?: string[]; tables_queried?: string[];
    sql_queries?: number; tool_calls?: number; latency_s?: number; used_ontobricks_mcp?: boolean;
  };
}

export interface Stage {
  key: string;
  title: string;
  semantic_concept: string;
  status: "live" | "page" | "doc" | "wired_next";
  data: unknown;
  note: string;
  short?: string;   // card label for this trace
  detail?: string;  // one line on what this hop holds for this trace
  summary?: string; // the patient's datum at this hop
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
  trace: string;
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

// Every request carries the active demo; the backend refuses a cross-demo call (409), and a payload stamped with
// a different demo_id is refused here too, so a slow response can't paint the other demo's data.
export async function get<T>(url: string): Promise<T> {
  const demo = getActiveDemo();
  const r = await fetch(url, { headers: { "X-Demo-Id": demo } });
  if (!r.ok) {
    let detail = "";
    try {
      detail = (await r.json()).detail ?? "";
    } catch {
      /* not JSON */
    }
    throw new Error(`${r.status} ${r.statusText}${detail ? ": " + detail : ""}`);
  }
  const body = await r.json();
  if (body && typeof body === "object" && "demo_id" in body && body.demo_id !== demo)
    throw new Error(`refused a ${body.demo_id} payload while ${demo} is active`);
  return body as T;
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
  kind: "retrieval" | "end_to_end";
}
export interface CapQuestion {
  id: string;
  question: string;
  gold: string;
  min_approach: string;
  note: string;
  verdicts: Record<string, string>;
  why?: Record<string, string>;
  evidence?: Record<string, { context: string; sql?: string | null; tier_runs?: number[] | null; stable?: boolean | null }>;
}
export interface CapClass {
  class_num: string;
  class_name: string;
  questions: CapQuestion[];
}
export interface CapRollup {
  arm: string;
  label: string;
  tier1: number;
  tier2: number;
  tier3: number;
  answered: number;
  wrong: number;
  no_query: number;
  skipped: number;
  unstable: number;
  reached: number;
  diverged: number;
  not_reached: number;
  no_retrieval: number;
  kind: "retrieval" | "end_to_end";
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
  scored_by?: { judge?: string; agent?: string; repeats?: number } | null;
  floor?: { tier1: number; tier2: number; total: number };
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
  snippet_evidence?: {
    recorded_at?: string;
    [ws: string]: { identity: string; questions: number; searched: number; snippets: number; on_topic: number; pages: number } | string | undefined;
  };
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
  tracers: () => get<{ measurement_year: number; traces: Tracer[] }>("/api/tracers"),
  journey: (pid: string, trace: string) => get<Journey>(`/api/patient/${pid}/journey?trace=${trace}`),
  stage: (pid: string, key: string, trace: string) =>
    get<StageDetail>(`/api/patient/${pid}/stage/${key}?trace=${trace}`),
  lsTraces: () => get<{ traces: Tracer[] }>("/api/ls/traces"),
  lsJourney: (id: string, trace: string) => get<Journey>(`/api/ls/traces/${id}/journey?trace=${trace}`),
  lsStage: (id: string, key: string, trace: string) =>
    get<StageDetail>(`/api/ls/traces/${id}/stage/${key}?trace=${trace}`),
  genie: (pid: string) => get<GenieResult>(`/api/patient/${pid}/genie`),
  rag: (pid: string) => get<RagResult>(`/api/patient/${pid}/rag`),
  retrieval: (pid: string) => get<RetrievalResult>(`/api/patient/${pid}/retrieval`),
  ontobricks: (pid: string) => get<OntobricksResult>(`/api/patient/${pid}/ontobricks`),
  ontobricksCareEdges: () => get<OntobricksCareEdges>("/api/ontobricks/care_edges"),
  arenaContext: (qid: string) => get<ArenaContext>(`/api/arena/${qid}/context`),
  capabilityMap: () => get<CapabilityMap>("/api/benchmark/capability_map"),
  benchmarkV2: () => get<BenchmarkV2>("/api/benchmark/v2"),
  lsBenchmark: () => get<BenchmarkV2>("/api/ls/benchmark"),
  a1Runs: () => get<A1Runs>("/api/benchmark/a1_runs"),
  drift: () => get<Drift>("/api/drift"),
  ontology: () => get<OntologyGraph>("/api/ontology/graph"),
};

// Benchmark v2 (docs/benchmark/questions_v2.yaml + benchmark_v2.json): 8 locked questions x 5 retrieval approaches
// (one simple agent) + Genie One as the reasoning engine.
export interface V2Judgment { ok: boolean; verdict?: "stated" | "missing" | "contradicted"; quote?: string; rationale: string }
export interface V2Fact { fact: string; in_context?: V2Judgment; in_result?: V2Judgment | null }
export interface V2Cell {
  tier: number | null; tier_runs?: number[]; stable?: boolean; interface?: string; retrieved?: string;
  facts?: V2Fact[]; reason?: string; sql?: string | null; sql_result?: string | null; sql_error?: string | null;
  n_docs?: number; hand_verified?: boolean; prediction?: string; answer?: string; genie_sql?: string[];
  judge_tier?: number | null; override?: string; judge_outcome?: string | null;
  outcome?: "in_context" | "one_query" | "incomplete" | "wrong" | "query_failed" | "no_query" | "nothing" | null;
  declined_reason?: string | null; hand_note?: string | null;
}
export interface BenchmarkV2 {
  available: boolean;
  arms: { id: string; label: string; kind: "retrieval" | "end_to_end" }[];
  questions: { id: string; short?: string | null; question: string; answer_type: string; expected_facts: string[]; hero_rule?: string;
    run_as?: string; cells: Record<string, V2Cell> }[];
  meta: { agent: string; judge: string; repeats: number; mode: "test" | "final"; data_horizon: string; scoring?: string };
}
