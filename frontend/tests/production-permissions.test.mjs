// PROD-RBAC-001: the frontend production permission codes equal the backend's single source.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { P, REPORT } from "../src/lib/production-permissions.ts";

const backend = readFileSync(new URL("../../backend/app/production/domain/permissions.py", import.meta.url), "utf8");

function backendCodes() {
  const block = backend.match(/RESOURCES: dict\[str, tuple\[str, \.\.\.\]\] = \{([\s\S]*?)\n\}/)[1];
  const codes = [];
  for (const [, resource, actions] of block.matchAll(/"([a-z_]+)": \(([^)]*)\)/g)) {
    for (const [, action] of actions.matchAll(/"([a-z_]+)"/g)) codes.push(`production:${resource}:${action}`);
  }
  return codes;
}

test("every backend production permission exists in the frontend, and nothing else", () => {
  assert.deepEqual([...Object.values(P)].sort(), backendCodes().sort());
  assert.equal(new Set(Object.values(P)).size, Object.values(P).length);
});

test("report permission codes match the backend constants", () => {
  const reports = [...backend.matchAll(/^REPORT_[A-Z_]+ = "([a-z_:]+)"/gm)].map((m) => m[1]);
  assert.deepEqual(Object.values(REPORT).sort(), reports.sort());
});

test("no screen spells a production permission or uses a removed code", () => {
  const files = [];
  const walk = (dir) => readdirSync(dir).forEach((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) walk(path);
    else if (/\.(ts|tsx)$/.test(name) && !path.endsWith("production-permissions.ts")) files.push(path);
  });
  walk(new URL("../src", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
  const offenders = files.filter((f) => /["'`](production|reports):[a-z_]+:[a-z_]+["'`]/.test(readFileSync(f, "utf8")));
  assert.deepEqual(offenders, []);
});
