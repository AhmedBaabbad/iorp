import { test, expect, type Page } from "@playwright/test";

// Browser-level UI contracts use a deterministic API fixture. Server behavior is verified by backend integration tests.
async function fixture(page: Page) {
  const permissions=["commercial:customers:read","commercial:customers:update","commercial:interactions:read","commercial:followups:read",
    "shipping:directory:read","shipping:directory:write","shipping:shipments:read","shipping:shipments:create","shipping:shipments:update","shipping:shipments:ready"];
  const contacts=[{id:"contact1",name:"Stored receiver",role:"Purchasing manager",phone:"+966551234567",email:"receiver@example.com",active:true,is_default:true,version:1}];
  const sites=[{id:"site1",name:"Default site",address:"Default street 10",country:"sa",city:"riyadh",contact_id:"contact1",contact_name:"Stored receiver",location_url:"https://maps.example.test/site",active:true,is_default:true,version:1}];
  const drivers=[{id:"driver1",name:"Stored driver",affiliation:"external",phone:"+966557654321",identity_no:"ID-1",license_no:"LIC-1",license_expiry:"2035-01-01",default_vehicle_id:"vehicle1",carrier_id:null,active:true,version:1}];
  const vehicles=[{id:"vehicle1",name:"Truck",plate:"ABC 123",vehicle_type:"truck",carrier_id:null,active:true,version:1}];
  const carriers=[{id:"carrier1",name:"Carrier",phone:"+966551111111",active:true,version:1}];
  const customer={id:"c1",customer_code:"C1",name:"Browser customer",name_ar:"عميل الاختبار",name_en:"Browser customer",phone:null,email:null,
    country:"sa",city:"riyadh",city_other:null,status:"active",relationship_stage:"lead",priority_level:"medium",sector:null,notes:null,
    opportunity_source:null,sales_owner_user_id:null,sales_owner:null,key_influencer_name:null,created_by:null,created_at:"2026-11-22T00:00:00Z",updated_at:"2026-11-22T00:00:00Z"};
  let shipment:Record<string,unknown>={id:"s1",shipment_no:"DN-TEST",customer_name:customer.name,customer_id:"c1",status:"draft",delivery_method:"factory_delivery",shipment_date:"2026-11-22",lines:[],quantities:[],actions:["edit","ready"],history:[],returns:[],line_returns:{},attachments:[],missing_details:[],attempt:1};
  await page.addInitScript(()=>{localStorage.setItem("iorp.access_token","ui-test-token");localStorage.setItem("iorp.last_activity",String(Date.now()));});
  await page.context().addCookies([{name:"IORP_LOCALE",value:"en",domain:"127.0.0.1",path:"/"}]);
  await page.route("**/api/v1/**",async route=>{
    const request=route.request(),url=new URL(request.url()),path=url.pathname.replace("/api/v1","");
    const method=request.method();const body=method==="POST"||method==="PUT"?request.postDataJSON():null;
    let result:unknown=[];
    if(path==="/auth/me")result={id:"u1",organization_id:"org",organization_code:"TEST",organization_name:"UI test",organization_timezone:"UTC",full_name:"Browser tester",email:"tester@example.test",status:"active",is_organization_root:true,roles:["organization_admin"],permissions,preferred_locale:"en",effective_locale:"en",organization:{id:"org",name:"UI test",code:"TEST",has_logo:false,logo_url:null,default_locale:"en"}};
    else if(path.includes("/masterdata/lists"))result=[{id:"sa",list:"country",key:"sa",name_en:"Saudi Arabia",name_ar:"السعودية",active:true},{id:"riyadh",list:"city",key:"riyadh",parent_key:"sa",name_en:"Riyadh",name_ar:"الرياض",active:true},{id:"truck",list:"vehicle_type",key:"truck",name_en:"Truck",name_ar:"شاحنة",active:true}];
    else if(path.includes("/lookups/customers")||path.includes("/customers/lookup"))result=[customer];
    else if(path.includes("/lookups/production-orders"))result=[];
    else if(path==="/commercial/customers/c1")result=customer;
    else if(path.includes("/directory/")){
      const kind=path.includes("/contacts")?"contacts":path.includes("/sites")?"sites":path.includes("/drivers")?"drivers":path.includes("/vehicles")?"vehicles":"carriers";
      const data=({contacts,sites,drivers,vehicles,carriers} as Record<string,Array<Record<string,unknown>>>)[kind];
      if(body){const row={...body,id:kind+String(data.length+1),version:1};data.push(row);result=row;}
      else result=url.searchParams.has("page")?{items:data,total:data.length,pages:1,page:1}:data;
    }else if(path==="/shipping/shipments"&&body){
      shipment={...shipment,...body,lines:body.lines.map((line:Record<string,unknown>)=>({...line,id:"line1",line_no:1,weight:"100",weight_unit:"kg",production_order_no:null,delivered_quantity:null})),weight_total_kg:"100",gross_weight_kg:body.gross_weight??null,packaging_weight_kg:"0"};result=shipment;
    }else if(path==="/shipping/shipments/s1")result=shipment;
    else if(path.includes("/interactions")||path.includes("/follow-ups")||path.includes("/followups"))result={items:[],pages:1,total:0};
    else if(path.includes("/notifications"))result={items:[],total:0,pages:1,unread_count:0,ack_required_count:0,unread:0,latest:[],pending_ack:[]};
    await route.fulfill({status:body?201:200,contentType:"application/json",body:JSON.stringify(result)});
  });
}
test.beforeEach(async({page})=>fixture(page));

test("creates a shipment with immediate saved contact, site and driver fields",async({page})=>{
  await page.goto("/shipments/new");
  await page.getByRole("combobox",{name:"Customer",exact:true}).click();
  await page.getByRole("option",{name:/Browser customer/}).click();
  await expect(page.getByRole("textbox",{name:"Delivery address",exact:true})).toHaveValue("Default street 10");
  await expect(page.getByLabel("Recipient",{exact:true})).toHaveValue("Stored receiver");
  await page.getByRole("combobox",{name:"Saved driver",exact:true}).click();
  await page.getByRole("option",{name:/Stored driver/}).click();
  await expect(page.getByLabel("Driver phone",{exact:true})).toHaveValue("+966557654321");
  await expect(page.getByLabel("Driver",{exact:true})).toHaveAttribute("readonly","");
  await page.getByLabel("Description",{exact:true}).fill("Browser shipment");
  await page.getByLabel("Quantity",{exact:true}).fill("40");
  await page.getByLabel("Net weight per unit",{exact:true}).fill("2.5");
  await page.getByRole("button",{name:"Save draft",exact:true}).click();
  await expect(page).toHaveURL(/\/shipments\/s1/);
  await page.getByRole("tab",{name:"Items and weights"}).click();
  await expect(page.getByRole("cell",{name:"2.5 kg",exact:true})).toBeVisible();
});

test("adds a customer contact and delivery site in record dialogs",async({page})=>{
  await page.goto("/customers/c1");
  await page.getByRole("tab",{name:"Contacts",exact:true}).click();
  await expect(page).toHaveURL(/tab=contacts/);
  await page.reload();
  await expect(page.getByRole("tab",{name:"Contacts",exact:true})).toHaveAttribute("aria-selected","true");
  await expect(page.getByRole("columnheader",{name:"Role",exact:true})).toBeVisible();
  await page.getByRole("button",{name:"Add",exact:true}).click();
  const contact=page.getByRole("dialog");
  await contact.getByLabel("Name",{exact:true}).fill("New browser contact");
  await contact.getByLabel("Role",{exact:true}).fill("Warehouse manager");
  await contact.getByRole("button",{name:"Save",exact:true}).click();
  await expect(contact).toBeHidden();
  await expect(page.getByRole("cell",{name:"Warehouse manager"})).toBeVisible();
  await page.getByRole("tab",{name:"Delivery sites",exact:true}).click();
  await page.getByRole("button",{name:"Add",exact:true}).click();
  const site=page.getByRole("dialog");
  await site.getByLabel("Name",{exact:true}).fill("New browser site");
  await site.getByLabel("Address",{exact:true}).fill("Browser street 20");
  await site.getByRole("combobox",{name:"Site contact"}).click();
  await site.getByRole("option",{name:/New browser contact/}).click();
  await site.getByRole("button",{name:"Save",exact:true}).click();
  await expect(site).toBeHidden();
  await expect(page.getByRole("cell",{name:"New browser site",exact:true})).toBeVisible();
});

test("adds a driver and keeps the transport directory within the mobile viewport",async({page},info)=>{
  await page.goto("/shipping-directory");
  await page.getByRole("button",{name:"Add",exact:true}).click();
  const dialog=page.getByRole("dialog");
  await dialog.getByLabel("Name",{exact:true}).fill("New browser driver");
  await dialog.getByLabel("National ID / Iqama",{exact:true}).fill("ID-BROWSER");
  await dialog.getByRole("button",{name:"Save",exact:true}).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByRole("cell",{name:"New browser driver",exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
  await page.screenshot({path:info.outputPath("directory.png"),fullPage:true});
});

test("keeps the Arabic directory and record dialog inside a phone viewport",async({page},info)=>{
  await page.setViewportSize({width:390,height:844});
  await page.context().addCookies([{name:"IORP_LOCALE",value:"ar",domain:"127.0.0.1",path:"/"}]);
  await page.goto("/shipping-directory");
  await expect(page.locator("html")).toHaveAttribute("dir","rtl");
  await expect(page.getByRole("cell",{name:"Stored driver",exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
  await page.getByRole("button",{name:"إضافة",exact:true}).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  const box=await page.getByRole("dialog").boundingBox();
  expect(box!.width).toBeLessThanOrEqual(390);
  const save=await page.getByRole("dialog").getByRole("button",{name:"حفظ",exact:true}).boundingBox();
  expect(save!.height).toBeGreaterThanOrEqual(44);
  await page.addStyleTag({content:"nextjs-portal{display:none}"});
  await page.screenshot({path:info.outputPath("arabic-mobile-dialog.png"),fullPage:true});
});
