import { AlertTriangle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, type GenieResult, type Journey, type RagResult, type Tracer } from "../api";
import { AnswerPanel } from "../components/AnswerPanel";
import { FlowDiagram } from "../components/FlowDiagram";
import { GenieLive, type GenieStatus } from "../components/GenieLive";
import { NodeDetail } from "../components/NodeDetail";
import { RagLive, type RagStatus } from "../components/RagLive";
import { RetrievalModes } from "../components/RetrievalModes";
import { TracerPicker } from "../components/TracerPicker";

function SectionLabel({ n, title, hint }: { n: string; title: string; hint: string }) {
  return (
    <div className="mb-3 flex items-baseline gap-2">
      <span className="text-[11px] font-semibold text-primary">{n}</span>
      <h2 className="text-sm font-semibold">{title}</h2>
      <span className="text-xs text-muted">{hint}</span>
    </div>
  );
}

export function TracerJourney() {
  const [tracers, setTracers] = useState<Tracer[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [journey, setJourney] = useState<Journey | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingJourney, setLoadingJourney] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [activeClaim, setActiveClaim] = useState<string | null>(null);

  const [genieStatus, setGenieStatus] = useState<GenieStatus>("idle");
  const [genieResult, setGenieResult] = useState<GenieResult | null>(null);
  const [genieError, setGenieError] = useState<string | null>(null);

  const askGenie = () => {
    if (!selected) return;
    setGenieStatus("loading");
    setGenieError(null);
    api.genie(selected)
      .then((r) => {
        setGenieResult(r);
        setGenieStatus("done");
      })
      .catch((e) => {
        setGenieError(String(e));
        setGenieStatus("error");
      });
  };

  const [ragStatus, setRagStatus] = useState<RagStatus>("idle");
  const [ragResult, setRagResult] = useState<RagResult | null>(null);
  const [ragError, setRagError] = useState<string | null>(null);

  const askRag = () => {
    if (!selected) return;
    setRagStatus("loading");
    setRagError(null);
    api.rag(selected)
      .then((r) => {
        setRagResult(r);
        setRagStatus("done");
      })
      .catch((e) => {
        setRagError(String(e));
        setRagStatus("error");
      });
  };

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
    setSelectedNode(null);
    setActiveClaim(null);
    setGenieStatus("idle");
    setGenieResult(null);
    setGenieError(null);
    setRagStatus("idle");
    setRagResult(null);
    setRagError(null);
    api.journey(selected)
      .then(setJourney)
      .catch((e) => setError(String(e)))
      .finally(() => setLoadingJourney(false));
  }, [selected]);

  const picked = tracers.find((t) => t.patient_id === selected);

  const claim = useMemo(
    () => journey?.answer.claims.find((c) => c.id === activeClaim) ?? null,
    [journey, activeClaim],
  );
  const activePath = useMemo(() => new Set(claim?.stage_path ?? []), [claim]);
  const activeModes = useMemo(() => new Set(claim?.modes ?? []), [claim]);
  const stageTitle = (key: string) =>
    journey?.stages.find((s) => s.key === key)?.title ?? key;
  const detailStage = journey?.stages.find((s) => s.key === selectedNode) ?? null;

  return (
    <div className="flex min-h-0 flex-1">
      <TracerPicker tracers={tracers} selected={selected} onSelect={setSelected} loading={loadingList} />
      <main className="min-w-0 flex-1 overflow-y-auto px-6 py-5">
        {picked && (
          <div className="mb-5">
            <h1 className="text-lg font-semibold">Follow one patient from raw code to governed answer</h1>
            <p className="mt-1 text-sm text-muted">
              Patient <span className="font-mono">{picked.patient_id.slice(0, 8)}</span> ·{" "}
              <span className="font-mono text-primary">{picked.dx_code}</span> {picked.dx_desc} · {picked.clinic_id} ·{" "}
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
            <div className="h-28 animate-pulse rounded-xl bg-surface-2" />
            <div className="h-36 animate-pulse rounded-xl bg-surface-2" />
            <div className="h-32 animate-pulse rounded-xl bg-surface-2" />
          </div>
        )}

        {!loadingJourney && !error && journey && (
          <div className="space-y-7">
            <section>
              <SectionLabel n="01" title="The build" hint="one record through every semantic layer — click a node" />
              <FlowDiagram
                stages={journey.stages}
                activePath={activePath}
                selectedKey={selectedNode}
                onSelect={(k) => {
                  setActiveClaim(null);
                  setSelectedNode((cur) => (cur === k ? null : k));
                }}
              />
              {detailStage && <NodeDetail stage={detailStage} onClose={() => setSelectedNode(null)} />}
            </section>

            <section>
              <SectionLabel n="02" title="Retrieval" hint="five ways to answer the same question — value · impact · mode" />
              <RetrievalModes
                activeModes={activeModes}
                onAskGenie={askGenie}
                genieBusy={genieStatus === "loading"}
                onAskRag={askRag}
                ragBusy={ragStatus === "loading"}
              />
            </section>

            <section>
              <SectionLabel n="03" title="The answer" hint="model a question, then trace any claim back to source" />
              <AnswerPanel
                question={journey.answer.question}
                claims={journey.answer.claims}
                activeClaimId={activeClaim}
                onSelect={(id) => {
                  setSelectedNode(null);
                  setActiveClaim(id);
                }}
                stageTitle={stageTitle}
              />
            </section>

            <section>
              <SectionLabel n="04" title="Genie One, live" hint="the same answer via natural language — grounded + cited" />
              <GenieLive status={genieStatus} result={genieResult} error={genieError} onAsk={askGenie} />
            </section>

            <section>
              <SectionLabel n="05" title="A4 RAG, live" hint="the care-protocol passage behind the rule — RLS-governed" />
              <RagLive status={ragStatus} result={ragResult} error={ragError} onAsk={askRag} />
            </section>
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
