import { Activity, FlaskConical, Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import type { Meta } from "../api";

export function Header({ meta }: { meta: Meta | null }) {
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
