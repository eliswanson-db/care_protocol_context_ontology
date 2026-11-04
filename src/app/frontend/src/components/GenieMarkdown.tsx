// Tidy renderer for a Genie markdown answer: drops embedded query-table dumps + pipe tables + HTML comments
// (they're linked out), renders headings / bullets / bold / links. Shared by the Tracer card + the Arena.

function inline(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const re = /\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    if (m[1]) {
      parts.push(
        <a key={key++} href={m[2]} target="_blank" rel="noreferrer" className="text-primary underline underline-offset-2">
          {m[1]}
        </a>,
      );
    } else {
      parts.push(<strong key={key++} className="font-semibold text-fg">{m[3]}</strong>);
    }
    last = re.lastIndex;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export function GenieMarkdown({ md, className }: { md: string; className?: string }) {
  const lines: string[] = [];
  let inEmbed = false;
  for (const raw of md.split("\n")) {
    const t = raw.trim();
    if (/<!--\s*begin-embedded/.test(t)) { inEmbed = true; continue; }
    if (/<!--\s*end-embedded/.test(t)) { inEmbed = false; continue; }
    if (inEmbed) continue;
    if (t.startsWith("<!--") || t.startsWith("|")) continue; // drop comments + pipe tables
    lines.push(raw);
  }
  return (
    <div
      className={
        className ??
        "max-h-48 space-y-1 overflow-auto rounded-md border border-primary/25 bg-primary/5 p-2.5 text-[11.5px] leading-5 text-fg/90"
      }
    >
      {lines.map((line, i) => {
        const t = line.trim();
        if (!t) return <div key={i} className="h-1" />;
        if (/^#{1,6}\s/.test(t))
          return <div key={i} className="mt-1.5 text-[12.5px] font-bold text-fg">{inline(t.replace(/^#{1,6}\s/, ""))}</div>;
        if (/^[-*]\s/.test(t))
          return (
            <div key={i} className="flex gap-1.5">
              <span className="text-muted">•</span>
              <span>{inline(t.replace(/^[-*]\s/, ""))}</span>
            </div>
          );
        return <p key={i}>{inline(t)}</p>;
      })}
    </div>
  );
}
