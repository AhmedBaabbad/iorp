import { test } from "node:test";
import assert from "node:assert/strict";
import { snapshotPhone } from "../src/features/shipments/selected-records.ts";

test("saved phones match the server snapshot projection without affecting typed input",()=>{
  for(const [value,expected] of [["0551234567","+966551234567"],["٠٥٥ ١٢٣ ٤٥٦٧","+966551234567"],
    ["۰۵۵۱۲۳۴۵۶۷","+966551234567"],["00971501234567","+971501234567"],
    ["+1 (202) 555-0123","+12025550123"],["invalid legacy value",""],[null,""],[undefined,""],["",""]]){
    assert.equal(snapshotPhone(value),expected);
  }
});
