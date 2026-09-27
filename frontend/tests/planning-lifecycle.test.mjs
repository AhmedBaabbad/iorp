// PROD-PLAN-003 frontend rules. Run: npm test (node --test, no DOM required).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  canReleaseFromOrder, lifecycleErrorCode, parseView, planningQuery, progress, statusOptions,
} from "../src/features/production-demands/planning-lifecycle.ts";

const query = (...args) => Object.fromEntries(new URLSearchParams(planningQuery(...args)));

test("active queue is the default view and hides completed planning", () => {
  assert.equal(parseView(null), "active");
  assert.equal(parseView("bogus"), "active");
  assert.equal(query(parseView(null), {}, 1).view, "active");
  // A fully planned status can never be requested from the active queue.
  assert.equal(query("active", { status: "planned" }, 1).status, undefined);
  assert.deepEqual(statusOptions("active"), ["ready_for_planning", "partially_planned"]);
});

test("active / planned / all filters are sent to the server", () => {
  assert.equal(query("planned", {}, 2).view, "planned");
  assert.equal(query("planned", {}, 2).page, "2");
  assert.equal(query("all", { status: "cancelled", search: "PD-1", customer_id: "" }, 1).status, "cancelled");
  assert.equal(query("all", { customer_id: "" }, 1).customer_id, undefined);
  assert.deepEqual(statusOptions("planned"), []);
});

test("partial progress is shown correctly", () => {
  const p = progress({ required_quantity: "1000.000", active_allocated_quantity: "600.000", remaining_quantity: "400.000" });
  assert.deepEqual([p.allocated, p.required, p.remaining, p.percent, p.partial], ["600", "1000", "400", 60, true]);
  assert.equal(progress({ required_quantity: "1000", active_allocated_quantity: "1000", remaining_quantity: "0" }).partial, false);
  assert.equal(progress({ required_quantity: "1000", active_allocated_quantity: "0", remaining_quantity: "1000" }).partial, false);
});

test("remaining quantity updates and is decimal-exact", () => {
  // Derived when the server omits it; no floating point drift (0.1 + 0.2 style).
  assert.equal(progress({ required_quantity: "1.003", active_allocated_quantity: "1.002" }).remaining, "0.001");
  // After a release the server sends fewer active units; the UI trusts active, never released.
  assert.equal(progress({ required_quantity: "1000", active_allocated_quantity: "300", remaining_quantity: "700" }).remaining, "700");
  assert.equal(progress({ required_quantity: "1000", allocated_quantity: "250" }).allocated, "250");
});

test("release is offered only before execution", () => {
  assert.equal(canReleaseFromOrder("draft"), true);
  assert.equal(canReleaseFromOrder("released"), true);
  for (const status of ["in_progress", "completed", "cancelled"]) assert.equal(canReleaseFromOrder(status), false);
});

test("server lifecycle error codes are surfaced", () => {
  assert.equal(lifecycleErrorCode({ status: 409, details: { detail: { code: "ORDER_EXECUTION_STARTED" } } }), "ORDER_EXECUTION_STARTED");
  assert.equal(lifecycleErrorCode({ status: 403 }), "forbidden");
  assert.equal(lifecycleErrorCode(new Error("x")), "request_failed");
});

test("every lifecycle message exists in English and Arabic", () => {
  for (const lang of ["en", "ar"]) {
    const m = JSON.parse(readFileSync(new URL(`../src/i18n/locales/${lang}/production.json`, import.meta.url), "utf8"));
    for (const view of ["active", "planned", "all"]) {
      assert.ok(m.planning.views[view] && m.planning.views.empty[view], `${lang} view ${view}`);
    }
    for (const key of ["active", "released"]) assert.ok(m.allocation.statuses[key], `${lang} status ${key}`);
    for (const code of ["ORDER_EXECUTION_STARTED", "ORDER_COMPLETED", "LAST_ACTIVE_ALLOCATION", "ALLOCATION_ALREADY_RELEASED", "ORDER_ALREADY_CANCELLED"]) {
      assert.ok(m.allocation.errors[code], `${lang} error ${code}`);
    }
  }
});
