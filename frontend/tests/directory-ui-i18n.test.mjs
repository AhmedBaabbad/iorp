import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
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

function directoryKeyUsage() {
  const used=new Set();
  const root=new URL('../src/',import.meta.url);
  for(const file of readdirSync(root,{recursive:true}).filter(file=>/\.[jt]sx?$/.test(file))){
    const source=readFileSync(new URL(file.replaceAll('\\','/'),root),'utf8');
    if(!/useTranslations\(["']directory["']\)/.test(source))continue;
    const tree=ts.createSourceFile(file,source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
    const translators=new Set();
    function bindings(node){
      if(ts.isVariableDeclaration(node)&&ts.isIdentifier(node.name)&&node.initializer&&ts.isCallExpression(node.initializer)
        &&node.initializer.expression.getText(tree)==='useTranslations'&&node.initializer.arguments[0]?.text==='directory')translators.add(node.name.text);
      ts.forEachChild(node,bindings);
    }bindings(tree);
    function literals(node,consume){
      if(ts.isStringLiteralLike(node))consume(node.text);
      ts.forEachChild(node,child=>literals(child,consume));
    }
    function calls(node){
      if(ts.isCallExpression(node)&&translators.has(node.expression.getText(tree))&&node.arguments[0]){
        literals(node.arguments[0],key=>used.add(key));
      }
      // DirectoryPanel's dynamic field labels are backed by its field/column declarations.
      if(file.endsWith('DirectoryPanel.tsx')){
        if(ts.isVariableDeclaration(node)&&['fields','columns'].includes(node.name.getText(tree))&&node.initializer){
          literals(node.initializer,key=>used.add(`fields.${key}`));
        }
        if(ts.isCallExpression(node)&&['textInput','label'].includes(node.expression.getText(tree))){
          for(const arg of node.arguments)if(ts.isStringLiteralLike(arg))used.add(`fields.${arg.text}`);
        }
      }
      // The shipping directory page maps these kinds to fields.${kind} tab labels.
      if(file.replaceAll('\\','/').endsWith('app/shipping-directory/page.tsx')&&ts.isArrayLiteralExpression(node)){
        for(const element of node.elements)if(ts.isStringLiteralLike(element))used.add(`fields.${element.text}`);
      }
      ts.forEachChild(node,calls);
    }calls(tree);
  }
  // API errors are selected dynamically from the application's recognized error codes.
  const errors=readFileSync(new URL('../src/lib/api-error-handler.ts',import.meta.url),'utf8');
  for(const match of errors.matchAll(/["']([A-Z][A-Z_]+)["']/g))used.add(`errors.${match[1]}`);
  return used;
}

test("directory translations have semantic names and no unused keys in either language",()=>{
  const used=directoryKeyUsage();
  for(const locale of ['ar','en']){
    const dictionary=JSON.parse(readFileSync(new URL(`../src/i18n/locales/${locale}/directory.json`,import.meta.url),'utf8'));
    const unused=[];
    function check(node,prefix=''){
      for(const [key,value] of Object.entries(node)){
        const path=prefix?`${prefix}.${key}`:key;
        assert.doesNotMatch(key,/\d$/u,`${locale}: numbered translation key ${path}`);
        if(typeof value==='object')check(value,path);
        else if(!used.has(path))unused.push(path);
      }
    }check(dictionary);
    assert.deepEqual(unused,[],`${locale}: unused directory translations`);
  }
});
