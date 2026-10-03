// QUAL-001: the frontend quality permission codes equal the backend's single source.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { Q, QUALITY_REPORTS } from "../src/lib/quality-permissions.ts";

const backend = readFileSync(new URL("../../backend/app/quality/domain/permissions.py", import.meta.url), "utf8");

test("every backend quality permission exists in the frontend, and nothing else", () => {
  const block = backend.match(/RESOURCES: dict\[str, tuple\[str, \.\.\.\]\] = \{([\s\S]*?)\n\}/)[1];
  const codes = [];
  for (const [, resource, actions] of block.matchAll(/"([a-z_]+)": \(([^)]*)\)/g)) {
    for (const [, action] of actions.matchAll(/"([a-z_]+)"/g)) codes.push(`quality:${resource}:${action}`);
  }
  assert.deepEqual(Object.values(Q).sort(), codes.sort());
});

test("the quality report permissions equal the backend's report catalog", () => {
  const source = readFileSync(new URL("../../backend/app/quality/domain/report_permissions.py", import.meta.url), "utf8");
  const block = source.match(/LABELS = \{([\s\S]*?)\r?\n\}/)[1];
  const codes = [...block.matchAll(/^\s+'([a-z_]+)':/gm)].map(([, key]) => `reports:quality:${key}`);
  assert.deepEqual([...QUALITY_REPORTS].sort(), codes.sort());
});
