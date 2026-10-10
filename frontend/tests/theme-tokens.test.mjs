// WCAG contrast of the theme tokens, for every theme. Run: npm test
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const css = readFileSync(new URL("../src/app/globals.css", import.meta.url), "utf8");
const block = selector => {
  const start = css.indexOf(`${selector} {`);
  assert.ok(start >= 0, `missing theme block ${selector}`);
  const body = css.slice(start, css.indexOf("}", start));
  return Object.fromEntries([...body.matchAll(/(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{6})\b/g)].map(m => [m[1].slice(2), m[2]]));
};
const light = block(":root");
export const THEMES = {
  light,
  dark: { ...light, ...block(':root[data-theme="dark"]') },
  dim: { ...light, ...block(':root[data-theme="dim"]') },
  contrast: { ...light, ...block(':root[data-theme="contrast"]') },
};
const FAMILIES = ["accent", "success", "warning", "danger", "purple", "teal"];

function luminance(hex) {
  const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255).map(c => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
export function ratio(a, b) {
  const [x, y] = [luminance(a), luminance(b)].sort((m, n) => n - m);
  return (x + 0.05) / (y + 0.05);
}

for (const [name, t] of Object.entries(THEMES)) {
  test(`${name}: every token is defined`, () => {
    for (const key of ["page-bg", "surface", "surface-muted", "surface-raised", "text", "text-muted", "text-subtle", "border", "border-strong", "on-accent", "focus", ...FAMILIES, ...FAMILIES.map(f => `${f}-soft`), "accent-strong"]) {
      assert.match(t[key] ?? "", /^#[0-9a-fA-F]{6}$/, `${name} --${key}`);
    }
  });

  test(`${name}: text contrast meets WCAG`, () => {
    const failures = [];
    const need = (fg, bg, min) => { const r = ratio(t[fg], t[bg]); if (r < min) failures.push(`${fg} on ${bg}: ${r.toFixed(2)} < ${min}`); };
    const strict = name === "contrast";
    for (const bg of ["page-bg", "surface", "surface-muted", "surface-raised"]) {
      need("text", bg, strict ? 15 : 7);
      need("text-muted", bg, strict ? 10 : 4.5);
      need("text-subtle", bg, strict ? 7 : 4.5);
    }
    for (const f of FAMILIES) {
      need(f, "surface", strict ? 7 : 4.5);   // colored text on cards
      need(f, `${f}-soft`, strict ? 7 : 4.5); // badges: colored text on their tint
      need("on-accent", f, 4.5);              // text on a colored fill (buttons, strong badges)
    }
    need("accent-strong", "surface", 4.5);
    need("on-accent", "accent-strong", 4.5);
    need("on-accent", "text", 4.5);           // inverted fills use text as background
    need("surface", "text", 4.5);
    assert.deepEqual(failures, []);
  });

  test(`${name}: controls and focus are visible`, () => {
    // WCAG 1.4.11: component boundaries and focus indicators need 3:1 against their surroundings.
    assert.ok(ratio(t["border-strong"], t.surface) >= 3, `border-strong ${ratio(t["border-strong"], t.surface).toFixed(2)}`);
    assert.ok(ratio(t.focus, t.surface) >= 3, `focus ${ratio(t.focus, t.surface).toFixed(2)}`);
  });
}

test("every background/text pair used in the code is readable in every theme", async () => {
  const { readdirSync, statSync } = await import("node:fs");
  const { join } = await import("node:path");
  const root = new URL("../src/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
  const files = [];
  (function walk(dir) { for (const n of readdirSync(dir)) { const p = join(dir, n); if (statSync(p).isDirectory()) walk(p); else if (/\.(tsx|ts|css)$/.test(n)) files.push(p); } })(root);
  const failures = [];
  for (const file of files) {
    const src = readFileSync(file, "utf8");
    // Each CSS rule body or object literal that sets both a plain token background and a token text color.
    for (const [scope] of src.matchAll(/\{[^{}]*\}/g)) {
      const bg = /background(?:-color|Color)?\s*:\s*["']?var\(--([\w-]+)\)["']?\s*[;,}\n]/.exec(scope)?.[1];
      const fg = /(?:^|[\s{;,])color\s*:\s*["']?var\(--([\w-]+)\)/.exec(scope)?.[1];
      if (!bg || !fg) continue;
      for (const [name, t] of Object.entries(THEMES)) {
        if (!t[bg] || !t[fg]) continue;
        const r = ratio(t[fg], t[bg]);
        if (r < 4.5) failures.push(`${name}: ${fg} on ${bg} = ${r.toFixed(2)} in ${file.slice(root.length)}`);
      }
    }
  }
  assert.deepEqual([...new Set(failures)], []);
});

// DASH-002: the blue sidebar keeps its labels readable at both ends of its gradient, in every theme.
for (const [name, t] of Object.entries(THEMES)) {
  test(`${name}: the sidebar's text is readable`, () => {
    const failures = [];
    const strict = name === "contrast";
    for (const bg of ["sidebar-bg", "sidebar-bg-end"]) {
      for (const [fg, min] of [["sidebar-text", strict ? 15 : 7], ["sidebar-muted", strict ? 15 : 4.5]]) {
        const r = ratio(t[fg], t[bg]);
        if (r < min) failures.push(`${fg} on ${bg}: ${r.toFixed(2)} < ${min}`);
      }
    }
    const active = ratio(t["sidebar-active-text"], t["sidebar-active"]);
    if (active < (strict ? 15 : 7)) failures.push(`sidebar-active-text on sidebar-active: ${active.toFixed(2)}`);
    assert.deepEqual(failures, []);
  });
}
