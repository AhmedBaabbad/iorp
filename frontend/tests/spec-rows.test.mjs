// Quote line specification rows: stored as the same JSON production reads.
import { test } from "node:test";
import assert from "node:assert/strict";
import { parseSpecValue, rowsToSpec, specToRows } from "../src/lib/spec-rows.ts";

test("numbers and booleans keep their type, text stays text", () => {
  assert.equal(parseSpecValue("5"), 5);
  assert.equal(parseSpecValue("0.35"), 0.35);
  assert.equal(parseSpecValue("true"), true);
  assert.equal(parseSpecValue("أسود"), "أسود");
  assert.equal(parseSpecValue("5MM"), "5MM");
  assert.deepEqual(parseSpecValue('{"a":1}'), { a: 1 });
});

test("rows round-trip through the stored JSON", () => {
  const json = rowsToSpec([{ key: "width_mm", value: "5" }, { key: "color", value: "black" }, { key: " ", value: "ignored" }]);
  assert.deepEqual(JSON.parse(json), { width_mm: 5, color: "black" });
  assert.deepEqual(specToRows(json), [{ key: "width_mm", value: "5" }, { key: "color", value: "black" }]);
  assert.equal(rowsToSpec([]), "");
  assert.deepEqual(specToRows(""), []);
  assert.deepEqual(specToRows("not json"), []);
});
