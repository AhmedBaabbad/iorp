import {test,expect} from "@playwright/test";
import {mockLogin} from "./fixtures/auth";
import ar from "../src/i18n/locales/ar/production.json";
import directory from "../src/i18n/locales/ar/directory.json";

test("returns an allocation, corrects the item, reallocates and reads Arabic history",async({page},info)=>{
  await mockLogin(page);await page.context().addCookies([{name:"IORP_LOCALE",value:"ar",domain:"127.0.0.1",path:"/"}]);
  let returned=false,edited=false,attached=false;
  const oldSpec={color:"blue",thickness:{min:.7,max:.75}};
  const product={id:"product",key:"film",name_ar:"فيلم",name_en:"Film",kind:"finished",active:true,default_unit:"kg",properties:[{key:"color",name_ar:"اللون",name_en:"Color",kind:"text"},{key:"thickness",name_ar:"السماكة",name_en:"Thickness",kind:"number",allows_range:true}]};
  const allocation=(n:number)=>({id:`a${n}`,production_order_id:"order",production_order_number:"PO-REWORK",production_order_status:"draft",allocated_quantity:"50",status:n===1&&returned?"released":"active",created_at:"2026-11-26T10:00:00Z",released_at:n===1&&returned?"2026-11-26T11:00:00Z":null,release_reason:n===1&&returned?"تصحيح مواصفة الصنف":null,target_spec_json_snapshot:oldSpec,product_type_snapshot:"film",unit:"kg"});
  const items=()=>[1,2].map(n=>({id:`i${n}`,line_no:n,product_type:"film",required_quantity:"50",unit:"kg",notes:null,target_spec_json:n===1&&edited?{color:"red",thickness:{min:.8,max:.85}}:oldSpec,allocated_quantity:n===1&&returned&&!attached?"0":"50",active_allocated_quantity:n===1&&returned&&!attached?"0":"50",released_allocated_quantity:n===1&&returned?"50":"0",remaining_quantity:n===1&&returned&&!attached?"50":"0",planning_state:n===1&&returned&&!attached?"ready_for_planning":"planned",allocations:[allocation(n)]}));
  const demand=()=>({id:"demand",demand_number:"PD-REWORK",customer:{id:"customer",code:"C",name:"عميل الاختبار"},quote:null,request_date:"2026-11-26",requested_delivery_date:null,priority:"normal",status:returned&&!attached?"partially_planned":"planned",notes:null,created_by:"Planner",created_at:"2026-11-26T10:00:00Z",items:items(),total_required:"100",total_active_allocated:returned&&!attached?"50":"100",total_allocated:returned&&!attached?"50":"100",total_released_allocated:returned?"50":"0",total_remaining:returned&&!attached?"50":"0",allocation_percentage:returned&&!attached?"50":"100",item_count:2,total_quantity:"100",quantities_by_unit:{kg:"100"}});
  const events=()=>[{id:"event-return",action:"production_allocation.released",actor_name:"Planner",created_at:"2026-11-26T11:00:00Z",details:{schema_version:1,changes:[{field:"allocation_status",old:"active",new:"released"}],reason:"تصحيح مواصفة الصنف",related:{production_order_number:"PO-REWORK"}}},...(edited?[{id:"event-edit",action:"production_demand.item_updated",actor_name:"Planner",created_at:"2026-11-26T11:01:00Z",details:{schema_version:1,changes:[{field:"target_spec_json.thickness",old:oldSpec.thickness,new:{min:.8,max:.85}}],reason:null,related:{}}}]:[])];
  await page.route("**/api/v1/**",async route=>{
    const req=route.request(),path=new URL(req.url()).pathname.replace("/api/v1","");let result:unknown=[];
    if(path==="/auth/me")result={id:"u",organization_id:"org",organization_code:"TEST",organization_name:"Rework",organization_timezone:"UTC",full_name:"Planner",email:"planner@example.test",status:"active",is_organization_root:false,roles:[],permissions:["production:demands:read","production:demands:update","production:planning:read","production:planning:allocate","production:planning:release_allocation","production:production_orders:read","masterdata:products:read","masterdata:lists:read"],preferred_locale:"ar",effective_locale:"ar",organization:{id:"org",name:"Rework",code:"TEST",has_logo:false,default_locale:"ar"}};
    else if(path==="/masterdata/products")result=[product];
    else if(path==="/production/allocations/a1/release"&&req.method()==="POST"){expect(req.postDataJSON().reason).toBe("تصحيح مواصفة الصنف");returned=true;result={allocation:allocation(1),demand:demand()};}
    else if(path==="/production/demands/demand/items/i1"&&req.method()==="PATCH"){
      expect(req.postDataJSON().target_spec_json).toEqual({color:"red",thickness:{min:.8,max:.85}});edited=true;result=items()[0];
    }else if(path==="/production/demands/demand")result=demand();
    else if(path==="/production/planning/demands")result={items:[demand()],total:1,page:1,page_size:50,pages:1,hidden_by_status:0};
    else if(path==="/production/planning/eligible-orders")result=[{id:"order",production_order_number:"PO-REWORK",status:"draft",work_center_name:"Line",product_type:"film",unit:"kg",planned_quantity:"50",planned_start_date:"2030-01-01",planned_end_date:"2030-01-02",finish_overdue:false}];
    else if(path==="/production/orders/order/allocations"&&req.method()==="POST"){expect(req.postDataJSON()).toEqual({production_demand_item_id:"i1",allocated_quantity:"50"});attached=true;result={id:"order"};}
    else if(path==="/production/production-orders/order")result={id:"order",organization_id:"org",production_order_number:"PO-REWORK",work_center_id:"wc",product_type:"film",planned_quantity:"100",unit:"kg",priority:"normal",status:"draft",planned_start_date:"2030-01-01",planned_end_date:"2030-01-02",created_at:"2026-11-26T10:00:00Z",updated_at:"2026-11-26T11:00:00Z",allocations:[],lines:[],target_spec_json:items()[0].target_spec_json,notes:null,lifecycle:{status_version:1,actual_start_at:null,actual_end_at:null,start_overdue:false,finish_overdue:false,terminal:false,actions:[]},reschedule_history:[]};
    else if(path.startsWith("/record-history/"))result={items:returned?events().sort((a,b)=>b.created_at.localeCompare(a.created_at)):[],total:returned?events().length:0,pages:1};
    else if(path.includes("/notifications"))result={items:[],total:0,pages:1,unread_count:0,ack_required_count:0,latest:[],pending_ack:[]};
    else if(req.method()!=="GET")throw new Error(`Unhandled mutation: ${req.method()} ${path}`);
    await route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(result)});
  });
  const a=ar.allocation,d=ar.demands;
  await page.goto("/production/demands/demand");
  await page.getByRole("button",{name:a.release,exact:true}).first().click();
  let dialog=page.getByRole("dialog");await dialog.getByLabel(a.reason,{exact:true}).fill("تصحيح مواصفة الصنف");
  await dialog.getByRole("button",{name:a.release,exact:true}).click();
  await page.getByRole("button",{name:d.editItem,exact:true}).click();dialog=page.getByRole("dialog");
  await dialog.getByLabel("اللون",{exact:true}).fill("red");await dialog.getByLabel("السماكة",{exact:true}).fill("0.80-0.85");
  expect((await dialog.boundingBox())!.width).toBeLessThanOrEqual(page.viewportSize()!.width);
  await dialog.getByRole("button",{name:directory.save,exact:true}).click();await expect(dialog).toBeHidden();
  await expect(page.getByText("0.70 – 0.75",{exact:false}).first()).toBeVisible();
  await page.getByRole("link",{name:a.allocateNow,exact:true}).click();
  await page.getByRole("checkbox",{name:`${a.select} PD-REWORK 1`,exact:true}).check();
  await page.getByRole("button",{name:a.addToExisting,exact:true}).click();
  await page.getByRole("button",{name:a.addToThisOrder,exact:true}).click();await expect(page).toHaveURL(/production-orders\/order$/);expect(attached).toBe(true);
  await page.goto("/production/demands/demand?tab=history");
  const history=page.getByRole("tabpanel");
  await expect(history.getByText(ar.recordHistory.events.production_demand_item_updated,{exact:true})).toBeVisible();
  await expect(history.getByText("0.70 – 0.75",{exact:true})).toBeVisible();await expect(history.getByText("0.80 – 0.85",{exact:true})).toBeVisible();
  await page.screenshot({path:info.outputPath("demand-rework-history-ar.png")});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
});
