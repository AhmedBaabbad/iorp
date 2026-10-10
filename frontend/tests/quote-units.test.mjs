// Units of measure are one catalogue: the frontend list, the backend list and both locale files (QUOTE-DOC-001, SHIP-002).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { UNITS, WEIGHT_UNITS } from "../src/lib/units.ts";

const backend = readFileSync(new URL("../../backend/app/core/units.py", import.meta.url), "utf8");
const normalized = backend.replace(/\r\n/g, "\n");
// One table of backend/app/core/units.py: from "UNITS: dict…" (or "SYMBOLS: dict…") to its closing brace.
const block = (name) => { const start = normalized.indexOf(`\n${name}: dict`); return normalized.slice(start, normalized.indexOf("\n}", start)); };
const backendCodes = [...block("UNITS").matchAll(/^    "([a-z_]+)": \("/gm)].map((m) => m[1]);
const backendSymbols = Object.fromEntries([...block("SYMBOLS").matchAll(/^    "([a-z_]+)": \("([^"]+)", "([^"]+)"\)/gm)].map((m) => [m[1], [m[2], m[3]]]));
const backendWeights = [...normalized.match(/KILOGRAMS[^=]*= \{([\s\S]*?)\}/)[1].matchAll(/"([a-z_]+)": Decimal/g)].map((m) => m[1]);

test("frontend units equal the backend list, without duplicates (quotations re-export the same list)", () => {
  assert.deepEqual([...UNITS].sort(), [...backendCodes].sort());
  assert.equal(new Set(UNITS).size, UNITS.length);
  assert.deepEqual([...WEIGHT_UNITS].sort(), [...backendWeights].sort());
});

test("every unit has an Arabic and an English name, and the short form the documents print", () => {
  for (const [i, lang] of ["ar", "en"].entries()) {
    const { units, names } = JSON.parse(readFileSync(new URL(`../src/i18n/locales/${lang}/common.json`, import.meta.url), "utf8")).units;
    for (const code of UNITS) {
      assert.ok(names[code], `${lang} name ${code}`);
      // UNIT-SYM-001: screens print the same symbol as the backend documents (مم / mm, كجم / kg).
      assert.equal(units[code], backendSymbols[code]?.[i], `${lang} symbol ${code}`);
    }
  }
  assert.deepEqual(Object.keys(backendSymbols).sort(), [...UNITS].sort());
});
