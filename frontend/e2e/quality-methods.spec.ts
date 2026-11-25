import {test,expect} from "@playwright/test";
import {mockLogin} from "./fixtures/auth";
import ar from "../src/i18n/locales/ar/quality.json";

test("selects an official test method in Arabic and saves both official names",async({page})=>{
  await mockLogin(page);
  await page.context().addCookies([{name:"IORP_LOCALE",value:"ar",domain:"127.0.0.1",path:"/"}]);
  const method={id:"method",list:"test_method",key:"micrometer",name_ar:"ميكرومتر",name_en:"Micrometer",active:true,parent_key:null,sort_order:1};
  const parameters:Record<string,unknown>[]=[];
  await page.route("**/api/v1/**",async route=>{
    const request=route.request(),path=new URL(request.url()).pathname.replace("/api/v1","");let result:unknown=[];
    if(path==="/auth/me")result={id:"u1",organization_id:"org",organization_code:"TEST",organization_name:"UI test",organization_timezone:"UTC",full_name:"Browser tester",email:"tester@example.test",status:"active",is_organization_root:false,roles:[],permissions:["quality:specifications:read","quality:specifications:create","masterdata:lists:read"],preferred_locale:"ar",effective_locale:"ar",organization:{id:"org",name:"UI test",code:"TEST",has_logo:false,logo_url:null,default_locale:"ar"}};
    else if(path==="/masterdata/lists")result=[method];
    else if(path==="/quality/quality-test-parameters"&&request.method()==="POST"){
      const body=request.postDataJSON();expect(body.method_ar).toBe(method.name_ar);expect(body.method_en).toBe(method.name_en);
      const parameter={...body,id:"parameter",sort_order:1,is_active:true};parameters.push(parameter);result=parameter;
    }else if(path==="/quality/quality-test-parameters")result={items:parameters,total:parameters.length,page:1,page_size:50,pages:parameters.length?1:0};
    else if(path.includes("/notifications"))result={items:[],total:0,pages:1,unread_count:0,ack_required_count:0,latest:[],pending_ack:[]};
    else if(request.method()!=="GET")throw new Error(`Unhandled fixture mutation: ${request.method()} ${path}`);
    await route.fulfill({status:request.method()==="POST"?201:200,contentType:"application/json",body:JSON.stringify(result)});
  });
  const t=ar.parameters;
  await page.goto("/quality-test-parameters");
  const form=page.getByRole("form",{name:t.newTitle});
  await form.getByLabel(t.fields.code,{exact:true}).fill("METHOD-TEST");
  await form.getByLabel(t.fields.nameAr,{exact:true}).fill("اختبار قياس");
  await form.getByLabel(t.fields.nameEn,{exact:true}).fill("Measurement test");
  await form.getByRole("combobox",{name:t.fields.method,exact:true}).click();
  await page.getByRole("option",{name:method.name_ar,exact:true}).click();
  await expect(form.getByLabel(t.fields.method_ar,{exact:true})).toHaveCount(0);
  await form.getByRole("button",{name:t.add,exact:true}).click();
  const row=page.getByRole("row").filter({hasText:"METHOD-TEST"});
  await expect(row.getByText(method.name_ar,{exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
});
