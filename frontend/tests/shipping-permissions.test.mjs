// SHIP-001: the frontend shipping permission codes equal the backend's single source.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { S } from "../src/lib/shipping-permissions.ts";

const backend = readFileSync(new URL("../../backend/app/shipping/domain/permissions.py", import.meta.url), "utf8");

test("every backend shipping permission exists in the frontend, and nothing else", () => {
  const block = backend.match(/RESOURCES: dict\[str, tuple\[str, \.\.\.\]\] = \{([\s\S]*?)\r?\n\}/)[1];
  const codes = [];
  for (const [, resource, actions] of block.matchAll(/"([a-z_]+)": \(([^)]*)\)/g)) {
    for (const [, action] of actions.matchAll(/"([a-z_]+)"/g)) codes.push(`shipping:${resource}:${action}`);
  }
  assert.deepEqual(Object.values(S).sort(), codes.sort());
});
