import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const root=new URL("../src/features/",import.meta.url);
// These match the filename convention but are not independent list pages.
const exceptions={
  "masterdata/components/ListSelect.tsx":"Searchable reference picker, not a table page; options are scoped by list and parent.",
  "masterdata/components/ListCreateDialog.tsx":"Creates one reference record in a modal, not a list page.",
  "production-order-items/components/ProductionOrderItemsList.tsx":"Line editor within one production-order document; all lines are needed for document editing and totals.",
};
const additional=["masterdata/components/Products.tsx","quality-specifications/components/TestParametersPage.tsx","quality-checks/components/IncomingInspection.tsx","production-demands/list.tsx","reference-directory/DirectoryPanel.tsx","platform/platform-organizations-page.tsx","platform/platform-audit-page.tsx","notifications/NotificationsPage.tsx","logs/SeparatedLogPages.tsx",... ["Suppliers","Materials","PurchaseOrders","Receipts"].map(file=>`procurement/components/${file}.tsx`)];
const isList=filename=>/(?:[^/]*List[^/]*|-list-page)\.tsx$/.test(filename);
const covered=source=>/import\s*\{[^}]*\bPagination\b[^}]*\}\s*from\s*["'][^"']*pagination/.test(source)&&/<Pagination\b/.test(source);
test("every list page uses shared pagination or has an explicit documented exception",()=>{
  const files=fs.readdirSync(root,{recursive:true}).map(file=>file.replaceAll("\\","/"));
  const candidates=[...new Set([...files.filter(isList),...additional])];
  for(const [file,reason] of Object.entries(exceptions)){assert.ok(candidates.includes(file),`Stale exception: ${file}`);assert.ok(reason.length>30);}
  for(const file of candidates){if(exceptions[file])continue;assert.ok(covered(fs.readFileSync(new URL(file,root),"utf8")),`Missing Pagination: ${file}`);}
});
test("coverage rule rejects a newly added unpaginated list",()=>{
  assert.ok(isList("future/components/NewRecordsList.tsx"));
  assert.ok(isList("future/new-list-page.tsx"));
  assert.equal(covered('export function NewRecordsList(){return <table/>;}'),false);
  assert.equal(covered('// Pagination\nexport function NewRecordsList(){return <table/>;}'),false);
});
