import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,readdirSync} from 'node:fs';
import ts from 'typescript';

// These are technical measurement units, not commercial/production quantities.
const technicalUnits=new Set([
  'features/quality-specifications/components/ParameterFormFields.tsx',
  'features/quality-specifications/components/TestParametersPage.tsx',
]);
// Every remaining mapped native select was reviewed. New cases require an explicit reason.
const exceptions=JSON.parse(readFileSync(new URL('./fixtures/native-select-enums.json',import.meta.url),'utf8'));
const normalizedMaps=maps=>maps.map(value=>value.replace(/\s+/g,' ').trim()).join('\n');
test('API record selections never use native selects or a separate search input',()=>{
  const root=new URL('../src/',import.meta.url),violations=[];
  for(const path of readdirSync(root,{recursive:true}).filter(p=>p.endsWith('.tsx'))){
    const file=path.replaceAll('\\','/'),source=readFileSync(new URL(file,root),'utf8');
    const tree=ts.createSourceFile(file,source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
    const attrs=node=>Object.fromEntries(node.attributes.properties.filter(ts.isJsxAttribute).map(a=>[a.name.getText(tree),a.initializer?.getText(tree)??'']));
    function visit(node){
      if((ts.isJsxOpeningElement(node)||ts.isJsxSelfClosingElement(node))&&node.tagName.getText(tree)==='RecordCombobox'
        &&!node.attributes.properties.some(attribute=>ts.isJsxAttribute(attribute)&&attribute.name.getText(tree)==='aria-label'))
        violations.push(`${file}: record choice has no explicit translated accessible label`);
      if(ts.isFunctionDeclaration(node)&&node.name&&/(?:Form|Picker|Lookup|OrderLines)$/.test(node.name.text)){
        const body=node.body?.getText(tree)??'';
        if(/type=["']search["']/.test(body)&&/<(?:select|RecordCombobox)\b/.test(body))
          violations.push(`${file}: ${node.name.text} pairs a separate search with its choice control`);
      }
      if(ts.isJsxElement(node)&&node.openingElement.tagName.getText(tree)==='select'){
        const maps=[];
        function collect(child){if(ts.isCallExpression(child)&&ts.isPropertyAccessExpression(child.expression)&&child.expression.name.text==='map')maps.push(child.expression.expression.getText(tree));ts.forEachChild(child,collect);}
        node.children.forEach(collect);
        const records=maps.filter(value=>/\b(?:customers|suppliers|materials|centers|products|orders|workCenters|eligibleOwners|eligibleUsers|eligibleAssignees|parameters|specifications|reasonChoices|categoryChoices|permGroups)\b/.test(value));
        if(records.length)violations.push(`${file}: native API select ${records.join(', ')}`);
        if(maps.length&&!exceptions.some(entry=>entry.file===file&&entry.reason&&normalizedMaps(entry.maps)===normalizedMaps(maps)))
          violations.push(`${file}: unreviewed native select ${maps.join(', ')}`);
        let container=node.parent;
        while(container!==tree&&!(ts.isJsxElement(container)&&container.openingElement.tagName.getText(tree)==='label'))container=container.parent;
        if(container!==tree&&/type=["']search["']/.test(container.getText(tree)))violations.push(`${file}: paired search and select`);
      }
      if(ts.isJsxSelfClosingElement(node)&&node.tagName.getText(tree)==='input'){
        const attributes=attrs(node),value=attributes.value??'';
        if(/\b(?:unit|secondaryUnit)\b/.test(value)&&!technicalUnits.has(file)&&!('readOnly' in attributes)&&!/["'](?:hidden|checkbox)["']/.test(attributes.type??''))
          violations.push(`${file}: free-text unit ${value}`);
      }
      ts.forEachChild(node,visit);
    }visit(tree);
  }
  assert.deepEqual(violations,[]);
});
