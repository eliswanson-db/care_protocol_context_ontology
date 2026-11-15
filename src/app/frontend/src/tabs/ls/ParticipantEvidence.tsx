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
  useEffect(() => { ls.tracers().then((r) => setTracers(r.tracers)).catch(() => void 0); }, []);
  const search = () => q.length >= 3 && ls.search(q).then((r) => setHits(r.participants)).catch(() => setHits([]));
  const groups = [["EDGE", "Endpoint edge cases"], ["ELIG", "Eligibility cases"]] as const;
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
      {groups.map(([prefix, label]) => (
        <div key={prefix} className="mb-3">
          <div className="mb-1 text-[11px] font-semibold uppercase text-muted">{label}</div>
          {tracers.filter((t) => t.tracer_id.startsWith(prefix)).map((t) => (
            <button key={t.usubjid} onClick={() => onPick(t.usubjid)}
              className={`mb-0.5 block w-full rounded px-1.5 py-1 text-left hover:bg-surface-2 ${current === t.usubjid ? "bg-primary/10" : ""}`}>
              <div className="font-mono text-[11.5px] font-semibold">{t.usubjid} <span className="font-normal text-muted">{t.tracer_id}</span></div>
              <div className="text-[11.5px] leading-snug text-muted">{t.title}</div>
            </button>
          ))}
        </div>
      ))}
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

export function ParticipantEvidence() {
  const { ruleVersion, setRuleVersion, focus, study, setStudy } = useLs();
  const [usubjid, setUsubjid] = useState<string | null>(focus?.usubjid ?? "CSL-A-FX-05");
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

            <Card title="Observations on the study timeline" sub={`Every weight record, placed by its actual date. Colour = decision under ${p.rule_version}; numbers = record sequence. Dates decide, visit labels don't.`}>
              <Timeline p={p} />
              <div className="mt-1 flex gap-3 text-[11px] text-muted">
                <span><span style={{ color: "var(--success)" }}>●</span> selected</span>
                <span><span style={{ color: "var(--warning)" }}>●</span> eligible, not selected</span>
                <span><span style={{ color: "var(--destructive)" }}>●</span> excluded</span>
              </div>
            </Card>

            <Card title="Candidates and decisions" sub="Raw value and unit as keyed at the site → CDISC CT unit → kg → decision. Nothing is dropped silently.">
              <Table rows={t.candidates} highlight={(c) => c.decision === "SELECTED"} cols={[
                { key: "vsseq", label: "seq" },
                { key: "visit", label: "visit" },
                { key: "vsdtc", label: "date/time", className: "font-mono" },
                { key: "study_day", label: "day" },
                { key: "days_from_target", label: "Δ target" },
                { key: "orres", label: "raw", render: (c: Candidate) => <>{fmt(c.orres)} <span className="text-muted">{c.raw_unit || ""}</span></> },
                { key: "ct_unit", label: "CT unit" },
                { key: "weight_kg", label: "kg", render: (c) => num(c.weight_kg, 2) },
                { key: "role", label: "role" },
                { key: "decision", label: "decision", render: (c) => <Chip tone={toneFor(c.decision)}>{c.decision}</Chip> },
                { key: "reason", label: "reason", className: "font-mono text-[11px]" },
              ]} />
            </Card>

            <div className="grid gap-3 lg:grid-cols-2">
              <Card title="Calculation" sub={`${t.endpoint_version} · formula from the approved rule`}>
                <div className="mb-2 flex flex-wrap gap-2 text-[12px]">
                  <Chip tone={toneFor(t.result_status)}>{t.result_status}</Chip>
                  {t.exclusion_reason && <span className="font-mono text-[11.5px]">{t.exclusion_reason}</span>}
                </div>
                <div className="text-[12.5px]">reference date <b>{fmt(t.reference_date)}</b> · Week 24 target <b>{fmt(t.target_date)}</b></div>
                {t.calculation ? <Code>{t.calculation}</Code> : <div className="mt-1 text-[12px] text-muted">No value derived; no imputation is done.</div>}
              </Card>
              <Card title={<span className="flex items-center gap-1"><FileText className="h-3.5 w-3.5" /> Document support</span>}
                sub={`${p.rule.citation.document} §${p.rule.citation.section} · protocol ${p.rule.citation.protocol_version} / SAP ${p.rule.citation.sap_version} · ${p.rule.citation.review_state} (${p.rule.citation.approved_by})`}>
                {p.rule.section_text ? <Code>{p.rule.section_text.text}</Code> : <div className="text-[12px] text-muted">Section text unavailable.</div>}
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {Object.entries(p.rule.assertions.reduce<Record<string, { n: number; state: string }>>((acc, a) => {
                    const k = `${a.assertion_type}=${a.value}`;
                    acc[k] = { n: (acc[k]?.n ?? 0) + 1, state: a.review_state };
                    return acc;
                  }, {})).map(([k, v]) => (
                    <Chip key={k} tone={toneFor(v.state)} title={`${v.state}; stated in ${v.n} document section(s)`}>{k}{v.n > 1 ? ` ×${v.n}` : ""}</Chip>
                  ))}
                </div>
              </Card>
            </div>

            <Card title="Eligibility at screening" sub={p.eligibility.criteria[0] ? `${p.eligibility.criteria[0].eligibility_rule_id} · protocol ${p.eligibility.criteria[0].protocol_version} (in force on the screening date)` : undefined}
              right={p.eligibility.population && (
                <div className="flex gap-1">
                  <Chip tone={toneFor(String(p.eligibility.population.rule_eligible))}>rule-eligible {String(p.eligibility.population.rule_eligible)}</Chip>
                  <Chip>EDC {p.eligibility.population.edc_eligible}</Chip>
                  <Chip tone={toneFor(p.eligibility.population.FASFL)}>FAS {p.eligibility.population.FASFL}</Chip>
                  <Chip tone={toneFor(p.eligibility.population.PPSFL)}>PPS {p.eligibility.population.PPSFL}</Chip>
                </div>
              )}>
              <Table rows={p.eligibility.criteria} cols={[
                { key: "criterion_id", label: "criterion", className: "font-mono" },
                { key: "outcome", label: "outcome", render: (c) => <Chip tone={toneFor(c.outcome)}>{c.outcome}</Chip> },
                { key: "detail", label: "detail" },
                { key: "path_labels", label: "ontology path", render: (c) => {
                  let labels: string[] = [];
                  try { labels = typeof c.path_labels === "string" ? JSON.parse(c.path_labels) : c.path_labels || []; } catch { labels = []; }
                  return labels.length ? <span className="text-[11.5px]">{labels.join(" → ")}</span> : <span className="text-muted">—</span>;
                } },
              ]} />
            </Card>

            <Card title={<span className="flex items-center gap-1"><GitBranch className="h-3.5 w-3.5" /> Provenance chain</span>} sub="From the raw record to the run that produced the number.">
              <ProvenanceChain p={p} />
            </Card>

            <Card title="Raw EDC source (bronze)" sub="Exactly as delivered: strings, site units, blanks.">
              <Table rows={p.raw_source} cols={[
                { key: "record_id", label: "record", className: "font-mono text-[11px]" },
                { key: "visit", label: "visit" }, { key: "vsdtc", label: "vsdtc", className: "font-mono" },
                { key: "vsorres", label: "vsorres" }, { key: "vsorresu", label: "vsorresu" }, { key: "vsstat", label: "vsstat" },
              ]} />
            </Card>
          </>
        )}
      </main>
    </div>
  );
}
