import { ArrowRight, FileText, GitBranch, Search, User } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { ls, type Candidate, type Participant, type Row } from "../../lsApi";
import { useLs, VERSIONS } from "./LsContext";
import { Card, Chip, Code, ErrorBox, Loading, Table, fmt, num, toneFor } from "./ui";

const DECISION_COLOR: Record<string, string> = {
  SELECTED: "var(--success)", ELIGIBLE_NOT_SELECTED: "var(--warning)", EXCLUDED: "var(--destructive)",
};

function Timeline({ p }: { p: Participant }) {
  const r = p.rule.rule;
  const target = Number(r.target_offset_days) + 1; // target study day (no day 0)
  const hw = Number(r.window_half_width_days);
  const blo = Number(r.baseline_window_start), bhi = Number(r.baseline_window_end);
  const pts = p.trace.candidates.filter((c) => c.study_day !== null && c.study_day !== undefined);
  const lo = Math.min(blo - 8, ...pts.map((c) => Number(c.study_day)));
  const hiCap = target + hw + 30;
  const shown = pts.filter((c) => Number(c.study_day) <= hiCap);
  const later = pts.length - shown.length;
  const W = 900, H = 150, L = 20, R = 20, top = 22, mid = 78;
  const x = (d: number) => L + ((d - lo) / (hiCap - lo)) * (W - L - R);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="observation timeline by study day">
      <rect x={x(blo)} y={top} width={Math.max(2, x(bhi + (r.same_day_predose === "not_allowed" ? 0 : 1)) - x(blo))} height={mid - top + 18}
        fill="var(--primary)" opacity="0.10" />
      <text x={x(blo)} y={top - 6} fontSize="10" fill="var(--primary)">baseline window {blo}…{bhi}{r.same_day_predose === "not_allowed" ? "" : " (+ day 1 pre-dose)"}</text>
      <rect x={x(target - hw)} y={top} width={x(target + hw) - x(target - hw)} height={mid - top + 18} fill="var(--success)" opacity="0.12" />
      <line x1={x(target)} y1={top} x2={x(target)} y2={mid + 18} stroke="var(--success)" strokeDasharray="4 3" />
      <text x={x(target - hw)} y={top - 6} fontSize="10" fill="var(--success)">Week 24 window: day {target} ±{hw}</text>
      <line x1={L} y1={mid} x2={W - R} y2={mid} stroke="var(--border)" />
      <line x1={x(1)} y1={mid - 30} x2={x(1)} y2={mid + 8} stroke="var(--fg)" strokeWidth="1" />
      <text x={x(1) + 3} y={mid - 22} fontSize="9" fill="var(--fg)">first dose (day 1)</text>
      {shown.map((c, i) => {
        const cx = x(Number(c.study_day));
        const color = DECISION_COLOR[c.decision] ?? "var(--muted)";
        return (
          <g key={c.obs_id}>
            <circle cx={cx} cy={mid} r={c.decision === "SELECTED" ? 7 : 5} fill={color} stroke="var(--surface)" strokeWidth="1.5">
              <title>{`${c.visit} · ${c.vsdtc} · day ${c.study_day}\n${c.orres ?? "—"} ${c.raw_unit ?? ""} → ${c.weight_kg ? num(c.weight_kg, 2) + " kg" : "invalid"}\n${c.decision} — ${c.reason}`}</title>
            </circle>
            <text x={cx} y={mid + 22 + (i % 3) * 11} fontSize="9" textAnchor="middle" fill="var(--muted)">{c.vsseq}</text>
          </g>
        );
      })}
      {later > 0 && <text x={W - R} y={mid - 8} fontSize="9" textAnchor="end" fill="var(--muted)">+{later} later visits (not shown)</text>}
    </svg>
  );
}

function Picker({ onPick, current }: { onPick: (u: string) => void; current: string | null }) {
  const [tracers, setTracers] = useState<Row[]>([]);
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Row[] | null>(null);
  useEffect(() => {
    ls.tracers().then((r) => {
      setTracers(r.tracers);
      if (!current && r.tracers.length) onPick(r.tracers[0].usubjid);  // first hero, picked by rule server-side
    }).catch(() => void 0);
  }, []);
  const search = () => q.length >= 3 && ls.search(q).then((r) => setHits(r.participants)).catch(() => setHits([]));
  return (
    <aside className="w-72 shrink-0 overflow-y-auto border-r border-border bg-surface p-3">
      <div className="mb-2 flex gap-1">
        <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search()}
          placeholder="search e.g. CSL-A-118-00" className="w-full rounded-md border border-border bg-surface-2 px-2 py-1 text-[12px]" />
        <button onClick={search} className="rounded-md border border-border px-2 text-muted hover:text-fg" aria-label="search"><Search className="h-3.5 w-3.5" /></button>
      </div>
      {hits && (
        <div className="mb-3">
          <div className="mb-1 text-[11px] font-semibold uppercase text-muted">Search results</div>
          {hits.map((h) => (
            <button key={h.usubjid} onClick={() => onPick(h.usubjid)} className="block w-full truncate rounded px-1.5 py-1 text-left font-mono text-[12px] hover:bg-surface-2">
              {h.usubjid} <span className="text-muted">{h.site} {h.arm}</span>
            </button>
          ))}
        </div>
      )}
      <div className="mb-3">
        <div className="mb-1 text-[11px] font-semibold uppercase text-muted">Participants (picked by rule)</div>
        {tracers.map((t) => (
          <button key={t.tracer_id} onClick={() => onPick(t.usubjid)} title={t.rule}
            className={`mb-0.5 block w-full rounded px-1.5 py-1 text-left hover:bg-surface-2 ${current === t.usubjid ? "bg-primary/10" : ""}`}>
            <div className="text-[12px] font-semibold leading-snug">{t.title}</div>
            <div className="font-mono text-[11.5px] text-muted">{t.usubjid}</div>
          </button>
        ))}
      </div>
    </aside>
  );
}

function ProvenanceChain({ p }: { p: Participant }) {
  const t = p.trace;
  const sel = t.candidates.filter((c) => c.decision === "SELECTED");
  const steps: [string, string][] = [
    ["Raw EDC record", sel.map((c) => c.source_record_id).join(", ") || "—"],
    ["SDTM-shaped observation", sel.map((c) => c.obs_id).join(", ") || "—"],
    ["Endpoint result", `${t.usubjid} · ${t.endpoint_version} · ${t.result_status}`],
    ["Rule version", `${t.citation.rule_version} (${t.citation.review_state}, ${t.citation.approved_by})`],
    ["Document section", `${t.citation.document} §${t.citation.section}`],
    ["Execution run", t.execution_run_id],
  ];
  return (
    <div className="flex flex-wrap items-stretch gap-1.5">
      {steps.map(([k, v], i) => (
        <div key={k} className="flex items-center gap-1.5">
          <div className="rounded-md border border-border bg-surface-2 px-2 py-1">
            <div className="text-[10px] font-semibold uppercase tracking-wide text-muted">{k}</div>
            <div className="max-w-[260px] truncate font-mono text-[11.5px]" title={v}>{v}</div>
          </div>
          {i < steps.length - 1 && <ArrowRight className="h-3.5 w-3.5 text-muted" />}
        </div>
      ))}
    </div>
  );
}

// The SAP section is long; show only the sentences that state this rule's parameters, the rest on demand.
const RULE_LABELS = ["Baseline.", "Week 24 target date.", "Analysis window.", "Selection."];
function RuleSentences({ text }: { text?: string }) {
  if (!text) return <div className="text-[12px] text-muted">Section text unavailable.</div>;
  const paras = text.split(/\n\s*\n/).map((x) => x.replace(/\s+/g, " ").trim());
  const key = paras.filter((x) => RULE_LABELS.some((l) => x.startsWith(l)));
  return (
    <div className="space-y-1.5 text-[12px] leading-snug">
      {(key.length ? key : paras.slice(0, 2)).map((x, i) => {
        const l = RULE_LABELS.find((r) => x.startsWith(r));
        return <p key={i}>{l ? <><b>{l.slice(0, -1)}:</b>{x.slice(l.length)}</> : x}</p>;
      })}
      <details>
        <summary className="cursor-pointer text-muted hover:text-fg">Full section</summary>
        <Code>{text}</Code>
      </details>
    </div>
  );
}

function pathLabels(c: Row): string[] {
  try { return typeof c.path_labels === "string" ? JSON.parse(c.path_labels) : c.path_labels || []; } catch { return []; }
}

// One-line verdict; only the criteria that decided it are spelled out (with the ontology path when there is one).
function EligibilityCard({ p }: { p: Participant }) {
  const crit = p.eligibility.criteria;
  const pop = p.eligibility.population;
  const deciding = crit.filter((c) => !["MET", "NOT_TRIGGERED"].includes(c.outcome) || pathLabels(c).length);
  const head = crit[0] ? `${crit[0].eligibility_rule_id} · protocol ${crit[0].protocol_version} at screening` : undefined;
  return (
    <Card title="Eligibility at screening" sub={head}
      right={pop && (
        <div className="flex gap-1">
          <Chip tone={toneFor(String(pop.rule_eligible))}>{pop.rule_eligible ? "eligible" : "not eligible"}</Chip>
          {String(pop.edc_eligible) !== (pop.rule_eligible ? "Y" : "N") && <Chip tone="warn">EDC says {pop.edc_eligible}</Chip>}
          <Chip tone={toneFor(pop.FASFL)}>FAS {pop.FASFL}</Chip>
          <Chip tone={toneFor(pop.PPSFL)}>PPS {pop.PPSFL}</Chip>
        </div>
      )}>
      {deciding.length === 0 ? (
        <div className="text-[12px] text-muted">All {crit.length} criteria met; no history or medication triggered an exclusion.</div>
      ) : (
        <ul className="space-y-1 text-[12px]">
          {deciding.map((c) => (
            <li key={c.criterion_id} className="flex flex-wrap items-baseline gap-1.5">
              <span className="font-mono">{c.criterion_id}</span>
              <Chip tone={toneFor(c.outcome)}>{c.outcome}</Chip>
              <span>{c.detail}</span>
              {pathLabels(c).length > 0 && <span className="text-muted">· {pathLabels(c).join(" → ")}</span>}
            </li>
          ))}
        </ul>
      )}
      <details className="mt-1.5">
        <summary className="cursor-pointer text-[12px] text-muted hover:text-fg">All {crit.length} criteria</summary>
        <Table rows={crit} cols={[
          { key: "criterion_id", label: "criterion", className: "font-mono" },
          { key: "outcome", label: "outcome", render: (c) => <Chip tone={toneFor(c.outcome)}>{c.outcome}</Chip> },
          { key: "detail", label: "detail" },
        ]} />
      </details>
    </Card>
  );
}

export function ParticipantEvidence() {
  const { ruleVersion, setRuleVersion, focus, study, setStudy } = useLs();
  const [usubjid, setUsubjid] = useState<string | null>(focus?.usubjid ?? null);
  const [p, setP] = useState<Participant | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (focus?.usubjid) setUsubjid(focus.usubjid); }, [focus]);
  const rvForSubject = useMemo(() => {
    if (!usubjid) return ruleVersion;
    const s = usubjid.startsWith("CSL-B") ? "CSL-B" : "CSL-A";
    return VERSIONS[s].includes(ruleVersion) ? ruleVersion : VERSIONS[s][VERSIONS[s].length - 1];
  }, [usubjid, ruleVersion]);
  useEffect(() => {
    if (!usubjid) return;
    let live = true;
    setP(null);
    setError(null);
    ls.participant(usubjid, rvForSubject).then((r) => live && setP(r)).catch((e) => live && setError(String(e)));
    return () => { live = false; };
  }, [usubjid, rvForSubject]);

  const pick = (u: string) => {
    const s = u.startsWith("CSL-B") ? "CSL-B" : "CSL-A";
    if (s !== study) setStudy(s);
    setUsubjid(u);
  };
  const t = p?.trace;
  return (
    <div className="flex min-h-0 flex-1">
      <Picker onPick={pick} current={usubjid} />
      <main className="min-w-0 flex-1 space-y-3 overflow-y-auto p-4">
        {error && <ErrorBox error={error} />}
        {!p && !error && <Loading what={`Tracing ${usubjid} under ${rvForSubject}`} />}
        {p && t && (
          <>
            <div className="flex flex-wrap items-center gap-3">
              <User className="h-5 w-5 text-primary" />
              <div>
                <div className="font-mono text-lg font-bold">{p.usubjid}</div>
                <div className="text-[12.5px] text-muted">
                  {p.tracer ? <><b className="text-fg">{p.tracer.tracer_id}</b> {p.tracer.title} · </> : null}
                  {p.demographics && `${p.demographics.SITEID} ${p.demographics.COUNTRY} · ${p.demographics.SEX} ${p.demographics.AGE} y · arm ${p.demographics.ARMCD} · first dose ${p.demographics.RFXSTDTC ?? "—"}`}
                </div>
              </div>
              <div className="ml-auto flex flex-wrap gap-1.5">
                {p.rule_versions.map((v) => {
                  const b = p.by_version[v];
                  return (
                    <button key={v} onClick={() => setRuleVersion(v)}
                      className={`rounded-md border px-2 py-1 text-left ${v === p.rule_version ? "border-primary bg-primary/10" : "border-border"}`}>
                      <div className="font-mono text-[11px]">{v}</div>
                      <Chip tone={toneFor(b.result_status)}>{b.result_status}{b.pct_change ? ` ${num(b.pct_change, 2)}%` : ""}</Chip>
                    </button>
                  );
                })}
              </div>
            </div>

            <Card title="Observations on the study timeline" sub={`Placed by actual date; colour = decision under ${p.rule_version}.`}>
              <Timeline p={p} />
              <div className="mt-1 flex gap-3 text-[11px] text-muted">
                <span><span style={{ color: "var(--success)" }}>●</span> selected</span>
                <span><span style={{ color: "var(--warning)" }}>●</span> eligible, not selected</span>
                <span><span style={{ color: "var(--destructive)" }}>●</span> excluded</span>
              </div>
            </Card>

            <Card title="Candidates and decisions" sub="Every weight record, raw as keyed → kg → decision.">
              <Table rows={t.candidates} highlight={(c) => c.decision === "SELECTED"} cols={[
                { key: "vsseq", label: "seq" },
                { key: "visit", label: "visit" },
                { key: "vsdtc", label: "date", className: "font-mono" },
                { key: "study_day", label: "day" },
                { key: "days_from_target", label: "Δ target" },
                { key: "orres", label: "raw", render: (c: Candidate) => <>{fmt(c.orres)} <span className="text-muted">{c.raw_unit || ""}</span></> },
                { key: "weight_kg", label: "kg", render: (c) => num(c.weight_kg, 2) },
                { key: "decision", label: "decision", render: (c) => <Chip tone={toneFor(c.decision)}>{c.decision.replace(/_/g, " ").toLowerCase()}</Chip> },
                { key: "reason", label: "why", className: "font-mono text-[11px]" },
              ]} />
            </Card>

            <div className="grid gap-3 lg:grid-cols-2">
              <Card title="Calculation" sub={t.endpoint_version}>
                <div className="mb-1.5 flex flex-wrap items-center gap-2 text-[12px]">
                  <Chip tone={toneFor(t.result_status)}>{t.result_status}</Chip>
                  {t.exclusion_reason && <span className="font-mono text-[11.5px]">{t.exclusion_reason}</span>}
                </div>
                <div className="text-[12px] text-muted">reference {fmt(t.reference_date)} · Week 24 target {fmt(t.target_date)}</div>
                {t.calculation ? <Code>{t.calculation}</Code> : <div className="mt-1 text-[12px] text-muted">No value derived (no imputation).</div>}
              </Card>
              <Card title={<span className="flex items-center gap-1"><FileText className="h-3.5 w-3.5" /> Document support</span>}
                sub={`${p.rule.citation.document} §${p.rule.citation.section} · ${p.rule.citation.review_state} (${p.rule.citation.approved_by})`}>
                <RuleSentences text={p.rule.section_text?.text} />
              </Card>
            </div>

            <EligibilityCard p={p} />

            <Card title={<span className="flex items-center gap-1"><GitBranch className="h-3.5 w-3.5" /> Provenance chain</span>}>
              <ProvenanceChain p={p} />
              <details className="mt-2">
                <summary className="cursor-pointer text-[12px] text-muted hover:text-fg">Raw EDC source rows (bronze, exactly as delivered)</summary>
                <Table rows={p.raw_source} cols={[
                  { key: "record_id", label: "record", className: "font-mono text-[11px]" },
                  { key: "visit", label: "visit" }, { key: "vsdtc", label: "vsdtc", className: "font-mono" },
                  { key: "vsorres", label: "vsorres" }, { key: "vsorresu", label: "vsorresu" }, { key: "vsstat", label: "vsstat" },
                ]} />
              </details>
            </Card>
          </>
        )}
      </main>
    </div>
  );
}
