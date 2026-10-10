// A line specification (quotations, shipments, ...) <-> "property | value" rows. Pure: no React, tested by tests/spec-rows.test.mjs.
export type Row = { key: string; value: string };

/** A specification value as typed: numbers and true/false keep their type (production reads e.g. width_mm as a number). */
export function parseSpecValue(text: string): unknown {
  const value = text.trim();
  if (/^-?\d+(\.\d+)?$/.test(value)) return Number(value);
  if (value === "true" || value === "false") return value === "true";
  if (/^[[{]/.test(value)) {
    try { return JSON.parse(value); } catch { /* kept as text */ }
  }
  return value;
}

export function specToRows(json: string): Row[] {
  if (!json.trim()) return [];
  try {
    const parsed = JSON.parse(json) as Record<string, unknown>;
    return Object.entries(parsed).map(([key, value]) => ({ key, value: typeof value === "string" ? value : JSON.stringify(value) }));
  } catch {
    return [];
  }
}

/** Rows with a property name become the specification JSON (empty when there are none). */
export function rowsToSpec(rows: Row[]): string {
  const entries = rows.filter((row) => row.key.trim()).map((row) => [row.key.trim(), parseSpecValue(row.value)] as const);
  return entries.length ? JSON.stringify(Object.fromEntries(entries)) : "";
}

/** A property of a product's specification template (master data): the value a line stores under `key`. */
export type SpecTemplateProperty = {
  key: string; name_ar: string; name_en: string; kind: "number" | "text" | "choice"; unit: string | null; required: boolean;
  options: { value: string; label_ar: string; label_en: string }[] | null;
};

/** The template's values first, in its order, then any other row: the order a document prints. Empty values are left out. */
export function templateSpec(template: SpecTemplateProperty[], values: Record<string, string>, extra: Row[]): string {
  const entries: [string, unknown][] = [];
  for (const prop of template) {
    const text = (values[prop.key] ?? "").trim();
    if (text) entries.push([prop.key, prop.kind === "number" ? parseSpecValue(text) : text]);
  }
  const known = new Set(template.map(p => p.key));
  for (const row of extra) if (row.key.trim() && !known.has(row.key.trim())) entries.push([row.key.trim(), parseSpecValue(row.value)]);
  return entries.length ? JSON.stringify(Object.fromEntries(entries)) : "";
}
