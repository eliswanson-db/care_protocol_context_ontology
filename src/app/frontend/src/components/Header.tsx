import { Activity, FlaskConical, Moon, Settings, Sun } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { Meta } from "../api";
import { useSettings } from "../settings";

function SettingsMenu() {
  const { simple, setSimple } = useSettings();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);
  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className={`rounded-md border p-1.5 hover:text-fg ${simple ? "border-primary text-primary" : "border-border text-muted"}`}
        aria-label="Settings"
        title="Settings"
      >
        <Settings className="h-4 w-4" />
      </button>
      {open && (
        <div className="absolute right-0 z-20 mt-1.5 w-72 rounded-lg border border-border bg-surface p-3 shadow-lg">
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted">Settings</div>
          <label className="flex cursor-pointer items-start gap-2.5">
            <input type="checkbox" className="mt-0.5 h-4 w-4 accent-[var(--primary)]" checked={simple}
              onChange={(e) => setSimple(e.target.checked)} />
            <span>
              <span className="block text-[13px] font-semibold">Simple mode</span>
              <span className="block text-[11.5px] leading-snug text-muted">
                Three questions; Genie Ontology, RAG and the Ontobricks graph only; one MET and one NOT_MET patient.
              </span>
            </span>
          </label>
        </div>
      )}
    </div>
  );
}

export function Header({ meta }: { meta: Meta | null }) {
  const { simple } = useSettings();
  const [dark, setDark] = useState(
    () => window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false
  );
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  }, [dark]);

  return (
    <header className="flex items-center justify-between border-b border-border bg-surface px-5 py-3">
      <div className="flex items-center gap-2.5">
        <Activity className="h-6 w-6 text-primary" />
        <div>
          <div className="text-base font-bold leading-tight">Care Protocol Context</div>
          <div className="text-[12px] text-muted">The semantic throughline — one record through every layer</div>
        </div>
      </div>
      <div className="flex items-center gap-2 text-xs">
        {meta && (
          <>
            <span className="rounded-md border border-border bg-surface-2 px-2 py-1 font-medium uppercase tracking-wide">
              arm: {meta.arm}
            </span>
            <span className="rounded-md border border-border bg-surface-2 px-2 py-1">MY {meta.measurement_year}</span>
            <span className="flex items-center gap-1 rounded-md border border-warning/40 px-2 py-1 text-warning">
              <FlaskConical className="h-3.5 w-3.5" /> synthetic
            </span>
          </>
        )}
        {simple && (
          <span className="rounded-md bg-primary/15 px-2 py-1 font-semibold text-primary">simple mode</span>
        )}
        <SettingsMenu />
        <button
          onClick={() => setDark((d) => !d)}
          className="rounded-md border border-border p-1.5 text-muted hover:text-fg"
          aria-label="Toggle theme"
        >
          {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
      </div>
    </header>
  );
}
