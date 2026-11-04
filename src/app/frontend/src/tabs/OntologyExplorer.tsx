import { AlertTriangle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, type OntologyGraph } from "../api";

const KIND: Record<string, { label: string; fill: string; chip: string }> = {
  measure: { label: "measure", fill: "var(--primary)", chip: "bg-primary/15 text-primary" },
  drug_class: { label: "drug class", fill: "var(--success)", chip: "bg-success/15 text-success" },
  loinc_part: { label: "LOINC Part", fill: "var(--warning)", chip: "bg-warning/15 text-warning" },
  contraindication: { label: "contraindication", fill: "var(--destructive)", chip: "bg-destructive/15 text-destructive" },
  condition: { label: "condition", fill: "var(--fg)", chip: "bg-surface-2 text-fg" },
  threshold: { label: "threshold", fill: "var(--muted)", chip: "bg-surface-2 text-muted" },
};

function kindOf(g: OntologyGraph, id: string) {
  return g.nodes.find((n) => n.id === id)?.kind ?? "threshold";
}

function EgoGraph({ g, sel, onSelect }: { g: OntologyGraph; sel: string; onSelect: (id: string) => void }) {
  const ego = g.edges.filter((e) => e.subject === sel || e.object === sel);
  const W = 820, H = 460, cx = W / 2, cy = H / 2, R = 165;
  const chipW = (s: string) => Math.min(190, Math.max(54, s.length * 7.3 + 18));
  const CH = 26;

  const neighbors = ego.map((e, i) => {
    const other = e.subject === sel ? e.object : e.subject;
    const outgoing = e.subject === sel;
    const a = ego.length === 1 ? -Math.PI / 2 : (i / ego.length) * 2 * Math.PI - Math.PI / 2;
    return { e, other, outgoing, x: cx + R * Math.cos(a), y: cy + R * Math.sin(a) };
  });

  const Chip = ({ x, y, id, center }: { x: number; y: number; id: string; center?: boolean }) => {
    const w = chipW(id);
    const k = KIND[kindOf(g, id)];
    return (
      <g style={{ cursor: "pointer" }} onClick={() => onSelect(id)}>
        <rect x={x - w / 2} y={y - CH / 2} width={w} height={CH} rx={6}
          fill={center ? k.fill : "var(--surface)"} stroke={k.fill} strokeWidth={center ? 0 : 1.5} />
        <text x={x} y={y + 4} textAnchor="middle" fontSize="11" fontFamily="ui-monospace, monospace"
          fill={center ? "#fff" : "var(--fg)"} fontWeight={center ? 700 : 500}>{id}</text>
      </g>
    );
  };

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="concept ego-network">
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 Z" fill="var(--muted)" />
        </marker>
      </defs>
      {neighbors.map((n, i) => {
        const x1 = n.outgoing ? cx : n.x, y1 = n.outgoing ? cy : n.y;
        const x2 = n.outgoing ? n.x : cx, y2 = n.outgoing ? n.y : cy;
        const mx = (cx + n.x) / 2, my = (cy + n.y) / 2;
        return (
          <g key={i}>
            <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--border)" strokeWidth="1.5" markerEnd="url(#arrow)" />
            <text x={mx} y={my - 3} textAnchor="middle" fontSize="9" fill="var(--muted)">
              {n.e.predicate}{n.e.value ? ` (${n.e.value})` : ""}
            </text>
          </g>
        );
      })}
      {neighbors.map((n, i) => <Chip key={i} x={n.x} y={n.y} id={n.other} />)}
      <Chip x={cx} y={cy} id={sel} center />
    </svg>
  );
}

export function OntologyExplorer() {
  const [g, setG] = useState<OntologyGraph | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sel, setSel] = useState("GSD");

  useEffect(() => {
    api.ontology().then(setG).catch((e) => setError(String(e)));
  }, []);

  const grouped = useMemo(() => {
    if (!g) return [];
    const by: Record<string, typeof g.nodes> = {};
    for (const n of g.nodes) (by[n.kind] ??= []).push(n);
    return Object.entries(by);
  }, [g]);

  if (error)
    return (
      <div className="m-6 flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
        <AlertTriangle className="h-4 w-4" /> {error}
      </div>
    );
  if (!g) return <div className="m-6 h-96 animate-pulse rounded-xl bg-surface-2" />;

  const ego = g.edges.filter((e) => e.subject === sel || e.object === sel);

  return (
    <div className="flex min-h-0 flex-1">
      <aside className="w-64 shrink-0 overflow-y-auto border-r border-border bg-surface">
        <div className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted">Concepts ({g.nodes.length})</div>
        {grouped.map(([kind, nodes]) => (
          <div key={kind} className="mb-2 px-2">
            <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-muted">{KIND[kind]?.label ?? kind}</div>
            {nodes.map((n) => (
              <button key={n.id} onClick={() => setSel(n.id)}
                className={`block w-full truncate rounded px-2 py-1 text-left font-mono text-xs transition ${
                  n.id === sel ? "bg-surface-2 text-primary" : "text-fg hover:bg-surface-2"}`}>
                {n.id}
              </button>
            ))}
          </div>
        ))}
      </aside>

      <main className="min-w-0 flex-1 overflow-y-auto px-6 py-5">
        <div className="mb-4">
          <h1 className="text-2xl font-bold tracking-tight">The modeled clinical graph</h1>
          <p className="mt-1.5 text-[15px] text-muted">
            Typed edges (<span className="font-mono">protocol_edges</span>) linking measures ↔ drug classes ↔ LOINC
            Parts ↔ conditions ↔ thresholds — the cross-domain relationships a closure table can't express. Click a
            node to walk the graph.
          </p>
        </div>

        <div className="mb-3 flex flex-wrap gap-2 text-[10px]">
          {Object.entries(KIND).map(([k, v]) => (
            <span key={k} className={`rounded px-1.5 py-0.5 font-semibold ${v.chip}`}>{v.label}</span>
          ))}
        </div>

        <div className="rounded-xl border border-border bg-surface p-2">
          <EgoGraph g={g} sel={sel} onSelect={setSel} />
        </div>

        <div className="mt-4 overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-left text-xs">
            <thead className="bg-surface-2 text-muted">
              <tr>
                {["subject", "predicate", "object", "value", "source"].map((h) => (
                  <th key={h} className="px-3 py-1.5 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ego.map((e, i) => (
                <tr key={i} className="border-t border-border font-mono">
                  <td className="px-3 py-1.5">{e.subject}</td>
                  <td className="px-3 py-1.5 text-primary">{e.predicate}</td>
                  <td className="px-3 py-1.5">{e.object}</td>
                  <td className="px-3 py-1.5 text-muted">{e.value ?? "—"}</td>
                  <td className="px-3 py-1.5 text-muted">{e.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p className="mt-4 text-[11px] text-muted">
          Within a vocabulary, is-a (ICD-10, RxNorm) and LOINC multiaxial identity resolve via the governed closures /
          Part table — a closure <span className="font-semibold">is</span> the graph there. These cross-domain typed
          edges are where a graph earns its place; a formal OWL graph with a reasoner (inferred classes, variable-shape
          path queries) is the A5 Ontobricks hop — not yet built. Live over the shared catalog.
        </p>
      </main>
    </div>
  );
}
