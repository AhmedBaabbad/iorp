// Units of measure offered on quotations; mirrors backend/app/commercial/domain/units.py
// (tests/quote-units.test.mjs keeps both identical). Labels: commercial.quoteUnits.<code> in the locale files.
export const QUOTE_UNIT_GROUPS = {
  count: ["piece", "unit", "pair", "set", "dozen", "lot"],
  packaging: ["roll", "reel", "coil", "bundle", "pack", "box", "carton", "bag", "sack", "pallet", "drum", "can", "bottle", "sheet", "container"],
  weight: ["g", "kg", "ton"],
  length: ["mm", "cm", "m", "linear_m", "km"],
  areaVolume: ["sqm", "cbm", "ml", "l"],
  time: ["hour", "day"],
} as const;

export const QUOTE_UNITS: string[] = Object.values(QUOTE_UNIT_GROUPS).flat();

/** VAT rate applied when "include VAT" is ticked; the server computes the amount from it. */
export const VAT_RATE = 15;
