import { RefreshCw, X } from "lucide-react";
import { useEffect, useState } from "react";
import { readinessApi, type Readiness } from "../lsApi";
import { Chip, toneFor } from "../tabs/ls/ui";

// Deployment readiness for BOTH demos, evaluated live (server/readiness.py). Nothing is hidden: missing assets,
// failed runs and manual-only steps all show with their reason.
export function ReadinessDrawer({ onClose }: { onClose: () => void }) {
  const [data, setData] = useState<Readiness[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const load = (refresh = false) => {
    setBusy(true);
    readinessApi.all(refresh).then((r) => setData(r.demos)).catch((e) => setError(String(e))).finally(() => setBusy(false));
  };
  useEffect(() => load(), []);
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/30" onClick={onClose}>
      <div className="h-full w-[720px] max-w-full overflow-y-auto bg-surface p-4 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-bold">Deployment readiness</h2>
          <div className="flex gap-1.5">
            <button onClick={() => load(true)} className="rounded-md border border-border p-1.5 text-muted hover:text-fg" aria-label="refresh">
              <RefreshCw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} />
            </button>
            <button onClick={onClose} className="rounded-md border border-border p-1.5 text-muted hover:text-fg" aria-label="close"><X className="h-4 w-4" /></button>
          </div>
        </div>
        {error && <div className="text-sm text-destructive">{error}</div>}
        {!data && !error && <div className="text-sm text-muted">Checking every component live…</div>}
        {data?.map((d) => (
          <section key={d.demo_id} className="mb-5">
            <div className="mb-1.5 flex flex-wrap items-center gap-2">
              <h3 className="text-[13px] font-semibold">{d.display_name}</h3>
              {Object.entries(d.summary).map(([s, n]) => <Chip key={s} tone={toneFor(s)}>{n} {s}</Chip>)}
              <span className="ml-auto text-[11px] text-muted">checked {d.checked_at}</span>
            </div>
            <table className="w-full text-[12px]">
              <tbody>
                {d.components.map((c) => (
                  <tr key={c.id} className="border-b border-border/60 align-top">
                    <td className="w-44 py-1.5 pr-2 font-medium">{c.label}</td>
                    <td className="w-48 py-1.5 pr-2"><Chip tone={toneFor(c.state)}>{c.state}</Chip></td>
                    <td className="py-1.5 text-muted">{c.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ))}
      </div>
    </div>
  );
}
