import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { ls, type Overview } from "../../lsApi";

// Clinical Study lab state shared by its tabs: the active study + rule version (always visible in the strip) and
// a "open this participant" hand-off between tabs. Lives inside the demo-keyed tree, so a demo switch resets it.
type Ctx = {
  study: string; setStudy: (s: string) => void;
  ruleVersion: string; setRuleVersion: (r: string) => void;
  overview: Overview | null; overviewError: string | null;
  focus: { usubjid: string; ruleVersion?: string } | null;
  openParticipant: (usubjid: string, ruleVersion?: string) => void;
  tab: string; setTab: (t: string) => void;
};
const LsCtx = createContext<Ctx | null>(null);

export const VERSIONS: Record<string, string[]> = { "CSL-A": ["EP-A-WT24.R1", "EP-A-WT24.R2"], "CSL-B": ["EP-B-WT24.R1"] };

export function LsProvider({ children, tab, setTab }: { children: ReactNode; tab: string; setTab: (t: string) => void }) {
  const [study, setStudyState] = useState("CSL-A");
  const [ruleVersion, setRuleVersion] = useState("EP-A-WT24.R2");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [overviewError, setOverviewError] = useState<string | null>(null);
  const [focus, setFocus] = useState<Ctx["focus"]>(null);
  useEffect(() => {
    ls.overview().then(setOverview).catch((e) => setOverviewError(String(e)));
  }, []);
  const setStudy = (s: string) => {
    setStudyState(s);
    setRuleVersion(VERSIONS[s][VERSIONS[s].length - 1]);
  };
  const openParticipant = (usubjid: string, rv?: string) => {
    const s = usubjid.startsWith("CSL-B") ? "CSL-B" : "CSL-A";
    if (s !== study) setStudy(s);
    if (rv) setRuleVersion(rv);
    setFocus({ usubjid, ruleVersion: rv });
    setTab("ls_participant");
  };
  return (
    <LsCtx.Provider value={{ study, setStudy, ruleVersion, setRuleVersion, overview, overviewError, focus, openParticipant, tab, setTab }}>
      {children}
    </LsCtx.Provider>
  );
}

export function useLs(): Ctx {
  const c = useContext(LsCtx);
  if (!c) throw new Error("useLs outside LsProvider");
  return c;
}
