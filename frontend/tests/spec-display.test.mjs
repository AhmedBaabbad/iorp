import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';
import {formatSpecValue,formatSpecification,specificationRows} from '../src/lib/spec-value.ts';
import {normalizeSpecDraft} from '../src/lib/spec-rows.ts';
import {specText} from '../src/lib/units.ts';

const thickness={key:'thickness_mm',name_ar:'السماكة',name_en:'Thickness',kind:'number',allows_range:true,unit:'mm'};
test('every specification formatter shares range precision, template names and units',()=>{
  const spec={thickness_mm:{min:.7,max:.75}};
  assert.equal(formatSpecValue(spec.thickness_mm),'0.70 – 0.75');
  assert.equal(specText(spec),'0.70 – 0.75');
  assert.equal(formatSpecification(spec,{properties:[thickness]}),'Thickness: 0.70 – 0.75 mm');
  assert.equal(specificationRows(spec,{properties:[thickness],locale:'ar'})[0].text,'السماكة: 0.70 – 0.75 mm');
  assert.equal(formatSpecValue({historical:{min:.7,max:.75}}),'historical: 0.70 – 0.75');
  assert.equal(formatSpecValue([{min:.7,max:.75}]),'0.70 – 0.75');
});
test('saving numeric draft text preserves typed state and sends a numeric interval',()=>{
  const draft={thickness_mm:'0.70-0.75',description:'0.70',historicalEmpty:''};
  assert.deepEqual(normalizeSpecDraft(draft,[thickness]),{thickness_mm:{min:.7,max:.75},description:'0.70',historicalEmpty:''});
  assert.equal(draft.thickness_mm,'0.70-0.75');
  assert.deepEqual(normalizeSpecDraft({thickness_mm:'0.70'},[thickness]),{thickness_mm:.7});
});

function violations(text,file='screen.tsx'){
  const source=ts.createSourceFile(file,text,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX),bad=[];
  function visit(node){
    if(ts.isCallExpression(node)&&['String','JSON.stringify'].includes(node.expression.getText(source))){
      const argument=node.arguments[0]?.getText(source)??'';
      let current=node.parent,render=false,owner='';
      while(current){
        if(ts.isJsxExpression(current))render=true;
        if(ts.isFunctionDeclaration(current)&&current.name)owner+=' '+current.name.text;
        current=current.parent;
      }
      const specification=/\b(?:spec|specs|spec_summary|requested_spec_json|target_spec_json)\b/i.test(argument);
      const valueInRenderer=/^(value|raw|val|v)$/.test(argument)&&/Spec|ReadableValue/.test(owner);
      if(render&&(specification||valueInRenderer))bad.push(source.getLineAndCharacterOfPosition(node.pos).line+1);
      if(!render&&(specification||valueInRenderer)&&/^(?:\s*(?:otherSpecs|specValue|specSummary))+$/.test(owner))bad.push(source.getLineAndCharacterOfPosition(node.pos).line+1);
    }
    ts.forEachChild(node,visit);
  }
  visit(source);return bad;
}
test('guard detects raw specification renderers, while permitting JSON persistence',()=>{
  for(const text of ['const x=<td>{String(d.spec_summary?.[k])}</td>;','const x=<pre>{JSON.stringify(item.requested_spec_json)}</pre>;','function ReadableValue({value}){return <b>{String(value)}</b>}'])assert.equal(violations(text).length,1,text);
  assert.deepEqual(violations('function save(){return JSON.stringify(spec)}; const x=<input value={String(id)}/>;'),[]);
});
test('TSX specification displays never bypass the shared formatter',()=>{
  const root=path.resolve('src'),bad=[];
  for(const file of fs.readdirSync(root,{recursive:true}).filter(file=>file.endsWith('.tsx'))){
    const found=violations(fs.readFileSync(path.join(root,file),'utf8'),file);
    for(const line of found)bad.push(`${file}:${line}`);
  }
  assert.deepEqual(bad,[],'Use formatSpecValue/formatSpecification instead of raw coercion: '+bad.join(', '));
});
