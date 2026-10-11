// PROD-PLAN-003 frontend rules. Run: npm test (node --test, no DOM required).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { canReleaseFromOrder, lifecycleErrorCode, PLANNABLE_STATUSES, progress } from "../src/features/production-demands/planning-lifecycle.ts";
import { PLANNING, isActiveQueue, planningQuery, planningStatusesFromUrl } from "../src/features/production-demands/status-visibility.ts";

const query = (...args) => new URLSearchParams(planningQuery(...args));

test("the planning queue opens on what can still be planned", () => {
  assert.deepEqual(PLANNING.defaults, PLANNABLE_STATUSES);
  assert.ok(isActiveQueue(["partially_planned", "ready_for_planning"]));
  const q = query(PLANNING.defaults, {}, 1);
  assert.equal(q.get("view"), "active");
  assert.deepEqual(q.getAll("statuses"), ["ready_for_planning", "partially_planned"]);
  // The former single status filter is never sent.
  assert.equal(query(PLANNING.defaults, { status: "planned" }, 1).get("status"), null);
});

test("other selections are shown read-only from the all view", () => {
  const q = query(["planned", "cancelled"], { search: "PD-1", customer_id: "" }, 2);
  assert.equal(q.get("view"), "all");
  assert.deepEqual(q.getAll("statuses"), ["planned", "cancelled"]);
  assert.equal(q.get("page"), "2");
  assert.equal(q.get("search"), "PD-1");
  assert.equal(q.get("customer_id"), null);
  assert.deepEqual(query(["draft", "ready_for_planning", "partially_planned", "planned", "cancelled"], {}, 1).getAll("statuses"), []);
});

test("links from the former tabs still open the same demands", () => {
  assert.deepEqual(planningStatusesFromUrl(null, "planned"), ["planned"]);
  assert.equal(planningStatusesFromUrl(null, "all").length, 5);
  assert.equal(planningStatusesFromUrl(null, null), null);
  assert.deepEqual(planningStatusesFromUrl("cancelled", "planned"), ["cancelled"]);
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

// PROD-QUALITY-FIX-001: allocations follow the order's open/locked state (domain/order_lifecycle.py ALLOCATION_OPEN).
test("release is offered while the order is open, not once it is completed, closed or cancelled", () => {
  for (const status of ["draft", "released", "in_progress", "on_hold"]) assert.equal(canReleaseFromOrder(status), true, status);
  for (const status of ["completed", "closed", "cancelled"]) assert.equal(canReleaseFromOrder(status), false, status);
});

test("server lifecycle error codes are surfaced", () => {
  assert.equal(lifecycleErrorCode({ status: 409, details: { detail: { code: "ORDER_EXECUTION_STARTED" } } }), "ORDER_EXECUTION_STARTED");
  assert.equal(lifecycleErrorCode({ status: 403 }), "forbidden");
  assert.equal(lifecycleErrorCode(new Error("x")), "request_failed");
});

test("every lifecycle message exists in English and Arabic", () => {
  for (const lang of ["en", "ar"]) {
    const m = JSON.parse(readFileSync(new URL(`../src/i18n/locales/${lang}/production.json`, import.meta.url), "utf8"));
    for (const view of ["active", "all"]) assert.ok(m.planning.views.empty[view], `${lang} empty ${view}`);
    for (const key of ["label", "summary", "showAll", "reset", "hidden"]) assert.ok(m.demands.statusVisibility[key], `${lang} statusVisibility ${key}`);
    for (const key of ["active", "released"]) assert.ok(m.allocation.statuses[key], `${lang} status ${key}`);
    for (const code of ["ORDER_EXECUTION_STARTED", "ORDER_COMPLETED", "LAST_ACTIVE_ALLOCATION", "ALLOCATION_ALREADY_RELEASED", "ORDER_ALREADY_CANCELLED"]) {
      assert.ok(m.allocation.errors[code], `${lang} error ${code}`);
    }
  }
});
