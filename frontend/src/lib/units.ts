// Units of measure shared by every screen (quotations, shipments, ...); mirrors backend/app/core/units.py
// (tests/quote-units.test.mjs keeps both identical). Labels: common.units.<code> in the locale files.
export const UNIT_GROUPS = {
  count: ["piece", "unit", "pair", "set", "dozen", "lot"],
  packaging: ["roll", "reel", "coil", "bundle", "pack", "box", "carton", "bag", "sack", "pallet", "drum", "can", "bottle", "sheet", "container"],
  weight: ["g", "kg", "ton", "lb", "oz"],
  length: ["mm", "cm", "m", "linear_m", "km"],
  areaVolume: ["sqm", "cbm", "ml", "l"],
  time: ["hour", "day"],
} as const;

export type UnitGroup = keyof typeof UNIT_GROUPS;
export const UNITS: string[] = Object.values(UNIT_GROUPS).flat();
export const WEIGHT_UNITS: string[] = [...UNIT_GROUPS.weight];

// A weight unit's value in kilograms (metric ton; avoirdupois pound and ounce), as backend/app/core/units.py KILOGRAMS.
export const KILOGRAMS: Record<string, number> = { g: 0.001, kg: 1, ton: 1000, lb: 0.45359237, oz: 0.028349523125 };

/** A line's specification as printed: its values in order ("5 · 0.35 · Black"). */
export function specText(spec: Record<string, unknown> | null | undefined, separator = " · ") {
  return spec ? Object.values(spec).filter(v => v !== null && v !== "").map(String).join(separator) : "";
}
