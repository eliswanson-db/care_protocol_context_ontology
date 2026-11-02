import { BarChart3, GitCompare, Network, Route } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Meta } from "./api";
import { Header } from "./components/Header";
import { BenchmarkScorecard } from "./tabs/BenchmarkScorecard";
import { TracerJourney } from "./tabs/TracerJourney";

const TABS = [
  { key: "tracer", label: "Tracer Journey", icon: Route, enabled: true },
  { key: "scorecard", label: "Benchmark Scorecard", icon: BarChart3, enabled: true },
  { key: "arena", label: "Retrieval Arena", icon: GitCompare, enabled: false },
  { key: "ontology", label: "Ontology Explorer", icon: Network, enabled: false },
];

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [tab, setTab] = useState("tracer");

  useEffect(() => {
    api.meta().then(setMeta).catch(() => void 0);
  }, []);

  return (
    <div className="flex h-screen flex-col">
      <Header meta={meta} />
      <nav className="flex items-center gap-1 border-b border-border bg-surface px-4">
        {TABS.map((t) => {
          const Icon = t.icon;
          const active = t.key === tab;
          return (
            <button
              key={t.key}
              disabled={!t.enabled}
              onClick={() => t.enabled && setTab(t.key)}
              className={`flex items-center gap-1.5 border-b-2 px-3 py-2.5 text-sm transition ${
                active
                  ? "border-primary text-fg"
                  : t.enabled
                  ? "border-transparent text-muted hover:text-fg"
                  : "cursor-not-allowed border-transparent text-muted/40"
              }`}
            >
              <Icon className="h-4 w-4" />
              {t.label}
              {!t.enabled && <span className="ml-1 text-[10px] uppercase">soon</span>}
            </button>
          );
        })}
      </nav>
      {tab === "tracer" && <TracerJourney />}
      {tab === "scorecard" && <BenchmarkScorecard />}
      {meta && (
        <footer className="border-t border-border bg-surface px-5 py-1.5 text-[11px] text-muted">
          {meta.disclaimer} · catalog {meta.catalog} · context {meta.context_release}
        </footer>
      )}
    </div>
  );
}
