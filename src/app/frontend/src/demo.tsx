import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

// The active demo (ADR-0023). It is sent on EVERY API request as X-Demo-Id (api.ts), the backend refuses a
// cross-demo request with 409, and App remounts the whole content tree on a switch, so no conversation,
// selected participant, trace, cache or filter survives into the other demo.
export type DemoId = "healthcare_hedis" | "life_sciences_clinical";
export const DEMOS: { id: DemoId; label: string; short: string }[] = [
  { id: "healthcare_hedis", label: "Healthcare — HEDIS Diabetes", short: "Healthcare" },
  { id: "life_sciences_clinical", label: "Life Sciences — Clinical Study Evidence", short: "Life Sciences" },
];
const KEY = "lab.demo";

let active: DemoId = initial();
export const getActiveDemo = () => active;

function initial(): DemoId {
  const q = new URLSearchParams(window.location.search).get("demo");
  const ids = DEMOS.map((d) => d.id) as string[];
  if (q && ids.includes(q)) return q as DemoId;
  const s = window.localStorage.getItem(KEY);
  return s && ids.includes(s) ? (s as DemoId) : "healthcare_hedis";
}

type Ctx = { demo: DemoId; setDemo: (d: DemoId) => void };
const DemoCtx = createContext<Ctx>({ demo: active, setDemo: () => void 0 });

export function DemoProvider({ children }: { children: ReactNode }) {
  const [demo, setState] = useState<DemoId>(active);
  const setDemo = useCallback((d: DemoId) => {
    active = d; // before the remount, so the first request of the new tree already carries the new demo
    setState(d);
  }, []);
  useEffect(() => {
    window.localStorage.setItem(KEY, demo);
    const u = new URL(window.location.href);
    u.searchParams.set("demo", demo);
    window.history.replaceState(null, "", u.toString());
  }, [demo]);
  return <DemoCtx.Provider value={{ demo, setDemo }}>{children}</DemoCtx.Provider>;
}

export const useDemo = () => useContext(DemoCtx);
