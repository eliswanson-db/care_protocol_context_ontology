import { ArrowRight, CornerDownRight } from "lucide-react";
import type { ReactNode } from "react";

// What the Retrieval Arena and the Benchmark Scorecard evaluate, and how, in one picture.
// Kept in sync with src/benchmark/retrieval_eval/run_retrieval_eval.py (run_cell + INTERFACE).

const INTERFACES: { approach: string; retrieves: string; query: string }[] = [
  { approach: "Metric view", retrieves: "definitions of the 3 most relevant metric views", query: "1 SQL query (MEASURE())" },
  { approach: "Closure tables", retrieves: "concept → subtree → patients under it", query: "1 closure-tool call" },
  { approach: "Genie Ontology", retrieves: "Genie's own snippets + Pages", query: "1 SQL query" },
  { approach: "RAG", retrieves: "top 5 care-protocol passages", query: "1 SQL query" },
  { approach: "Ontobricks graph", retrieves: "subgraph around the linked entities", query: "1 graph-runner call" },
];

function Box({ children, tone = "plain" }: { children: ReactNode; tone?: "plain" | "accent" | "ok" }) {
  const cls = tone === "accent" ? "border-primary/40 bg-primary/5" : tone === "ok" ? "border-success/40 bg-success/10" : "border-border bg-surface";
  return <div className={`rounded-lg border px-2.5 py-1.5 text-[12px] leading-snug ${cls}`}>{children}</div>;
}

const Arrow = () => <ArrowRight className="h-4 w-4 shrink-0 text-muted" />;

export function EvalExplainer({ judge, agent }: { judge?: string; agent?: string }) {
  const j = judge?.replace("databricks:/", "") ?? "LLM judge";
  return (
    <div className="space-y-3">
      <p className="text-[13px] text-fg">
        <span className="font-semibold">What we evaluate:</span> can each approach's <span className="font-semibold">own retrieval</span> answer
        the question? Same questions, same agent ({agent ?? "fixed LLM"}), same judge ({j}), one run per cell, scored against a
        hand-verified gold answer.
      </p>
      <div className="flex flex-wrap items-center gap-1.5">
        <Box>Question</Box>
        <Arrow />
        <Box tone="accent">Approach retrieves<br /><span className="text-muted">its own way</span></Box>
        <Arrow />
        <Box>Judge: is every gold fact <span className="font-semibold">stated</span> in what it retrieved?</Box>
        <Arrow />
        <Box tone="ok">✓ Answered in context</Box>
      </div>
      <div className="flex flex-wrap items-center gap-1.5 pl-6">
        <CornerDownRight className="h-4 w-4 shrink-0 text-muted" />
        <span className="text-[11.5px] text-muted">if not</span>
        <Box tone="accent">Agent writes <span className="font-semibold">one</span> query in the approach's own language, using only what was retrieved</Box>
        <Arrow />
        <Box>Run it</Box>
        <Arrow />
        <Box>Judge: does the result match the gold?</Box>
        <Arrow />
        <Box tone="ok">✓ one query</Box>
        <span className="text-[11.5px] text-muted">else ✗, with the reason</span>
      </div>
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-[11.5px]">
          <thead className="bg-surface-2 text-left">
            <tr><th className="px-2.5 py-1 font-semibold">Approach</th><th className="px-2.5 py-1 font-semibold">Retrieves</th>
              <th className="px-2.5 py-1 font-semibold">Its one query</th></tr>
          </thead>
          <tbody>
            {INTERFACES.map((r) => (
              <tr key={r.approach} className="border-t border-border">
                <td className="px-2.5 py-1 font-medium">{r.approach}</td>
                <td className="px-2.5 py-1 text-muted">{r.retrieves}</td>
                <td className="px-2.5 py-1">{r.query}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[11.5px] text-muted">
        Genie One is scored separately, end to end and hand-verified: it runs its own retrieval and as many queries as it needs.
      </p>
    </div>
  );
}
