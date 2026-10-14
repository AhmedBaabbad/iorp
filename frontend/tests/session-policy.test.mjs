// Idle sign-out timing rules (lib/session-policy.ts).
import { test } from "node:test";
import assert from "node:assert/strict";
import { IDLE_TIMEOUT_MS, IDLE_WARNING_MS, nextSessionAction, tokenExpiry } from "../src/lib/session-policy.ts";

const MIN = 60_000;
const now = 1_000_000_000_000;
const farExpiry = now + 10 * MIN;

test("defaults to fifteen minutes of inactivity with a one-minute warning", () => {
  assert.equal(IDLE_TIMEOUT_MS, 15 * MIN);  // SEC-001
  assert.equal(IDLE_WARNING_MS, MIN);
});

test("active user: nothing happens", () => {
  assert.deepEqual(nextSessionAction(now, now, farExpiry), { type: "ok" });
  assert.deepEqual(nextSessionAction(now, now - (14 * MIN - 1000), farExpiry), { type: "ok" });
});

test("warns during the last minute with a countdown", () => {
  assert.deepEqual(nextSessionAction(now, now - 14 * MIN, farExpiry), { type: "warn", secondsLeft: 60 });
  assert.deepEqual(nextSessionAction(now, now - (15 * MIN - 1500), farExpiry), { type: "warn", secondsLeft: 2 });
});

test("signs out at fifteen minutes, even without any click", () => {
  assert.deepEqual(nextSessionAction(now, now - 15 * MIN, farExpiry), { type: "logout" });
  assert.deepEqual(nextSessionAction(now, now - 60 * MIN, null), { type: "logout" });
});

test("renews the token shortly before it expires, only while active", () => {
  assert.deepEqual(nextSessionAction(now, now, now + 30_000), { type: "refresh" });
  assert.deepEqual(nextSessionAction(now, now, now - 1), { type: "refresh" });
  // An idle user is signed out rather than kept alive by renewal.
  assert.deepEqual(nextSessionAction(now, now - 15 * MIN, now + 30_000), { type: "logout" });
});

test("reads the expiry from a JWT and tolerates bad tokens", () => {
  const payload = Buffer.from(JSON.stringify({ exp: 1_900_000_000 })).toString("base64url");
  assert.equal(tokenExpiry(`h.${payload}.s`), 1_900_000_000_000);
  assert.equal(tokenExpiry("not-a-jwt"), null);
  assert.equal(tokenExpiry(null), null);
});
