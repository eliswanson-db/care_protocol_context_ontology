export function DataTable({ data }: { data: unknown }) {
  if (data === null || data === undefined) return <span className="text-muted">—</span>;
  const rows = Array.isArray(data) ? data : [data];
  if (rows.length === 0) return <span className="text-muted">no rows</span>;
  const keys = Object.keys(rows[0] as Record<string, unknown>);
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full text-left text-xs">
        <thead className="bg-surface-2 text-muted">
          <tr>
            {keys.map((k) => (
              <th key={k} className="whitespace-nowrap px-2 py-1 font-medium">{k}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-border">
              {keys.map((k) => {
                const v = (r as Record<string, unknown>)[k];
                return (
                  <td key={k} className="whitespace-nowrap px-2 py-1 font-mono">
                    {v === null || v === undefined ? <span className="text-muted">null</span> : String(v)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
