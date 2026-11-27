import {mockLogin} from "./fixtures/auth";
import {test,expect} from "@playwright/test";
import ar from "../src/i18n/locales/ar/production.json";
import directory from "../src/i18n/locales/ar/directory.json";

test("extends an overdue order in Arabic without leaving its detail page",async({page},info)=>{
  const text=ar.productionOrders.reschedule;
  const lifecycle={status_version:1,actual_start_at:"2026-01-01T08:00:00Z",actual_end_at:null,start_overdue:false,finish_overdue:true,terminal:false,actions:[]};
  let order={id:"reschedule-order",organization_id:"org",production_order_number:"PO-RESCHEDULE",work_center_id:"wc",product_type:"roll",planned_quantity:"20",unit:"roll",priority:"normal",status:"in_progress",planned_start_date:"2026-01-01",planned_end_date:"2026-01-02",created_by_user_id:"u1",created_at:"2026-01-01T00:00:00Z",updated_at:"2026-01-01T00:00:00Z",allocations:[],lines:[],target_spec_json:null,notes:null,lifecycle,reschedule_history:[] as unknown[]};
  await mockLogin(page);
  await page.context().addCookies([{name:"IORP_LOCALE",value:"ar",domain:"127.0.0.1",path:"/"}]);
  await page.route("**/api/v1/**",async route=>{
    const request=route.request(),path=new URL(request.url()).pathname.replace("/api/v1","");
    let result:unknown=[];
    if(path==="/auth/me")result={id:"u1",organization_id:"org",organization_code:"TEST",organization_name:"UI test",organization_timezone:"UTC",full_name:"Browser tester",email:"tester@example.test",status:"active",is_organization_root:false,roles:[],permissions:["production:production_orders:read","production:production_orders:update"],preferred_locale:"ar",effective_locale:"ar",organization:{id:"org",name:"UI test",code:"TEST",has_logo:false,logo_url:null,default_locale:"ar"}};
    else if(path.endsWith("/reschedule")&&request.method()==="POST"){
      const body=request.postDataJSON();
      expect(body.planned_start_date).toBeUndefined();
      order={...order,planned_end_date:body.planned_end_date,lifecycle:{...lifecycle,finish_overdue:false},reschedule_history:[{id:"event1",created_at:"2026-11-24T12:00:00Z",actor_user_id:"u1",actor_name:"Browser tester",old_start:order.planned_start_date,new_start:order.planned_start_date,old_end:order.planned_end_date,new_end:body.planned_end_date,reason:body.reason}]};
      result=order;
    }else if(path==="/record-history/production_order/reschedule-order")result={items:order.reschedule_history.map((event)=>({...(event as object),action:"production_order.rescheduled",details:{...(event as object)}})),total:order.reschedule_history.length,pages:1};
    else if(path==="/production/production-orders/reschedule-order")result=order;
    else if(path.includes("/notifications"))result={items:[],total:0,pages:1,unread_count:0,ack_required_count:0,unread:0,latest:[],pending_ack:[]};
    else if(path.includes("/signatures"))result={items:[],signatures:[],requirements:[]};
    await route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(result)});
  });
  await page.goto("/production-orders/reschedule-order");
  const extend=page.getByRole("button",{name:text.extendFinish,exact:true});
  await expect(extend).toBeVisible();
  await extend.click();
  const dialog=page.getByRole("dialog");
  await expect(dialog.getByLabel(text.start,{exact:true})).toBeDisabled();
  await dialog.getByLabel(text.end,{exact:true}).fill("2030-01-10");
  await dialog.getByLabel(text.reason,{exact:true}).fill("تأخر التشغيل بسبب الصيانة");
  const bounds=await dialog.boundingBox();
  expect(bounds!.width).toBeLessThanOrEqual(page.viewportSize()!.width);
  await page.screenshot({path:info.outputPath("reschedule-ar.png")});
  await dialog.getByRole("button",{name:directory.save,exact:true}).click();
  await expect(dialog).toBeHidden();
  await expect(extend).toHaveCount(0);
  await page.getByRole("tab",{name:ar.recordHistory.title,exact:true}).click();
  await expect(page.getByRole("region",{name:ar.recordHistory.title,exact:true}).getByText("تأخر التشغيل بسبب الصيانة")).toBeVisible();
  await expect(page).toHaveURL(/\/production-orders\/reschedule-order\?tab=history$/);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
});
