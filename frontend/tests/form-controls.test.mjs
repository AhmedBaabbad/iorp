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

test("fixed height excludes native special inputs and multiple selects in both systems", () => {
  for (const css of [globals, demands]) {
    const rule = css.match(/([^{}]+)\{[^{}]*block-size:\s*var\(--control-height\)[^{}]*\}/);
    assert.ok(rule);
    for (const type of ["checkbox", "radio", "hidden", "file", "range", "color", "image", "submit", "reset", "button"]) {
      assert.ok(rule[1].includes(`:not([type="${type}"])`), type);
    }
    assert.ok(rule[1].includes("select:not([multiple])"));
  }
  const row = read("../src/components/forms/control-row.module.css");
  assert.match(row, /display:\s*flex/);
  assert.match(row, /min-inline-size:\s*0/);
  assert.match(row, /block-size:\s*var\(--control-height\)/);
});

test("inline grid defaults respect explicit alignment and do not force inline gaps", () => {
  const rule = globals.match(/\/\* Inline form grids[^]*?\*\/\s*([^{}]+)\{([^}]+)\}/);
  assert.ok(rule);
  assert.doesNotMatch(rule[0], /!important/);
  const selectors = rule[1].split(",").map(s => s.trim());
  assert.equal(selectors.length, 3);
  for (const selector of selectors) assert.ok(selector.endsWith(':not([style*="align-items"])'));
  assert.match(rule[2], /align-items:\s*start;/);
  assert.match(rule[2], /gap:\s*var\(--form-gap\);/);
  const defects = read("../src/features/quality-defects/components/QualityDefectForm.tsx");
  assert.match(defects, /row:\s*\{[^}]*display:\s*"grid"[^}]*alignItems:\s*"end"/);
});

test("directory controls wrap independently from the ListSelect management row", () => {
  const css = read("../src/components/forms/control-row.module.css");
  const directory = css.match(/\.directoryRow\s*\{([^}]+)\}/)[1];
  assert.match(directory, /flex-wrap:\s*wrap/);
  assert.match(css, /div\.directoryRow > input, div\.directoryRow > select\s*\{[^}]*flex:\s*1 1 10rem;[^}]*min-inline-size:\s*min\(10rem, 100%\)/);
  assert.doesNotMatch(css.match(/\.row\s*\{([^}]+)\}/)[1], /flex-wrap/);
  assert.match(read("../src/features/reference-directory/RecordSelect.tsx"), /className=\{row.directoryRow\}/);
});

test("helpers have normal weight without changing field title weight", () => {
  for (const css of [globals, demands]) {
    assert.match(css, /:is\(small, \[role="alert"\], \.muted, \.error\)[^{}]*\{\s*font-weight:\s*400;/);
    assert.match(css, /> span ~ span/);
    assert.match(css, /font-weight:\s*var\(--label-weight\)/);
  }
});
