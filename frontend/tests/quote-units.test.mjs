// Units of measure are one catalogue: the frontend list, the backend list and both locale files (QUOTE-DOC-001, SHIP-002).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { UNITS, WEIGHT_UNITS } from "../src/lib/units.ts";

const backend = readFileSync(new URL("../../backend/app/core/units.py", import.meta.url), "utf8");
const backendCodes = [...backend.matchAll(/^    "([a-z_]+)": \("/gm)].map((m) => m[1]);
const backendWeights = [...backend.match(/KILOGRAMS[^=]*= \{([\s\S]*?)\}/)[1].matchAll(/"([a-z_]+)": Decimal/g)].map((m) => m[1]);

test("frontend units equal the backend list, without duplicates (quotations re-export the same list)", () => {
  assert.deepEqual([...UNITS].sort(), [...backendCodes].sort());
  assert.equal(new Set(UNITS).size, UNITS.length);
  assert.deepEqual([...WEIGHT_UNITS].sort(), [...backendWeights].sort());
});

test("every unit has an Arabic and an English label", () => {
  for (const lang of ["ar", "en"]) {
    const units = JSON.parse(readFileSync(new URL(`../src/i18n/locales/${lang}/common.json`, import.meta.url), "utf8")).units.units;
    for (const code of UNITS) assert.ok(units[code], `${lang} ${code}`);
  }
});
