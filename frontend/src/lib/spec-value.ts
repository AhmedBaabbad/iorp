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
  if (Array.isArray(value)) return value.map(formatSpecValue).join(", ");
  return typeof value === "object" ? Object.entries(value).map(([key, item]) => `${key}: ${formatSpecValue(item)}`).join("; ") : String(value);
}

export type SpecDisplayProperty = {key:string;name_ar:string;name_en:string;unit?:string|null;options?:{value:string;label_ar:string;label_en:string}[]|null};
export type SpecDisplayOptions = {properties?:readonly SpecDisplayProperty[];locale?:string;label?:(key:string)=>string;unitLabel?:(unit:string)=>string;separator?:string;valuesOnly?:boolean};
/** One specification renderer: template order, translated names/choices, formatted values and units. */
export function formatSpecification(spec:Record<string,unknown>|null|undefined,options:SpecDisplayOptions={}):string {
  return specificationRows(spec,options).map(row=>options.valuesOnly?row.valueWithUnit:row.text).join(options.separator??" · ");
}
export function specificationRows(spec:Record<string,unknown>|null|undefined,options:SpecDisplayOptions={}) {
  const properties=options.properties??[],ar=options.locale==="ar";
  const keys=[...properties.map(p=>p.key),...Object.keys(spec??{}).filter(key=>!properties.some(p=>p.key===key))];
  return keys.filter((key,index)=>keys.indexOf(key)===index&&spec?.[key]!=null&&spec[key]!=="").map(key=>{
    const raw=spec![key],property=properties.find(p=>p.key===key),choice=property?.options?.find(o=>o.value===raw);
    const name=property?(ar?property.name_ar:property.name_en):(options.label?.(key)??key);
    const displayValue=choice?(ar?choice.label_ar:choice.label_en):raw;
    const value=formatSpecValue(displayValue);
    const unit=property?.unit?(options.unitLabel?.(property.unit)??property.unit):"";
    const valueWithUnit=[value,unit].filter(Boolean).join(" ");
    return {key,name,value,displayValue,unit,valueWithUnit,text:`${name}: ${valueWithUnit}`,range:isSpecRange(raw)};
  });
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
