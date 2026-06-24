/** Serialize a list of flat records to CSV and trigger a browser download. Quant users want
    the current table offline; the uniform row shapes across views make this generic. */

function cell(value: unknown): string {
  if (value == null) return "";
  if (Array.isArray(value)) return `"${value.join(" ")}"`;
  const s = String(value);
  // Quote if the value contains a comma, quote, or newline; double internal quotes.
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** Build CSV text from records. Columns are the union of keys, ordered by first appearance,
    skipping nested objects (only scalar/array fields make sense in a flat export). */
export function toCsv(rows: Record<string, unknown>[]): string {
  if (rows.length === 0) return "";
  const cols: string[] = [];
  for (const row of rows) {
    for (const k of Object.keys(row)) {
      const v = row[k];
      const scalar = v == null || typeof v !== "object" || Array.isArray(v);
      if (scalar && !cols.includes(k)) cols.push(k);
    }
  }
  const header = cols.join(",");
  const body = rows.map((r) => cols.map((c) => cell(r[c])).join(",")).join("\n");
  return `${header}\n${body}`;
}

export function downloadCsv(filename: string, rows: Record<string, unknown>[]): void {
  const blob = new Blob([toCsv(rows)], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename.endsWith(".csv") ? filename : `${filename}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
