import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

// "Simple mode": a pared-down view for presenting. Three questions, three retrieval approaches
// (Genie Ontology, RAG, Ontobricks graph) and two hero patients (one MET, one NOT_MET).
// Persisted in localStorage; `?simple=1` / `?simple=0` in the URL sets it too (handy for a demo link).
export const SIMPLE_QIDS = ["onto_ked_definition", "onto_poor_control_denominator", "graph_statin_contra_cohort"];
export const SIMPLE_APPROACHES = ["genie_ontology", "rag", "graph"];

type Settings = { simple: boolean; setSimple: (v: boolean) => void };
const Ctx = createContext<Settings>({ simple: false, setSimple: () => void 0 });
const KEY = "care.simpleMode";

function initial(): boolean {
  const q = new URLSearchParams(window.location.search).get("simple");
  if (q === "1" || q === "0") return q === "1";
  return window.localStorage.getItem(KEY) === "1";
}

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [simple, setSimple] = useState(initial);
  useEffect(() => {
    window.localStorage.setItem(KEY, simple ? "1" : "0");
  }, [simple]);
  return <Ctx.Provider value={{ simple, setSimple }}>{children}</Ctx.Provider>;
}

export const useSettings = () => useContext(Ctx);
