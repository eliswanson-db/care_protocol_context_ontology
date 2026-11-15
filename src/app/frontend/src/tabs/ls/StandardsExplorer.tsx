import { ArrowLeft, Network, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { ls, type ConceptNode, type Row } from "../../lsApi";
import { Card, Chip, ErrorBox, Loading, Table, fmt } from "./ui";

const STARTS: [string, string][] = [
  ["COSMOS_BC:C81328", "Body Weight (biomedical concept)"],
  ["MONDO:0005439", "familial hypercholesterolemia"],
  ["MONDO:0012819", "diabetic ketoacidosis"],
  ["MONDO:0015277", "medullary thyroid carcinoma"],
  ["MONDO:0007147", "obstructive sleep apnea"],
  ["MONDO:0001302", "hypertensive heart disease (MONDO gap)"],
  ["MEDRT:N0000178480", "GLP-1 Receptor Agonist [EPC]"],
  ["RXNORM:1991302", "semaglutide"],
];
const OFFICIAL: Record<string, string> = {
  MONDO: "MONDO 2026-11-03", MEDRT: "MED-RT 2026.11.02 (public EVS)", MESH: "MeSH 2026", MESH_SCR: "MeSH SCR 2026",
  RXNORM: "RxNorm via MED-RT", CDISC_CT: "CDISC CT", COSMOS_BC: "CDISC COSMoS", COSMOS_DSS: "CDISC COSMoS",
  SDTM_VAR: "COSMoS DSS (SDTM variable names)", NCIT: "NCIt 26.10d", ICD10CM: "ICD-10-CM (MONDO xref)",
};

function EdgeList({ rows, dir, go }: { rows: Row[]; dir: "out" | "in"; go: (id: string) => void }) {
  const by: Record<string, Row[]> = {};
  rows.forEach((r) => (by[r.predicate] ??= []).push(r));
  return (
    <div className="space-y-2">
      {Object.entries(by).map(([pred, rs]) => (
        <div key={pred}>
          <div className="mb-0.5 flex items-center gap-1.5 font-mono text-[11.5px] font-semibold">
            {dir === "in" ? "← " : ""}{pred}{dir === "out" ? " →" : ""}
            {pred.startsWith("cpl:") ? <Chip tone="warn">demo extension</Chip> : <Chip>{rs[0].source_artifact}</Chip>}
            <span className="font-normal text-muted">{rs.length}</span>
          </div>
          <div className="flex flex-wrap gap-1">
            {rs.slice(0, 40).map((r) => (
              <button key={r.other} onClick={() => go(r.other)} title={r.authority ? `authority: ${r.authority}` : r.other}
                className="rounded border border-border bg-surface-2 px-1.5 py-0.5 text-[11.5px] hover:border-primary">
                {r.label || r.other} <span className="font-mono text-[10px] text-muted">{r.other}</span>
              </button>
            ))}
            {rs.length > 40 && <span className="text-[11px] text-muted">+{rs.length - 40} more</span>}
          </div>
        </div>
      ))}
      {!rows.length && <div className="text-[12px] text-muted">None.</div>}
    </div>
  );
}

export function StandardsExplorer() {
  const [id, setId] = useState("MONDO:0012819");
  const [hist, setHist] = useState<string[]>([]);
  const [node, setNode] = useState<ConceptNode | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Row[] | null>(null);
  useEffect(() => {
    let live = true;
    setNode(null);
    setError(null);
    ls.concept(id).then((n) => live && setNode(n)).catch((e) => live && setError(String(e)));
    return () => { live = false; };
  }, [id]);
  const go = (next: string) => { setHist((h) => [...h, id]); setId(next); };
  const back = () => setHist((h) => { const p = h[h.length - 1]; if (p) setId(p); return h.slice(0, -1); });
  const search = () => q.length >= 2 && ls.conceptSearch(q).then((r) => setHits(r.results)).catch(() => setHits([]));
  const c = node?.concept;
  return (
    <div className="flex min-h-0 flex-1">
      <aside className="w-72 shrink-0 overflow-y-auto border-r border-border bg-surface p-3">
        <div className="mb-2 flex gap-1">
          <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search()}
            placeholder="search concepts (label or id)" className="w-full rounded-md border border-border bg-surface-2 px-2 py-1 text-[12px]" />
          <button onClick={search} className="rounded-md border border-border px-2 text-muted hover:text-fg" aria-label="search"><Search className="h-3.5 w-3.5" /></button>
        </div>
        {hits && (
          <div className="mb-3">
            {hits.map((h) => (
              <button key={h.concept_id} onClick={() => go(h.concept_id)} className="block w-full rounded px-1.5 py-1 text-left hover:bg-surface-2">
                <div className="text-[12px]">{h.label || h.concept_id}</div>
                <div className="font-mono text-[10.5px] text-muted">{h.concept_id} · {h.concept_type}</div>
              </button>
            ))}
          </div>
        )}
        <div className="mb-1 text-[11px] font-semibold uppercase text-muted">Start here</div>
        {STARTS.map(([sid, label]) => (
          <button key={sid} onClick={() => go(sid)} className={`block w-full rounded px-1.5 py-1 text-left hover:bg-surface-2 ${sid === id ? "bg-primary/10" : ""}`}>
            <div className="text-[12px]">{label}</div>
            <div className="font-mono text-[10.5px] text-muted">{sid}</div>
          </button>
        ))}
        <div className="mt-3 rounded-md border border-border bg-surface-2 p-2 text-[11.5px] leading-snug text-muted">
          Every fact here is a <b>direct</b> assertion from a pinned open release. Membership and contraindication
          answers are derived by walking them (closure / graph), never stored. Predicates prefixed <span className="font-mono">cpl:</span> are demo extensions.
        </div>
      </aside>
      <main className="min-w-0 flex-1 space-y-3 overflow-y-auto p-4">
        {error && <ErrorBox error={error} />}
        {!node && !error && <Loading what={`Loading ${id}`} />}
        {node && c && (
          <>
            <div className="flex flex-wrap items-center gap-2">
              {hist.length > 0 && <button onClick={back} className="rounded-md border border-border p-1 text-muted hover:text-fg" aria-label="back"><ArrowLeft className="h-4 w-4" /></button>}
              <Network className="h-5 w-5 text-primary" />
              <div>
                <div className="text-lg font-bold">{c.label || c.concept_id}</div>
                <div className="font-mono text-[12px] text-muted">{c.concept_id} · {c.concept_type}{c.notation ? ` · ${c.notation}` : ""}</div>
              </div>
              <div className="ml-auto flex gap-1">
                <Chip tone="info">{OFFICIAL[c.scheme] ?? c.scheme}</Chip>
                <Chip>release {c.release}</Chip>
              </div>
            </div>
            {c.definition && <div className="text-[12.5px] leading-snug text-muted">{c.definition}</div>}

            {node.classes.length > 0 && (
              <Card title="Concept classes (derived, not stored)" sub="Closure walk over MONDO is_a, exclusion wins; contraindication = broadening-only MONDO → MeSH → MED-RT walk.">
                <Table rows={node.classes} cols={[
                  { key: "class_id", label: "class", className: "font-mono" },
                  { key: "member", label: "result", render: (r) => r.class_id === "CI-STUDY-DRUG-CLASS"
                    ? <Chip tone={r.contraindicated_for_class ? "bad" : "good"}>{r.contraindicated_for_class ? "contraindicated" : "not contraindicated"}</Chip>
                    : <Chip tone={r.member ? "good" : "muted"}>{r.member ? "member" : "not a member"}</Chip> },
                  { key: "via", label: "why", render: (r) => r.class_id === "CI-STUDY-DRUG-CLASS"
                    ? (r.drugs?.length ? <span>CI_with for <b>{r.drugs.join(", ")}</b>{r.paths?.[0] ? <span className="text-muted"> via {r.paths[0].via_disease} → {r.paths[0].mesh_record} → {r.paths[0].mesh_concept}</span> : null}</span> : "no MED-RT contraindication reached")
                    : r.excluded_by?.length ? <span>under carve-out <b>{r.excluded_by.map((x: Row) => x.root).join(", ")}</b></span>
                    : r.via_roots?.length ? <span>is_a* <b>{r.via_roots.map((x: Row) => `${x.root_label ?? x.root} (depth ${x.depth})`).join(", ")}</b></span>
                    : <span className="text-muted">not under any root</span> },
                ]} />
              </Card>
            )}

            {node.ancestors.length > 0 && (
              <Card title="Ancestors (closure)" sub={`${node.ancestors.length} ancestor(s), shortest distance`}>
                <div className="flex flex-wrap gap-1">
                  {node.ancestors.map((a) => (
                    <button key={a.ancestor_code} onClick={() => go(a.ancestor_code)} className="rounded border border-border bg-surface-2 px-1.5 py-0.5 text-[11.5px] hover:border-primary">
                      <span className="text-muted">{a.depth}·</span> {a.ancestor_name || a.ancestor_code}
                    </button>
                  ))}
                </div>
              </Card>
            )}

            {node.mapping && (
              <Card title="Concept → dataset → physical column" sub={`filter: ${node.mapping.filter}`}>
                <Table rows={node.mapping.mappings} cols={[
                  { key: "specialization", label: "specialization", className: "font-mono" },
                  { key: "variable", label: "SDTM variable", className: "font-mono" },
                  { key: "allowed_values", label: "allowed CT values", render: (r) => fmt(r.allowed_values) },
                  { key: "physical_column", label: "physical column", className: "font-mono text-[11px]" },
                ]} />
              </Card>
            )}

            <div className="grid gap-3 xl:grid-cols-2">
              <Card title="Outgoing direct facts"><EdgeList rows={node.outgoing} dir="out" go={go} /></Card>
              <Card title="Incoming direct facts"><EdgeList rows={node.incoming} dir="in" go={go} /></Card>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
