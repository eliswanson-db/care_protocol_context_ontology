import { FlaskConical, ShieldCheck, TriangleAlert } from "lucide-react";
import { Chip, num, pct } from "./ui";
import { useLs, VERSIONS } from "./LsContext";

// Study Overview: always on top of every Clinical Study tab. Active study + rule version, population and
// evaluability counts for that version only (never pooled), data-quality warnings and the synthetic banner.
export function StudyStrip() {
  const { study, setStudy, ruleVersion, setRuleVersion, overview, overviewError } = useLs();
  const rv = overview?.rule_versions.find((r) => r.endpoint_version === ruleVersion);
  const sv = overview?.study_versions.filter((v) => v.study_id === study) ?? [];
  const arms = overview?.endpoint_summary.filter((r) => r.rule_version === ruleVersion) ?? [];
  const pop = overview?.populations.find((p) => p.study === study);
  const warnings = overview?.data_quality.filter((d) => Number(d.n_violations) > 0) ?? [];
  const errors = warnings.filter((w) => w.severity === "ERROR");
  return (
    <div className="border-b border-border bg-surface px-4 py-2.5">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-muted">Study</span>
          {Object.keys(VERSIONS).map((s) => (
            <button key={s} onClick={() => setStudy(s)}
              className={`rounded-md border px-2 py-1 text-[12px] font-semibold ${s === study ? "border-primary bg-primary/10 text-primary" : "border-border text-muted hover:text-fg"}`}>
              {s}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-muted">Rule version</span>
          {VERSIONS[study].map((v) => (
            <button key={v} onClick={() => setRuleVersion(v)}
              className={`rounded-md border px-2 py-1 font-mono text-[12px] ${v === ruleVersion ? "border-primary bg-primary/10 text-primary" : "border-border text-muted hover:text-fg"}`}>
              {v}
            </button>
          ))}
          {rv && (
            <span className="text-[11.5px] text-muted">
              protocol {rv.protocol_version} · SAP {rv.sap_version} · window ±{rv.window_half_width_days} d · baseline {rv.baseline_method}
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-1.5 text-[12px]">
          {arms.map((a) => (
            <span key={a.arm} className="rounded-md border border-border bg-surface-2 px-2 py-0.5">
              <b>{a.arm}</b> FAS {a.fas} · derived {a.derived} · missing {pct(a.missingness)} · mean {num(a.mean_pchg, 2)}%
            </span>
          ))}
          {pop && (
            <span className="text-muted">
              screened {pop.screened} · rule-eligible {pop.eligible} · randomized {pop.randomized} · PPS {pop.pps} · enrolled in error {pop.enrolled_in_error}
            </span>
          )}
        </div>
        <div className="ml-auto flex items-center gap-1.5">
          {overview?.verification && (
            <Chip tone={overview.verification.status === "PASS" ? "good" : "bad"} title="named participants vs hand-worked expected results">
              <ShieldCheck className="h-3 w-3" /> oracle {overview.verification.status}
            </Chip>
          )}
          {warnings.length > 0 && (
            <Chip tone={errors.length ? "bad" : "warn"} title={warnings.map((w) => `${w.check_id}: ${w.n_violations}`).join("\n")}>
              <TriangleAlert className="h-3 w-3" /> {warnings.reduce((s, w) => s + Number(w.n_violations), 0)} data-quality findings
            </Chip>
          )}
          <Chip tone="warn"><FlaskConical className="h-3 w-3" /> synthetic · not submission-ready</Chip>
        </div>
      </div>
      {sv.length > 1 && (
        <div className="mt-1.5 flex flex-wrap gap-x-4 text-[11.5px] text-muted">
          {sv.map((v) => (
            <span key={v.protocol_version}>
              <b className="text-fg">P{v.protocol_version}</b> {v.effective_date}{v.change_summary ? ` — ${v.change_summary}` : " — original"}
            </span>
          ))}
        </div>
      )}
      {overviewError && <div className="mt-1 text-[12px] text-destructive">{overviewError}</div>}
    </div>
  );
}
