import { ChevronDown } from "lucide-react";
import { useState } from "react";

// A self-contained collapsible section: a clickable header with a chevron + optional hint.
export function Collapsible({
  title,
  hint,
  defaultOpen = true,
  children,
}: {
  title: string;
  hint?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section>
      <button onClick={() => setOpen((o) => !o)} className="mb-3 flex w-full items-center gap-2.5 text-left">
        <ChevronDown className={`h-4 w-4 shrink-0 text-muted transition ${open ? "" : "-rotate-90"}`} />
        <h2 className="text-[17px] font-bold tracking-tight">{title}</h2>
        {hint ? <span className="truncate text-[13px] text-muted">{hint}</span> : null}
      </button>
      {open && children}
    </section>
  );
}
