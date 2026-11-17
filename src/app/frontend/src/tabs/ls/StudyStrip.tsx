import { FlaskConical, ShieldCheck, TriangleAlert } from "lucide-react";
import { Chip, num, pct } from "./ui";
import { useLs, VERSIONS } from "./LsContext";

// One line on top of every Clinical Study tab: what you're looking at (study + rule version) and the three numbers
// that matter for it (never pooled). Population detail and protocol history live on the tabs that use them.
export function StudyStrip() {
  const { study, setStudy, ruleVersion, setRuleVersion, overview, overviewError } = useLs();
  const rv = overview?.rule_versions.find((r) => r.endpoint_version === ruleVersion);
  const arms = overview?.endpoint_summary.filter((r) => r.rule_version === ruleVersion) ?? [];
  const pop = overview?.populations.find((p) => p.study === study);
  const warnings = overview?.data_quality.filter((d) => Number(d.n_violations) > 0) ?? [];
  const errors = warnings.filter((w) => w.severity === "ERROR");
  const btn = (on: boolean) =>
    `rounded-md border px-2 py-0.5 text-[12px] ${on ? "border-primary bg-primary/10 font-semibold text-primary" : "border-border text-muted hover:text-fg"}`;
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 border-b border-border bg-surface px-4 py-2 text-[12px]">
      <div className="flex items-center gap-1">
        {Object.keys(VERSIONS).map((s) => (
          <button key={s} onClick={() => setStudy(s)} className={btn(s === study)}>{s}</button>
        ))}
      </div>
      <div className="flex items-center gap-1">
        {VERSIONS[study].map((v) => (
          <button key={v} onClick={() => setRuleVersion(v)} className={`${btn(v === ruleVersion)} font-mono`}>{v.split(".")[1]}</button>
        ))}
        {rv && <span className="ml-1 text-muted">±{rv.window_half_width_days} d window · baseline {rv.baseline_method} · SAP {rv.sap_version}</span>}
      </div>
      <div className="flex items-center gap-3">
        {arms.map((a) => (
          <span key={a.arm} title={`FAS ${a.fas} · derived ${a.derived} · missing ${pct(a.missingness)}`}>
            <b>{a.arm === "CSL101" ? "CSL-101" : "Placebo"}</b> {num(a.mean_pchg, 1)}% <span className="text-muted">(n={a.derived})</span>
          </span>
        ))}
      </div>
      <div className="ml-auto flex items-center gap-1.5">
        {overview?.verification && (
          <Chip tone={overview.verification.status === "PASS" ? "good" : "bad"} title="named participants match their hand-worked expected results">
            <ShieldCheck className="h-3 w-3" /> oracle {overview.verification.status}
          </Chip>
        )}
        {warnings.length > 0 && (
          <Chip tone={errors.length ? "bad" : "warn"}
            title={[...warnings.map((w) => `${w.check_id}: ${w.n_violations}`),
              pop ? `screened ${pop.screened} · randomized ${pop.randomized} · PPS ${pop.pps} · enrolled in error ${pop.enrolled_in_error}` : ""].join("\n")}>
            <TriangleAlert className="h-3 w-3" /> {warnings.reduce((s, w) => s + Number(w.n_violations), 0)} DQ
          </Chip>
        )}
        <Chip tone="warn" title="Synthetic studies of a fictional compound. SDTM-/ADaM-shaped, not submission-ready. Descriptive only.">
          <FlaskConical className="h-3 w-3" /> synthetic
        </Chip>
      </div>
      {overviewError && <div className="w-full text-destructive">{overviewError}</div>}
    </div>
  );
}
