// Demands list status visibility. Run: npm test (node --test, no DOM required).
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  ALL_STATUSES, DEFAULT_VISIBLE, initialStatuses, isAll, parseStatuses, statusQuery, toggle, withStatusesInUrl,
} from "../src/features/production-demands/status-visibility.ts";

test("finished demands are hidden by default", () => {
  assert.deepEqual(DEFAULT_VISIBLE, ["draft", "ready_for_planning", "partially_planned"]);
  assert.deepEqual(initialStatuses(null, null), DEFAULT_VISIBLE);
});

test("a shared link wins over this browser's choice, which wins over the default", () => {
  assert.deepEqual(initialStatuses("planned,cancelled", "draft"), ["planned", "cancelled"]);
  assert.deepEqual(initialStatuses(null, "cancelled,draft"), ["draft", "cancelled"]);
  assert.deepEqual(initialStatuses("bogus", "also-bogus"), DEFAULT_VISIBLE);
  assert.equal(parseStatuses(""), null);
});

test("each status hides on its own and the last one cannot be hidden", () => {
  assert.deepEqual(toggle(DEFAULT_VISIBLE, "draft"), ["ready_for_planning", "partially_planned"]);
  assert.deepEqual(toggle(["draft"], "planned"), ["draft", "planned"]);
  assert.deepEqual(toggle(["draft"], "draft"), ["draft"]);
});

test("the API gets one statuses pair per shown status, none when all are shown", () => {
  assert.deepEqual(statusQuery(["cancelled", "draft"]), [["statuses", "draft"], ["statuses", "cancelled"]]);
  assert.deepEqual(statusQuery([...ALL_STATUSES]), []);
  assert.ok(isAll([...ALL_STATUSES]));
});

test("the page URL carries the choice only when it is not the default", () => {
  assert.equal(withStatusesInUrl("search=x", DEFAULT_VISIBLE).toString(), "search=x");
  assert.equal(withStatusesInUrl("search=x&statuses=draft", ["planned"]).get("statuses"), "planned");
});
