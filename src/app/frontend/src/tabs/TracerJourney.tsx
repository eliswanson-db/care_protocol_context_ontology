import { AlertTriangle, ChevronDown } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, type GenieResult, type Journey, type OntobricksResult, type RagResult, type RetrievalResult, type Tracer } from "../api";
import { AnswerPanel } from "../components/AnswerPanel";
import { FlowDiagram } from "../components/FlowDiagram";
import { NodeDetail } from "../components/NodeDetail";
import { RetrievalRow, type LiveStatus } from "../components/RetrievalRow";
import { TracerPicker } from "../components/TracerPicker";

function Section({
  n,
  title,
  hint,
  open,
  onToggle,
  children,
}: {
  n: string;
  title: string;
  hint: string;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <section>
      <button onClick={onToggle} className="mb-3.5 flex w-full items-center gap-2.5 text-left">
        <ChevronDown className={`h-4 w-4 shrink-0 text-muted transition ${open ? "" : "-rotate-90"}`} />
        <span className="rounded bg-primary/15 px-1.5 py-0.5 text-[12px] font-bold text-primary">{n}</span>
        <h2 className="text-[17px] font-bold tracking-tight">{title}</h2>
        <span className="truncate text-[13px] text-muted">{hint}</span>
      </button>
      {open && children}
    </section>
  );
}

export function TracerJourney() {
  const [tracers, setTracers] = useState<Tracer[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [journey, setJourney] = useState<Journey | null>(null);
  const [retrieval, setRetrieval] = useState<RetrievalResult | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingJourney, setLoadingJourney] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [open, setOpen] = useState<Record<string, boolean>>({ build: true, retrieval: false, answer: false });
  const toggle = (k: string) => setOpen((o) => ({ ...o, [k]: !o[k] }));

  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [activeClaim, setActiveClaim] = useState<string | null>(null);

  const [genieStatus, setGenieStatus] = useState<LiveStatus>("idle");
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

  const [ragStatus, setRagStatus] = useState<LiveStatus>("idle");
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

  const [graphStatus, setGraphStatus] = useState<LiveStatus>("idle");
  const [graphResult, setGraphResult] = useState<OntobricksResult | null>(null);
  const [graphError, setGraphError] = useState<string | null>(null);

  const askGraph = () => {
    if (!selected) return;
    setGraphStatus("loading");
    setGraphError(null);
    api.ontobricks(selected)
      .then((r) => {
        setGraphResult(r);
        setGraphStatus("done");
      })
      .catch((e) => {
        setGraphError(String(e));
        setGraphStatus("error");
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
    setGraphStatus("idle");
    setGraphResult(null);
    setGraphError(null);
    setRetrieval(null);
    api.journey(selected)
      .then(setJourney)
      .catch((e) => setError(String(e)))
      .finally(() => setLoadingJourney(false));
    api.retrieval(selected)
      .then(setRetrieval)
      .catch(() => setRetrieval(null));
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
      <TracerPicker
        tracers={tracers}
        selected={selected}
        onSelect={setSelected}
        loading={loadingList}
        collapsed={!sidebarOpen}
        onToggle={() => setSidebarOpen((v) => !v)}
      />
      <main className="min-w-0 flex-1 overflow-y-auto px-6 py-5">
        {picked && (
          <div className="mb-6">
            <h1 className="text-2xl font-bold tracking-tight">Follow one patient from raw code to governed answer</h1>
            <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl border border-border bg-surface px-4 py-3">
              <span className="font-mono text-xl font-bold">{picked.patient_id.slice(0, 8)}</span>
              <span className="rounded-md bg-primary/15 px-2.5 py-1 font-mono text-base font-semibold text-primary">
                {picked.dx_code}
              </span>
              <span className="text-[15px] text-muted">{picked.dx_desc}</span>
              <span className="text-[15px] font-medium text-muted">· {picked.clinic_id} · age {picked.age}</span>
              <span
                className={[
                  "ml-auto rounded-full px-3.5 py-1.5 text-sm font-bold",
                  picked.status === "NOT_MET"
                    ? "bg-destructive/15 text-destructive"
                    : "bg-success/15 text-success",
                ].join(" ")}
              >
                GSD {picked.status}
              </span>
            </div>
            {picked.gap_reason && (
              <p className="mt-2 text-[14px] text-muted">
                Care gap: <span className="font-medium text-fg">{picked.gap_reason}</span>
              </p>
            )}
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
          <div className="space-y-6">
            <Section
              n="01"
              title="The build"
              hint="raw code → bronze → silver → gold → ontology · click a node"
              open={open.build}
              onToggle={() => toggle("build")}
            >
              <FlowDiagram
                stages={journey.stages}
                activePath={activePath}
                selectedKey={selectedNode}
                onSelect={(k) => {
                  setActiveClaim(null);
                  setSelectedNode((cur) => (cur === k ? null : k));
                }}
              />
              {detailStage && selected && (
                <NodeDetail key={`${selected}-${detailStage.key}`} stage={detailStage} patientId={selected}
                  onClose={() => setSelectedNode(null)} />
              )}
            </Section>

            <Section
              n="02"
              title="Retrieval — the same question, five ways"
              hint="metric view · closure · Genie · RAG · graph"
              open={open.retrieval}
              onToggle={() => toggle("retrieval")}
            >
              <RetrievalRow
                retrieval={retrieval}
                activeModes={activeModes}
                genie={{ status: genieStatus, result: genieResult, error: genieError, onAsk: askGenie }}
                rag={{ status: ragStatus, result: ragResult, error: ragError, onAsk: askRag }}
                graph={{ status: graphStatus, result: graphResult, error: graphError, onAsk: askGraph }}
              />
            </Section>

            <Section
              n="03"
              title="The answer"
              hint="trace any claim back to its source"
              open={open.answer}
              onToggle={() => toggle("answer")}
            >
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
            </Section>
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
