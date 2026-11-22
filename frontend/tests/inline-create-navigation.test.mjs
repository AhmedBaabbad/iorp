import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,readdirSync} from 'node:fs';
import ts from 'typescript';

test('form components and contextual add actions never navigate to a creation page',()=>{
  const root=new URL('../src/',import.meta.url),violations=[];
  const contextual=new Set(['OrderDowntimeSection','OrderWasteSection','OrderQualitySection','QualityCheckDetail','ListCreateDialog']);
  for(const file of readdirSync(root,{recursive:true}).filter(file=>file.endsWith('.tsx'))){
    const source=readFileSync(new URL(file.replaceAll('\\','/'),root),'utf8');
    const tree=ts.createSourceFile(file,source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
    function staticText(node){
      if(!node)return '';
      if(ts.isStringLiteralLike(node))return node.text;
      if(ts.isJsxExpression(node))return staticText(node.expression);
      if(ts.isTemplateExpression(node))return node.head.text+node.templateSpans.map(span=>'{value}'+span.literal.text).join('');
      return node.getText(tree);
    }
    function inspect(node,component){
      if(ts.isJsxOpeningElement(node)||ts.isJsxSelfClosingElement(node)){
        if(['Link','a'].includes(node.tagName.getText(tree))){
          const attrs=node.attributes.properties.filter(ts.isJsxAttribute);
          const href=staticText(attrs.find(a=>a.name.getText(tree)==='href')?.initializer);
          const target=staticText(attrs.find(a=>a.name.getText(tree)==='target')?.initializer);
          if(/\/new(?:[/?#]|$)/.test(href))violations.push(`${file}: ${component} links to ${href}`);
          if(target==='_blank'&&!(component==='ListCreateDialog'&&href.startsWith('/master-data/lists?')))
            violations.push(`${file}: ${component} opens an add link in a new tab`);
        }
      }
      if(ts.isCallExpression(node)&&ts.isPropertyAccessExpression(node.expression)&&node.expression.name.text==='push'
        &&/\/new(?:[/?#]|$)/.test(staticText(node.arguments[0])))violations.push(`${file}: ${component} pushes a creation route`);
      ts.forEachChild(node,child=>inspect(child,component));
    }
    function components(node){
      if(ts.isFunctionDeclaration(node)&&node.name&&node.body&&(/(?:Form|Fields|Select)$/.test(node.name.text)||contextual.has(node.name.text)))inspect(node.body,node.name.text);
      else if(ts.isVariableDeclaration(node)&&ts.isIdentifier(node.name)&&node.initializer
        &&(ts.isArrowFunction(node.initializer)||ts.isFunctionExpression(node.initializer))
        &&(/(?:Form|Fields|Select)$/.test(node.name.text)||contextual.has(node.name.text)))inspect(node.initializer.body,node.name.text);
      else ts.forEachChild(node,components);
    }components(tree);
  }
  assert.deepEqual(violations,[]);
});
