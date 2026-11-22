import { BarChart3, FlaskConical, GitCompare, Network, Route, TrendingDown, User } from "lucide-react";
import { useEffect, useState, type ReactElement } from "react";
import { api, type Meta } from "./api";
import { Header } from "./components/Header";
import { useDemo, type DemoId } from "./demo";
import { Benchmark } from "./tabs/Benchmark";
import { DriftLab } from "./tabs/DriftLab";
import { OntologyExplorer } from "./tabs/OntologyExplorer";
import { TracerJourney } from "./tabs/TracerJourney";
import { AmendmentLab } from "./tabs/ls/AmendmentLab";
import { LsArena } from "./tabs/ls/LsArena";
import { LsBenchmark } from "./tabs/ls/LsBenchmark";
import { LsProvider } from "./tabs/ls/LsContext";
import { ParticipantEvidence } from "./tabs/ls/ParticipantEvidence";
import { StandardsExplorer } from "./tabs/ls/StandardsExplorer";
import { StudyStrip } from "./tabs/ls/StudyStrip";

type Tab = { key: string; label: string; icon: typeof Route; render: () => ReactElement };

// Same navigation pattern for both demos, terminology adapted (prompt §14).
const TABS: Record<DemoId, Tab[]> = {
  healthcare_hedis: [
    // Trace + Benchmark lead (docs/CONTEXT_LAB_PLAN.md step 7). The previous Retrieval Arena and Benchmark Scorecard
    // (tabs/RetrievalArena.tsx, tabs/BenchmarkScorecard.tsx) showed the retired question set; kept, not in the nav.
    { key: "tracer", label: "Trace", icon: Route, render: () => <TracerJourney /> },
    { key: "benchmark", label: "Benchmark", icon: BarChart3, render: () => <Benchmark /> },
    { key: "drift", label: "Drift Lab", icon: TrendingDown, render: () => <DriftLab /> },
    { key: "ontology", label: "Ontology Explorer", icon: Network, render: () => <OntologyExplorer /> },
  ],
  life_sciences_clinical: [
    { key: "ls_participant", label: "Participant Evidence", icon: User, render: () => <ParticipantEvidence /> },
    { key: "ls_arena", label: "Retrieval Arena", icon: GitCompare, render: () => <LsArena /> },
    { key: "ls_benchmark", label: "Benchmark", icon: BarChart3, render: () => <LsBenchmark /> },
    { key: "ls_amendment", label: "Amendment Lab", icon: FlaskConical, render: () => <AmendmentLab /> },
    { key: "ls_standards", label: "Standards & Ontology Explorer", icon: Network, render: () => <StandardsExplorer /> },
  ],
};

function Nav({ tabs, tab, setTab }: { tabs: Tab[]; tab: string; setTab: (k: string) => void }) {
  return (
    <nav className="flex items-center gap-1 border-b border-border bg-surface px-4">
      {tabs.map((t) => {
        const Icon = t.icon;
        const active = t.key === tab;
        return (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`flex items-center gap-1.5 border-b-2 px-3 py-2.5 text-sm transition ${active ? "border-primary text-fg" : "border-transparent text-muted hover:text-fg"}`}>
            <Icon className="h-4 w-4" />
            {t.label}
          </button>
        );
      })}
    </nav>
  );
}

// Everything below is remounted on a demo switch (key={demo}): tab, selection, traces, caches all reset.
function DemoContent({ demo, meta }: { demo: DemoId; meta: Meta | null }) {
  const tabs = TABS[demo];
  const [tab, setTab] = useState(tabs[0].key);
  const current = tabs.find((t) => t.key === tab) ?? tabs[0];
  const body = (
    <>
      <Nav tabs={tabs} tab={current.key} setTab={setTab} />
      {demo === "life_sciences_clinical" && <StudyStrip />}
      <div className="flex min-h-0 flex-1 flex-col">{current.render()}</div>
      {meta && (
        <footer className="border-t border-border bg-surface px-5 py-1.5 text-[11px] text-muted">
          {meta.disclaimer} · catalog {meta.catalog} · context {meta.context_release}
        </footer>
      )}
    </>
  );
  return demo === "life_sciences_clinical" ? <LsProvider tab={current.key} setTab={setTab}>{body}</LsProvider> : body;
}

export default function App() {
  const { demo } = useDemo();
  const [meta, setMeta] = useState<Meta | null>(null);
  useEffect(() => {
    setMeta(null);
    api.meta().then((m) => m.demo_id === demo && setMeta(m)).catch(() => void 0);
  }, [demo]);
  return (
    <div className="flex h-screen flex-col">
      <Header meta={meta} />
      <DemoContent key={demo} demo={demo} meta={meta} />
    </div>
  );
}
