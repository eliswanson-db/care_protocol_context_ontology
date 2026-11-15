import { ArrowRight, GitCompare } from "lucide-react";
import { useEffect, useState } from "react";
import { ls, type Amendment } from "../../lsApi";
import { useLs } from "./LsContext";
import { Card, Chip, ErrorBox, Loading, Table, num, pct, toneFor } from "./ui";

function Stat({ label, value, sub }: { label: string; value: number | string; sub?: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">{label}</div>
      <div className="text-2xl font-bold tabular-nums">{value}</div>
      {sub && <div className="text-[11.5px] text-muted">{sub}</div>}
    </div>
  );
}

function SiteBars({ rows, onPick, picked }: { rows: Amendment["by_site"]; onPick: (s: string | undefined) => void; picked?: string }) {
  const top = rows.slice(0, 12);
  const max = Math.max(1, ...top.map((r) => Number(r.recovered)));
  return (
    <div className="space-y-1">
      {top.map((r) => (
        <button key={r.site} onClick={() => onPick(picked === r.site ? undefined : r.site)} className="flex w-full items-center gap-2 text-left">
          <span className={`w-16 font-mono text-[11.5px] ${picked === r.site ? "font-bold text-primary" : ""}`}>{r.site}</span>
          <span className="h-3 rounded-sm" style={{ width: `${(Number(r.recovered) / max) * 70}%`, background: picked === r.site ? "var(--primary)" : "var(--lens-closure)" }} />
          <span className="text-[11.5px] tabular-nums">{r.recovered} <span className="text-muted">of {r.compared}</span></span>
        </button>
      ))}
    </div>
  );
}

export function AmendmentLab() {
  const { openParticipant, study } = useLs();
  const [site, setSite] = useState<string | undefined>();
  const [a, setA] = useState<Amendment | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    setA(null);
    ls.amendment(site).then((r) => live && setA(r)).catch((e) => live && setError(String(e)));
    return () => { live = false; };
  }, [site]);
  if (study !== "CSL-A")
    return <div className="p-6 text-sm text-muted">Amendment 1 changed the CSL-A Week 24 window. CSL-B has a single rule version; switch the study to CSL-A.</div>;
  if (error) return <ErrorBox error={error} />;
  if (!a) return <Loading what="Comparing EP-A-WT24.R1 with EP-A-WT24.R2" />;
  const c = a.impact.counts;
  const arms = (s: Amendment["summary_r1"]) => Object.fromEntries(s.by_arm.map((x) => [x.arm, x]));
  const r1 = arms(a.summary_r1), r2 = arms(a.summary_r2);
  return (
    <main className="flex-1 space-y-3 overflow-y-auto p-4">
      <div className="flex items-center gap-2">
        <GitCompare className="h-5 w-5 text-primary" />
        <h2 className="text-lg font-bold">Amendment Lab — CSL-A Protocol Amendment 1</h2>
        <span className="font-mono text-[12px] text-muted">EP-A-WT24.R1 <ArrowRight className="inline h-3 w-3" /> EP-A-WT24.R2</span>
      </div>

      <Card title="What changed in the definition" sub={a.definition_diff.differences.length === 1 ? "Exactly one parameter changed, so the impact is interpretable." : undefined}>
        <Table rows={a.definition_diff.differences}
          cols={[{ key: "parameter", label: "changed parameter", className: "font-mono font-semibold" },
            { key: "EP-A-WT24.R1", label: "R1 (protocol/SAP 1.0)" }, { key: "EP-A-WT24.R2", label: "R2 (protocol/SAP 2.0)" }]} />
        <div className="mt-1.5 flex flex-wrap items-center gap-1 text-[11.5px] text-muted">
          unchanged: {a.definition_diff.same.map((k) => <Chip key={k}>{k}</Chip>)}
        </div>
        <div className="mt-1 text-[11.5px] text-muted">
          Sources: {a.impact.citations.map((x) => `${x.rule_version} ← ${x.document} §${x.section}`).join(" · ")}
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Became derivable" value={c.became} sub={`of ${c.compared} randomized${site ? ` at ${site}` : ""}`} />
        <Stat label="Selected record changed" value={c.changed_selection} sub="incl. none → one" />
        <Stat label="Endpoint value changed" value={c.changed_value} sub="incl. NULL → value" />
        <Stat label="Gained eligible candidates" value={c.more_candidates} sub="selection may be unchanged" />
      </div>
      <div className="rounded-md border border-primary/30 bg-primary/5 px-3 py-2 text-[12.5px]">{a.impact.note}</div>

      <div className="grid gap-3 lg:grid-cols-2">
        <Card title="Aggregate, by arm (FAS)" sub="Same participants, two rule versions. Descriptive, synthetic.">
          <Table rows={Object.keys(r1).map((arm) => ({ arm, d1: r1[arm].derived, d2: r2[arm]?.derived, m1: r1[arm].missingness, m2: r2[arm]?.missingness, x1: r1[arm].mean_pct_change, x2: r2[arm]?.mean_pct_change }))}
            cols={[{ key: "arm", label: "arm" },
              { key: "d1", label: "derived R1" }, { key: "d2", label: "derived R2" },
              { key: "m1", label: "missing R1", render: (r) => pct(r.m1) }, { key: "m2", label: "missing R2", render: (r) => pct(r.m2) },
              { key: "x1", label: "mean % R1", render: (r) => num(r.x1, 2) }, { key: "x2", label: "mean % R2", render: (r) => num(r.x2, 2) }]} />
        </Card>
        <Card title="Recovered participants by site" sub="Click a site to filter. One site's Week 24 visits ran 8–13 days late.">
          <SiteBars rows={a.by_site} onPick={setSite} picked={site} />
        </Card>
      </div>

      {a.named_examples.length > 0 && (
        <Card title="Named fixture participants affected" sub="Hand-worked expected outcomes exist for each; click to open the evidence.">
          <Table rows={a.named_examples} onRow={(r) => openParticipant(r.USUBJID, "EP-A-WT24.R2")}
            cols={[{ key: "USUBJID", label: "participant", className: "font-mono" },
              { key: "status_from", label: "R1", render: (r) => <Chip tone={toneFor(r.status_from)}>{r.status_from}</Chip> },
              { key: "status_to", label: "R2", render: (r) => <Chip tone={toneFor(r.status_to)}>{r.status_to}</Chip> },
              { key: "pchg_to", label: "R2 %", render: (r) => num(r.pchg_to, 2) },
              { key: "explanation", label: "why" }]} />
        </Card>
      )}

      <Card title={`Affected participants${site ? ` at ${site}` : ""}`} sub="Every participant whose eligible candidates, selected record or value changed. Click to trace.">
        <Table rows={a.impact.affected} onRow={(r) => openParticipant(r.USUBJID, "EP-A-WT24.R2")} max={200}
          cols={[{ key: "USUBJID", label: "participant", className: "font-mono" }, { key: "site", label: "site" },
            { key: "status_from", label: "R1", render: (r) => <Chip tone={toneFor(r.status_from)}>{r.status_from}</Chip> },
            { key: "status_to", label: "R2", render: (r) => <Chip tone={toneFor(r.status_to)}>{r.status_to}</Chip> },
            { key: "pchg_to", label: "R2 %", render: (r) => num(r.pchg_to, 2) },
            { key: "explanation", label: "why" }]} />
      </Card>
    </main>
  );
}
