import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import ts from "typescript";

const files=["features/reference-directory/DirectoryPanel.tsx","features/reference-directory/DriverFields.tsx",
  "features/reference-directory/QuickDriverDialog.tsx","features/reference-directory/RecordSelect.tsx",
  "features/reference-directory/DirectorySelect.tsx","features/shipments/components/ShipmentForm.tsx",
  "features/shipments/components/ShipmentDetail.tsx","app/shipping-directory/page.tsx",
  "components/ui/Tabs.tsx","components/ui/RecordDialog.tsx","components/ui/Combobox.tsx"];
test("directory/shipment controls translate visible prose and do not branch on Arabic copy",()=>{
  for(const file of files){
    const source=readFileSync(new URL('../src/'+file,import.meta.url),'utf8');
    assert.doesNotMatch(source,/\bar\s*\?/u,file);
    const tree=ts.createSourceFile(file,source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
    const visibleAttributes=new Set(['label','placeholder','title','aria-label','alt']);
    function visit(node){
      if(ts.isJsxText(node))assert.doesNotMatch(node.text,/[A-Za-z\u0600-\u06ff]/u,`${file}: untranslated JSX text`);
      if(ts.isJsxAttribute(node)&&visibleAttributes.has(node.name.getText(tree))&&node.initializer&&ts.isStringLiteral(node.initializer)){
        assert.doesNotMatch(node.initializer.text,/[A-Za-z\u0600-\u06ff]/u,`${file}: untranslated attribute`);
      }
      ts.forEachChild(node,visit);
    }visit(tree);
  }
});
