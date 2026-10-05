// PROC-001: the frontend procurement permission codes equal the backend's single source.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { PR } from "../src/lib/procurement-permissions.ts";

const backend = readFileSync(new URL("../../backend/app/procurement/domain/permissions.py", import.meta.url), "utf8");

test("every backend procurement permission exists in the frontend, and nothing else", () => {
  const block = backend.match(/RESOURCES: dict\[str, tuple\[str, \.\.\.\]\] = \{([\s\S]*?)\r?\n\}/)[1];
  const codes = [];
  for (const [, resource, actions] of block.matchAll(/"([a-z_]+)": \(([^)]*)\)/g)) {
    for (const [, action] of actions.matchAll(/"([a-z_]+)"/g)) codes.push(`procurement:${resource}:${action}`);
  }
  assert.deepEqual(Object.values(PR).sort(), codes.sort());
});
