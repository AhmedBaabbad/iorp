import {mockLogin} from "./fixtures/auth";
import {test,expect} from "@playwright/test";
import common from "../src/i18n/locales/ar/common.json";
import shipping from "../src/i18n/locales/ar/shipping.json";

test("Arabic shipments keep page, filters and page size through navigation and reload",async({page})=>{
  const requests:URL[]=[];
  await mockLogin(page);
  await page.context().addCookies([{name:"IORP_LOCALE",value:"ar",domain:"127.0.0.1",path:"/"}]);
  await page.route("**/api/v1/**",async route=>{
    const url=new URL(route.request().url()),path=url.pathname.replace("/api/v1","");
    let result:unknown=[];
    if(path==="/auth/me")result={id:"u1",organization_id:"org",organization_code:"TEST",organization_name:"Pagination test",organization_timezone:"UTC",full_name:"Tester",email:"tester@example.test",status:"active",is_organization_root:false,roles:[],permissions:["shipping:shipments:read"],preferred_locale:"ar",effective_locale:"ar",organization:{id:"org",name:"Test",code:"TEST",has_logo:false,logo_url:null,default_locale:"ar"}};
    else if(path==="/shipping/shipments"){
      requests.push(url);
      const number=Number(url.searchParams.get("page")),size=Number(url.searchParams.get("page_size")),total=121;
      const items=Array.from({length:Math.max(0,Math.min(size,total-(number-1)*size))},(_,i)=>{
        const n=(number-1)*size+i+1;
        return {id:`s${n}`,shipment_no:`DN-${String(n).padStart(4,"0")}`,shipment_date:"2026-11-24",customer_id:null,customer_name:"عميل الاختبار",status:"draft",delivery_method:"factory_delivery",quantities:[{unit:"roll",quantity:"20"}],attempt:1,open_returns:0};
      });
      result={items,total,page:number,page_size:size,pages:Math.ceil(total/size)};
    }else if(path.includes("notifications"))result={items:[],total:0,pages:0,unread:0,unread_count:0,ack_required_count:0,latest:[],pending_ack:[]};
    await route.fulfill({contentType:"application/json",body:JSON.stringify(result)});
  });
  await page.goto("/shipments");
  await expect(page.getByRole("table",{name:shipping.listTitle})).toBeVisible();
  await expect(page.getByRole("link",{name:"DN-0001",exact:true})).toBeVisible();
  const pagination=page.getByRole("navigation",{name:common.pagination.label});
  await pagination.getByRole("button",{name:common.pagination.page.replace("{page}","2"),exact:true}).click();
  await expect(page).toHaveURL(/page=2/);
  await expect(page.getByRole("link",{name:"DN-0051",exact:true})).toBeVisible();
  expect(requests.at(-1)?.searchParams.get("page")).toBe("2");
  await page.reload();
  await expect(page.getByRole("link",{name:"DN-0051",exact:true})).toBeVisible();
  await pagination.getByRole("combobox").selectOption("25");
  await expect(page).toHaveURL(/page_size=25/);
  await expect(page.getByRole("link",{name:"DN-0001",exact:true})).toBeVisible();
  expect(requests.at(-1)?.searchParams.get("page")).toBe("1");
  expect(requests.at(-1)?.searchParams.get("page_size")).toBe("25");
  await expect(page.getByRole("table").getByRole("row")).toHaveCount(26);
  await expect(page.locator("html")).toHaveAttribute("dir","rtl");
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
});
