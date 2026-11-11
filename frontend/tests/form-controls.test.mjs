import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = path => readFileSync(new URL(path, import.meta.url), "utf8");
const globals = read("../src/app/globals.css");
const shared = read("../src/styles/shared-styles.ts");
const demands = read("../src/features/production-demands/demands.module.css");

test("form tokens are defined once in the root and both styling systems consume them", () => {
  const tokens = { "control-height": "44px", "control-padding-inline": "12px", "control-radius": "6px",
    "control-border": "var(--border-strong)", "field-gap": "8px", "label-size": "14px", "label-weight": "700", "form-gap": "16px" };
  const root = globals.match(/:root\s*\{([^}]+)\}/)[1];
  for (const [token, value] of Object.entries(tokens)) {
    assert.ok(root.includes(`--${token}: ${value};`), token);
    assert.equal(globals.split(`--${token}:`).length - 1, 1);
  }
  for (const token of ["control-padding-inline", "control-radius", "control-border", "field-gap", "label-size", "label-weight"]) {
    assert.ok(shared.includes(`var(--${token})`), `sharedStyles: ${token}`);
    assert.ok(demands.includes(`var(--${token})`), `.field: ${token}`);
  }
  assert.match(demands, /\.grid\s*\{[^}]*align-items:\s*start/);
  assert.match(demands, /gap:\s*var\(--form-gap\)/);
  assert.match(shared, /minBlockSize:\s*"90px"/);
  assert.match(demands, /min-block-size:\s*90px/);
});

test("fixed height excludes checkbox, radio and multiple select", () => {
  for (const css of [globals, demands]) {
    assert.match(css, /input:not\(\[type="checkbox"\]\):not\(\[type="radio"\]\)/);
    assert.match(css, /select:not\(\[multiple\]\)[^{]*\{[^}]*block-size:\s*var\(--control-height\)/);
  }
  const row = read("../src/components/forms/control-row.module.css");
  assert.match(row, /display:\s*flex/);
  assert.match(row, /min-inline-size:\s*0/);
  assert.match(row, /block-size:\s*var\(--control-height\)/);
});
