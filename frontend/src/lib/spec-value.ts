export type SpecRange = { min: number; max: number };
export class SpecValueError extends Error { code: string; constructor(code: string) { super(code); this.code = code; } }

export function normalizeSpecDigits(text: string): string {
  return text.replace(/[٠-٩۰-۹]/g, c => String(c.charCodeAt(0) - (c <= "٩" ? 0x660 : 0x6f0)))
    .replace(/٫/g, ".").replace(/−/g, "-").trim();
}
const number = "[+-]?(?:\\d+(?:\\.\\d+)?|\\.\\d+)(?:[eE][+-]?\\d+)?";
const scalarPattern = new RegExp(`^${number}$`);
const rangePattern = new RegExp(`^(${number})\\s*[-–]\\s*(${number})$`);
export function parseNumericSpec(text: string, allowsRange = false): number | SpecRange {
  const value = normalizeSpecDigits(text);
  if (scalarPattern.test(value) && Number.isFinite(Number(value))) return Number(value);
  const range = rangePattern.exec(value);
  if (!range) throw new SpecValueError("SPEC_RANGE_NUMBER");
  if (!allowsRange) throw new SpecValueError("SPEC_RANGE_NOT_ALLOWED");
  const min = Number(range[1]), max = Number(range[2]);
  if (!Number.isFinite(min) || !Number.isFinite(max)) throw new SpecValueError("SPEC_RANGE_NUMBER");
  if (min > max) throw new SpecValueError("SPEC_RANGE_REVERSED");
  return min === max ? min : { min, max };
}
export function numericSpecOrText(text: string, allowsRange = false): unknown {
  try { return parseNumericSpec(text, allowsRange); } catch { return text; }
}
export function isSpecRange(value: unknown): value is SpecRange {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const r = value as SpecRange;
  return Object.keys(r).length === 2 && typeof r.min === "number" && typeof r.max === "number" &&
    Number.isFinite(r.min) && Number.isFinite(r.max) && r.min <= r.max;
}
export function formatSpecValue(value: unknown): string {
  if (isSpecRange(value)) {
    if (value.min === value.max) return String(value.min);
    const places = Math.max(0, ...[value.min, value.max].map(n => { const [coefficient, exponent = "0"] = String(n).split("e"); return (coefficient.split(".")[1] ?? "").length - Number(exponent); }));
    return `${(places <= 100 ? value.min.toFixed(places) : String(value.min))} – ${(places <= 100 ? value.max.toFixed(places) : String(value.max))}`;
  }
  if (value == null) return "";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

export function formatThickness(minimum: string | number | null, maximum?: string | number | null): string {
  if (minimum == null) return "";
  return formatSpecValue(maximum == null ? Number(minimum) : { min: Number(minimum), max: Number(maximum) });
}

export function thicknessFields(text: string): { thickness_mm: string | null; thickness_max_mm: string | null } {
  if (!text.trim()) return { thickness_mm: null, thickness_max_mm: null };
  const value = parseNumericSpec(text, true);
  return isSpecRange(value) ? { thickness_mm: String(value.min), thickness_max_mm: String(value.max) }
    : { thickness_mm: String(value), thickness_max_mm: null };
}
