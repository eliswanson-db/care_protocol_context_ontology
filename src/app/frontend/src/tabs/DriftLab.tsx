import { AlertTriangle, Bell, Stethoscope, TrendingDown } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Drift, type DriftTraj } from "../api";

function TrajChart({ traj, baseline, transitionMonth }: { traj: DriftTraj[]; baseline: number; transitionMonth: string | null }) {
  const W = 680, H = 200, padL = 36, padB = 26, padT = 10, padR = 12;
  const iw = W - padL - padR, ih = H - padT - padB;
  const pts = traj.map((t, i) => {
    const x = padL + (traj.length === 1 ? iw / 2 : (i / (traj.length - 1)) * iw);
    const y = padT + (1 - parseFloat(t.rate)) * ih;
    return { x, y, t };
  });
  const line = pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
  const yBase = padT + (1 - baseline) * ih;
  const txIdx = transitionMonth ? traj.findIndex((t) => t.month.slice(0, 7) === transitionMonth.slice(0, 7)) : -1;
  const txX = txIdx >= 0 ? padL + (txIdx / (traj.length - 1)) * iw : null;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="monthly adherence trajectory">
      {[0, 0.25, 0.5, 0.75, 1].map((g) => {
        const y = padT + (1 - g) * ih;
        return (
          <g key={g}>
            <line x1={padL} y1={y} x2={W - padR} y2={y} stroke="var(--border)" strokeWidth="1" />
            <text x={padL - 6} y={y + 3} textAnchor="end" fontSize="9" fill="var(--muted)">{g * 100}%</text>
          </g>
        );
      })}
      {/* own baseline */}
      <line x1={padL} y1={yBase} x2={W - padR} y2={yBase} stroke="var(--success)" strokeWidth="1.5" strokeDasharray="5 4" />
      <text x={W - padR} y={yBase - 4} textAnchor="end" fontSize="9" fill="var(--success)">own baseline {(baseline * 100).toFixed(0)}%</text>
      {/* PCP transition marker */}
      {txX != null && (
        <>
          <line x1={txX} y1={padT} x2={txX} y2={padT + ih} stroke="var(--warning)" strokeWidth="1.5" strokeDasharray="3 3" />
          <text x={txX + 3} y={padT + 10} fontSize="9" fill="var(--warning)">PCP handoff</text>
        </>
      )}
      <polyline points={line} fill="none" stroke="var(--primary)" strokeWidth="2" />
      {pts.map((p, i) => (
        <g key={i}>
          <circle cx={p.x} cy={p.y} r="3" fill="var(--primary)" />
          <text x={p.x} y={H - padB + 14} textAnchor="middle" fontSize="8" fill="var(--muted)">{p.t.month.slice(5, 7)}</text>
        </g>
      ))}
    </svg>
  );
}

export function DriftLab() {
  const [d, setD] = useState<Drift | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.drift().then(setD).catch((e) => setError(String(e)));
  }, []);

  if (error)
    return (
      <div className="m-6 flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
        <AlertTriangle className="h-4 w-4" /> {error}
      </div>
    );
  if (!d) return <div className="m-6 h-96 animate-pulse rounded-xl bg-surface-2" />;

  const maxRate = Math.max(...d.annual_ranking.map((r) => parseFloat(r.rate)), 0.0001);
  const worstCaseMix = d.casemix.find((c) => c.clinic_id === d.worst_clinic);
  const topCaseMix = d.casemix[0];

  return (
    <main className="flex-1 overflow-y-auto px-6 py-5">
      <div className="mb-5">
        <h1 className="text-lg font-semibold">A Monday with Genie — the drift nobody asked about</h1>
        <p className="mt-1 text-sm text-muted">
          Protocol Step-3 = an A1c recheck within 90 days of an at/above-target result. The annual ranking and the
          operational question point at <span className="font-semibold">different clinics</span>. MY {d.measurement_year}.
        </p>
      </div>

      {/* Beat 1 — the trap */}
      <section className="mb-7">
        <h2 className="mb-2 text-sm font-semibold">01 · The annual ranking (the trap)</h2>
        <div className="space-y-1.5">
          {d.annual_ranking.map((r) => {
            const isAnnualWorst = r.clinic_id === d.annual_worst?.clinic_id;
            const isDrift = r.clinic_id === d.worst_clinic;
            return (
              <div key={r.clinic_id} className="flex items-center gap-3">
                <div className={`w-20 shrink-0 text-xs ${isDrift ? "font-semibold text-warning" : ""}`}>{r.clinic_id}</div>
                <div className="relative h-5 flex-1 overflow-hidden rounded bg-surface-2">
                  <div className={`h-full rounded ${isDrift ? "bg-warning/60" : "bg-primary/60"}`} style={{ width: `${(parseFloat(r.rate) / maxRate) * 100}%` }} />
                  <div className="absolute inset-0 flex items-center px-2 text-[10px] font-medium">{(parseFloat(r.rate) * 100).toFixed(1)}%</div>
                </div>
                <div className="w-44 shrink-0 text-[10px] text-muted">
                  {isAnnualWorst ? "← lowest overall (the obvious flag)" : isDrift ? `← drifted clinic, but #${d.worst_annual_rank} here` : ""}
                </div>
              </div>
            );
          })}
        </div>
        <p className="mt-2 text-xs text-muted">
          An annual ranking says <span className="font-mono">{d.annual_worst?.clinic_id}</span> is worst. Correct for the
          question as literally asked — and the wrong clinic to act on.
        </p>
      </section>

      {/* Beat 2 — the watch noticed */}
      {d.worst && (
        <section className="mb-7">
          <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
            <Bell className="h-4 w-4 text-warning" /> 02 · Nobody asked; the Weekly Protocol Watch noticed
          </h2>
          <div className="rounded-xl border border-warning/40 bg-warning/5 p-4">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-2xl font-semibold text-warning">{d.worst.clinic_id}</span>
              <span className="rounded bg-warning/20 px-2 py-0.5 text-xs font-semibold text-warning">{d.worst.severity}</span>
              <TrendingDown className="h-5 w-5 text-destructive" />
              <span className="text-sm">
                trailing <span className="font-semibold">{(parseFloat(d.worst.trailing_rate) * 100).toFixed(0)}%</span> vs its{" "}
                <span className="font-semibold">own</span> baseline {(parseFloat(d.worst.baseline) * 100).toFixed(0)}% —
                a <span className="font-semibold text-destructive">{(parseFloat(d.worst.delta) * 100).toFixed(0)} pp</span> drop
              </span>
            </div>
            <p className="mt-2 text-xs text-fg">
              Masked in the annual ranking at <span className="font-semibold">#{d.worst_annual_rank}</span> — a self-referential,
              trailing-window comparison (each clinic vs its own history) is what catches it. {d.worst.narrative}
            </p>
          </div>
        </section>
      )}

      {/* Beat 3 — trajectory */}
      {d.trajectory.length > 0 && d.worst && (
        <section className="mb-7">
          <h2 className="mb-2 text-sm font-semibold">03 · {d.worst_clinic} monthly trajectory — the cliff</h2>
          <div className="rounded-xl border border-border bg-surface p-3">
            <TrajChart traj={d.trajectory} baseline={parseFloat(d.worst.baseline)} transitionMonth={d.transition?.transition_date ?? null} />
          </div>
        </section>
      )}

      {/* Beat 4 — root cause */}
      <section className="mb-7">
        <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
          <Stethoscope className="h-4 w-4 text-primary" /> 04 · Root cause (and ruling out the confound)
        </h2>
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {d.transition && (
            <div className="rounded-xl border border-border bg-surface p-3">
              <div className="text-xs font-semibold uppercase tracking-wide text-muted">PCP transition</div>
              <div className="mt-1 text-sm">
                <span className="font-mono">{d.transition.change_type}</span> on{" "}
                <span className="font-semibold">{d.transition.transition_date}</span> · ~{d.transition.recovery_days}d recovery
              </div>
              <p className="mt-1.5 text-xs text-muted">{d.transition.narrative}</p>
            </div>
          )}
          <div className="rounded-xl border border-border bg-surface p-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-muted">Case-mix confound (ruled out)</div>
            <p className="mt-1 text-xs text-fg">
              A naive read blames complexity. But {d.worst_clinic}'s diabetic-complication share is{" "}
              <span className="font-semibold">{worstCaseMix ? (parseFloat(worstCaseMix.complication_share) * 100).toFixed(1) + "%" : "—"}</span>
              {topCaseMix ? ` — not the highest (${topCaseMix.clinic_id} leads at ${(parseFloat(topCaseMix.complication_share) * 100).toFixed(1)}%)` : ""}.
              It isn't the sickest panel, so case-mix doesn't explain the drop — the handoff does.
            </p>
          </div>
        </div>
        <p className="mt-3 text-[11px] text-muted">
          This is the "one layer that knows the protocol" beat: the drop, the own-baseline comparison, the panel/PCP
          transition, and the case-mix check are all governed assets Genie One can reason over and cite — live over the
          shared catalog.
        </p>
      </section>
    </main>
  );
}
