// PROJECT-FIX-002: Arabic and English stay complete. Every key exists in both languages with the same kind of value
// and the same variables, and every literal key the screens ask for exists. A failure names the file and the key.
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

const LOCALES = "src/i18n/locales";
const FILES = readdirSync(join(LOCALES, "ar")).filter((f) => f.endsWith(".json")).sort();
const NAMESPACE = (file) => file.replace(/\.json$/, "").replace(/-(\w)/g, (_, c) => c.toUpperCase());

// Keys written with dots ("a.b": …) are nested by the loader (src/i18n/messages.ts); do the same here.
function expand(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return value;
  const out = {};
  for (const [raw, v] of Object.entries(value)) {
    const parts = raw.split(".");
    let target = out;
    for (const part of parts.slice(0, -1)) target = target[part] ??= {};
    target[parts.at(-1)] = expand(v);
  }
  return out;
}
const read = (lang, file) => expand(JSON.parse(readFileSync(join(LOCALES, lang, file), "utf-8")));
function flatten(value, prefix = "", out = {}) {
  for (const [k, v] of Object.entries(value)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === "object" && !Array.isArray(v)) flatten(v, key, out);
    else out[key] = v;
  }
  return out;
}
// The variables a message takes: {name} and the argument of {count, plural, …}; the words inside a plural are not variables.
function variables(message) {
  const found = new Set();
  let depth = 0;
  for (let i = 0; i < message.length; i++) {
    if (message[i] === "{") {
      if (depth === 0) {
        const m = /^\{\s*(\w+)\s*[,}]/.exec(message.slice(i));
        if (m) found.add(m[1]);
      }
      depth++;
    } else if (message[i] === "}") depth--;
  }
  return [...found].sort();
}

test("the two languages have the same files", () => {
  assert.deepEqual(readdirSync(join(LOCALES, "en")).filter((f) => f.endsWith(".json")).sort(), FILES);
});

for (const file of FILES) {
  test(`${file}: every key in both languages, same kind of value and same variables`, () => {
    const ar = flatten(read("ar", file)), en = flatten(read("en", file));
    assert.deepEqual(Object.keys(en).filter((k) => !(k in ar)).sort(), [], `${file}: keys missing in Arabic`);
    assert.deepEqual(Object.keys(ar).filter((k) => !(k in en)).sort(), [], `${file}: keys missing in English`);
    for (const key of Object.keys(ar)) {
      assert.equal(typeof ar[key], typeof en[key], `${file}: ${key} is ${typeof ar[key]} in Arabic, ${typeof en[key]} in English`);
      if (typeof ar[key] === "string") {
        assert.ok(ar[key].trim() && en[key].trim(), `${file}: ${key} is empty`);
        assert.deepEqual(variables(ar[key]), variables(en[key]), `${file}: ${key} takes different variables`);
      }
    }
  });
}

test("every literal key a screen asks for exists in both languages", () => {
  const messages = Object.fromEntries(["ar", "en"].map((lang) => [lang, Object.fromEntries(FILES.map((f) => [NAMESPACE(f), read(lang, f)]))]));
  const has = (tree, path) => path.split(".").every((part) => (tree = tree && typeof tree === "object" ? tree[part] : undefined) !== undefined);
  // A namespace built at run time (`dashboard.${department}`) cannot be checked here; its calls are skipped.
  const declaration = /const\s+(\w+)\s*=\s*(?:useTranslations|await getTranslations)\(\s*(?:["'`]([^"'`]*)["'`])?\s*\)/g;
  const missing = [];
  const walk = (dir) => {
    for (const name of readdirSync(dir)) {
      const path = join(dir, name);
      if (statSync(path).isDirectory()) { if (name !== "i18n") walk(path); continue; }
      if (!/\.tsx?$/.test(name)) continue;
      const source = readFileSync(path, "utf-8");
      const declared = [...source.matchAll(declaration)].map((m) => ({ at: m.index, name: m[1], ns: m[2] ?? "" }));
      for (const variable of new Set(declared.map((d) => d.name))) {
        for (const call of source.matchAll(new RegExp(`(?<![\\w.])${variable}(?:\\.rich|\\.markup)?\\(\\s*["']([\\w-]+(?:\\.[\\w-]+)*)["']`, "g"))) {
          const scope = declared.filter((d) => d.name === variable && d.at < call.index).at(-1);
          if (!scope || scope.ns.includes("${")) continue;
          const key = scope.ns ? `${scope.ns}.${call[1]}` : call[1];
          for (const lang of ["ar", "en"]) if (!has(messages[lang], key)) missing.push(`${path}: ${lang} ${key}`);
        }
      }
    }
  };
  walk("src");
  assert.deepEqual(missing, []);
});
