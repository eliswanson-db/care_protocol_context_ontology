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
  status: "live" | "page" | "wired_next";
  data: unknown;
  note: string;
}

export interface Journey {
  patient_id: string;
  measurement_year: number;
  stages: Stage[];
}

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json() as Promise<T>;
}

export const api = {
  meta: () => get<Meta>("/api/meta"),
  tracers: () => get<{ measurement_year: number; tracers: Tracer[] }>("/api/tracers"),
  journey: (pid: string) => get<Journey>(`/api/patient/${pid}/journey`),
};
