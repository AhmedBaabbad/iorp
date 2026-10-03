// QUOTE-DOC-001: quotation units are the same list in the frontend, the backend and both locale files.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { QUOTE_UNITS } from "../src/features/quotes/quote-units.ts";

const backend = readFileSync(new URL("../../backend/app/commercial/domain/units.py", import.meta.url), "utf8");
const backendCodes = [...backend.matchAll(/^    "([a-z_]+)": \("/gm)].map((m) => m[1]);

test("frontend units equal the backend list, without duplicates", () => {
  assert.deepEqual([...QUOTE_UNITS].sort(), [...backendCodes].sort());
  assert.equal(new Set(QUOTE_UNITS).size, QUOTE_UNITS.length);
});

test("every unit has an Arabic and an English label", () => {
  for (const lang of ["ar", "en"]) {
    const units = JSON.parse(readFileSync(new URL(`../src/i18n/locales/${lang}/commercial.json`, import.meta.url), "utf8")).quoteUnits.units;
    for (const code of QUOTE_UNITS) assert.ok(units[code], `${lang} ${code}`);
  }
});
