import { KILOGRAMS } from "@/lib/units";

export const isWeightUnit = (unit: string) => Object.hasOwn(KILOGRAMS, unit);
export type WeightLine = {
  quantity: string; unit: string; unit_net_weight: string; weight_unit: string;
  legacy_weight?: string | null; legacy_quantity?: string; legacy_unit?: string; legacy_weight_unit?: string;
};
export const unchangedLegacyQuantity = (line: WeightLine) => line.legacy_quantity != null &&
  line.unit === line.legacy_unit && Number(line.quantity) === Number(line.legacy_quantity);
// Match Decimal/Numeric(14,3) half-even rounding for the read-only preview.
const rounded = (value: number) => {
  const scaled = value * 1000, floor = Math.floor(scaled);
  const half = Math.abs(scaled - floor - 0.5) <= Number.EPSILON * Math.max(1, Math.abs(scaled)) * 4;
  return (half ? floor + (floor % 2) : Math.round(scaled)) / 1000;
};
export function lineNet(line: WeightLine): { value: number; unit: string } | null {
  if (!line.unit_net_weight.trim() && line.legacy_weight != null && unchangedLegacyQuantity(line)) {
    return { value: Number(line.legacy_weight), unit: line.legacy_weight_unit ?? line.weight_unit };
  }
  if (!line.quantity.trim() || !Number.isFinite(Number(line.quantity))) return null;
  if (isWeightUnit(line.unit)) return { value: rounded(Number(line.quantity) * KILOGRAMS[line.unit]), unit: "kg" };
  if (!line.unit_net_weight.trim() || !Number.isFinite(Number(line.unit_net_weight))) return null;
  return { value: rounded(Number(line.quantity) * Number(line.unit_net_weight)), unit: line.weight_unit };
}
export function totalNetKg(lines: WeightLine[]): number {
  return rounded(lines.reduce((total, line) => { const net = lineNet(line); return total + (net ? net.value * KILOGRAMS[net.unit] : 0); }, 0));
}
export const grossKg = (value: string, unit: string) => value.trim() && Number.isFinite(Number(value)) ? rounded(Number(value) * KILOGRAMS[unit]) : null;
