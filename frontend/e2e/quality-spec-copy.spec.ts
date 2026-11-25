import {test,expect} from "@playwright/test";
import {mockLogin} from "./fixtures/auth";
import ar from "../src/i18n/locales/ar/quality.json";
import directory from "../src/i18n/locales/ar/directory.json";

test("copies a superseded specification in an Arabic dialog then opens its independent draft",async({page},info)=>{
  await mockLogin(page);
  await page.context().addCookies([{name:"IORP_LOCALE",value:"ar",domain:"127.0.0.1",path:"/"}]);
  const source={id:"source-spec",code:"SPEC-SOURCE",revision:3,title:"مواصفة أصلية",product_type:"film",grade:"A",status:"superseded",activated_at:null,activated_by_name:null,created_by_name:"Browser tester",updated_at:"2026-11-25T00:00:00Z",notes:null,lines:[],actions:["copy"]};
  let copied:Record<string,unknown>|null=null;
  await page.route("**/api/v1/**",async route=>{
    const req=route.request(),path=new URL(req.url()).pathname.replace("/api/v1","");
    let result:unknown=[];
    if(path==="/auth/me")result={id:"u1",organization_id:"org",organization_code:"TEST",organization_name:"UI test",organization_timezone:"UTC",full_name:"Browser tester",email:"tester@example.test",status:"active",is_organization_root:false,roles:[],permissions:["quality:specifications:read","quality:specifications:create","quality:specifications:update"],preferred_locale:"ar",effective_locale:"ar",organization:{id:"org",name:"UI test",code:"TEST",has_logo:false,logo_url:null,default_locale:"ar"}};
    else if(path==="/quality/quality-specifications/source-spec/copy"&&req.method()==="POST"){
      const body=req.postDataJSON();
      expect(body.title).toBe(source.title+ar.specifications.copySuffix);
      copied={...source,...body,id:"new-spec",status:"draft",revision:1,actions:["edit","activate","copy"]};result=copied;
    }else if(path==="/quality/quality-specifications/source-spec")result=source;
    else if(path==="/quality/quality-specifications/new-spec")result=copied;
    else if(path.includes("/notifications"))result={items:[],total:0,pages:1,unread_count:0,ack_required_count:0,latest:[],pending_ack:[]};
    else if(req.method()!=="GET")throw new Error(`Unhandled fixture mutation: ${req.method()} ${path}`);
    await route.fulfill({status:req.method()==="POST"?201:200,contentType:"application/json",body:JSON.stringify(result)});
  });
  await page.goto("/quality-specifications/source-spec");
  await page.getByRole("button",{name:ar.specifications.copy,exact:true}).click();
  const dialog=page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(page).toHaveURL(/\/quality-specifications\/source-spec$/);
  await dialog.getByLabel(ar.specifications.fields.code,{exact:true}).fill("SPEC-INDEPENDENT");
  expect((await dialog.boundingBox())!.width).toBeLessThanOrEqual(page.viewportSize()!.width);
  await page.screenshot({path:info.outputPath("quality-copy-ar.png")});
  await dialog.getByRole("button",{name:directory.save,exact:true}).click();
  await expect(page).toHaveURL(/\/quality-specifications\/new-spec\/edit$/);
  await expect(page.getByLabel(ar.specifications.fields.code,{exact:true})).toHaveValue("SPEC-INDEPENDENT");
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
});
