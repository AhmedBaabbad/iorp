// Guards against dropdowns (and other fields) whose text disappears in light or dark mode.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const root = new URL("../src/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const files = [];
(function walk(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) walk(path);
    else if (/\.(css|tsx?)$/.test(name)) files.push(path);
  }
})(root);
const read = path => readFileSync(path, "utf8");
const LIGHT = /^(#fff|#ffffff|white|#f8fafc|#fafafa)$/i;

test("every CSS variable used exists in the theme", () => {
  const globals = read(join(root, "app", "globals.css"));
  const defined = new Set([...globals.matchAll(/(--[\w-]+)\s*:/g)].map(m => m[1]));
  const missing = [];
  for (const file of files) {
    for (const m of read(file).matchAll(/var\((--[\w-]+)/g)) if (!defined.has(m[1])) missing.push(`${m[1]} in ${file}`);
  }
  // An undefined variable silently falls back to a fixed color that ignores the theme.
  assert.deepEqual(missing, []);
});

test("no stylesheet gives dropdowns or inputs a fixed light background", () => {
  const offenders = [];
  for (const file of files.filter(f => f.endsWith(".css"))) {
    for (const [, selector, body] of read(file).matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
      if (!/\b(select|option|input|\.select|\.input)\b/.test(selector)) continue;
      const background = /background(?:-color)?\s*:\s*([^;}]+)/.exec(body)?.[1].trim();
      if (background && LIGHT.test(background)) offenders.push(`${file}: ${selector.trim()}`);
    }
  }
  assert.deepEqual(offenders, []);
});

test("input style objects that set a background also set a text color", () => {
  const offenders = [];
  for (const file of files.filter(f => f.endsWith(".tsx") || f.endsWith(".ts"))) {
    const src = read(file);
    for (const m of src.matchAll(/(?:const\s+(\w*input\w*)[^=]*=\s*|\b(input)\s*:\s*)\{([^{}]*)\}/gi)) {
      const body = m[3];
      const background = /background(?:Color)?\s*:\s*"([^"]+)"/.exec(body)?.[1];
      if (background && !/\bcolor\s*:/.test(body)) offenders.push(`${file}: ${m[1] || m[2]} (background ${background}, no color)`);
    }
  }
  assert.deepEqual(offenders, []);
});

test("native option lists and widgets use explicit theme colors", () => {
  const globals = read(join(root, "app", "globals.css"));
  // Explicit colors: inherited/system colors let Firefox draw white text on a white list.
  assert.match(globals, /option,\s*optgroup\s*\{\s*background-color:\s*var\(--surface\);\s*color:\s*var\(--text\);\s*\}/);
  assert.match(globals, /:root\s*\{[^}]*color-scheme:\s*light;/);
  assert.match(globals, /:root\[data-theme="dark"\]\s*\{[^}]*color-scheme:\s*dark;/);
});

test("colors come from theme tokens, not hard-coded values", () => {
  // Only globals.css defines colors. A line may opt out with a "theme-exempt" note explaining why.
  const offenders = [];
  for (const file of files.filter(f => f !== join(root, "app", "globals.css") && !f.includes(join("src", "i18n")))) {
    read(file).split("\n").forEach((line, n) => {
      if (/#[0-9a-fA-F]{3,8}\b/.test(line.replace(/&#\d+;|#[\w-]+\s*\{|href="#[^"]*"/g, "")) && !line.includes("theme-exempt")) offenders.push(`${file}:${n + 1}`);
    });
  }
  assert.deepEqual(offenders, []);
});
