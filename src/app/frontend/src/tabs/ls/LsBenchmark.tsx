import { BarChart3 } from "lucide-react";
import { Card, Chip } from "./ui";

const CATEGORIES = [
  "Structured numerical result", "Protocol definition", "Standards mapping", "Participant-level explanation",
  "Amendment impact", "Cross-study definition comparison", "Missing information", "Ambiguous version",
  "Cross-demo contamination attempt", "Unapproved-rule conflict",
];
const DIMENSIONS = [
  "retrieval_relevance", "numerical_correctness", "study_scope_correctness", "version_correctness",
  "citation_correctness", "provenance_completeness", "explanation_fidelity", "abstention_correctness",
  "cross_demo_isolation", "latency",
];

export function LsBenchmark() {
  return (
    <main className="flex-1 space-y-3 overflow-y-auto p-4">
      <div className="flex items-center gap-2"><BarChart3 className="h-5 w-5 text-primary" /><h2 className="text-lg font-bold">Benchmark — Clinical Study lab</h2>
        <Chip tone="info">not run yet</Chip></div>
      <div className="rounded-md border border-primary/30 bg-primary/5 px-3 py-2 text-[12.5px]">
        No scores are shown until the benchmark has run against a hand-verified answer key (Phase 7). The graph and
        RAG lenses also wait on the Ontobricks publish and the Lakebase load; see Readiness. A capability map, not a
        leaderboard: for each question category, which approach is sufficient, adds value, or is necessary.
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        <Card title="Question categories (prompt §15)">
          <ol className="list-decimal space-y-0.5 pl-5 text-[12.5px]">{CATEGORIES.map((c) => <li key={c}>{c}</li>)}</ol>
        </Card>
        <Card title="Scored separately">
          <div className="flex flex-wrap gap-1">{DIMENSIONS.map((d) => <Chip key={d}>{d}</Chip>)}</div>
          <div className="mt-2 text-[12px] text-muted">Structured facts are checked deterministically against the gold tables; an LLM judge is used only where a fact can't be checked mechanically.</div>
        </Card>
      </div>
    </main>
  );
}
