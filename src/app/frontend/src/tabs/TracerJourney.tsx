import { AlertTriangle } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Journey, type Tracer } from "../api";
import { StageCard } from "../components/StageCard";
import { TracerPicker } from "../components/TracerPicker";

export function TracerJourney() {
  const [tracers, setTracers] = useState<Tracer[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [journey, setJourney] = useState<Journey | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingJourney, setLoadingJourney] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.tracers()
      .then((r) => {
        setTracers(r.tracers);
        if (r.tracers.length) setSelected(r.tracers[0].patient_id);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoadingList(false));
  }, []);

  useEffect(() => {
    if (!selected) return;
    setLoadingJourney(true);
    setError(null);
    api.journey(selected)
      .then(setJourney)
      .catch((e) => setError(String(e)))
      .finally(() => setLoadingJourney(false));
  }, [selected]);

  const picked = tracers.find((t) => t.patient_id === selected);

  return (
    <div className="flex min-h-0 flex-1">
      <TracerPicker tracers={tracers} selected={selected} onSelect={setSelected} loading={loadingList} />
      <main className="min-w-0 flex-1 overflow-y-auto px-6 py-5">
        {picked && (
          <div className="mb-5">
            <h1 className="text-lg font-semibold">
              Follow one patient from raw code to governed answer
            </h1>
            <p className="mt-1 text-sm text-muted">
              Patient <span className="font-mono">{picked.patient_id.slice(0, 8)}</span> ·{" "}
              <span className="font-mono text-primary">{picked.dx_code}</span> {picked.dx_desc} ·{" "}
              {picked.clinic_id} ·{" "}
              <span className={picked.status === "NOT_MET" ? "font-semibold text-destructive" : "font-semibold text-success"}>
                GSD {picked.status}
              </span>
              {picked.gap_reason ? ` — ${picked.gap_reason}` : ""}
            </p>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            <AlertTriangle className="h-4 w-4" /> {error}
          </div>
        )}

        {loadingJourney && (
          <div className="space-y-3">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="ml-8 h-20 animate-pulse rounded-lg bg-surface-2" />
            ))}
          </div>
        )}

        {!loadingJourney && !error && journey && (
          <div>
            {journey.stages.map((st, i) => (
              <StageCard key={st.key} stage={st} index={i} last={i === journey.stages.length - 1} />
            ))}
          </div>
        )}

        {!loadingJourney && !error && !journey && !loadingList && (
          <div className="rounded-md border border-border bg-surface px-4 py-8 text-center text-sm text-muted">
            Select a patient to trace their journey.
          </div>
        )}
      </main>
    </div>
  );
}
