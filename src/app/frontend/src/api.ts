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

export const api = {
  meta: () => get<Meta>("/api/meta"),
  tracers: () => get<{ measurement_year: number; tracers: Tracer[] }>("/api/tracers"),
  journey: (pid: string) => get<Journey>(`/api/patient/${pid}/journey`),
  genie: (pid: string) => get<GenieResult>(`/api/patient/${pid}/genie`),
  rag: (pid: string) => get<RagResult>(`/api/patient/${pid}/rag`),
};
