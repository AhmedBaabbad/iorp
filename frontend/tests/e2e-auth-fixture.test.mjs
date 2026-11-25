import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

test("every browser spec uses the shared dummy sign-in fixture",()=>{
  const root=new URL("../e2e/",import.meta.url);
  const specs=fs.readdirSync(root).filter(file=>file.endsWith(".spec.ts"));
  assert.ok(specs.length>=5);
  for(const file of specs){
    const source=fs.readFileSync(new URL(file,root),"utf8");
    assert.match(source,/import\s*\{mockLogin\}\s*from\s*["']\.\/fixtures\/auth["']/ ,file);
    assert.match(source,/await mockLogin\(page\)/,file);
    assert.doesNotMatch(source,/localStorage\.setItem\(["']iorp\.access_token/,file);
  }
});
