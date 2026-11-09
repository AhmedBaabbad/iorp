import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const css = readFileSync(new URL("../src/app/globals.css", import.meta.url), "utf8");

test("fieldsets let nested tables scroll without widening the page", () => {
  assert.match(css, /fieldset\s*\{[^}]*min-inline-size:\s*0\s*;/);
});
