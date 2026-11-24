import {test,expect,type Page} from '@playwright/test';
import c from '../src/i18n/locales/ar/commercial.json';
import p from '../src/i18n/locales/ar/production.json';
import common from '../src/i18n/locales/ar/common.json';

async function fixture(page:Page){
  const customer={id:'customer',customer_code:'C-RANGE',code:'C-RANGE',name:'عميل النطاق',name_ar:'عميل النطاق',name_en:'Range customer',status:'active'};
  const products=[{id:'product',key:'film',name_ar:'منتج النطاق',name_en:'Range product',active:true,default_unit:'roll',properties:[{key:'thickness_mm',name_ar:'السماكة',name_en:'Thickness',kind:'number',allows_range:true,unit:'mm',required:true,options:null}]}];
  let quote:Record<string,unknown>|null=null,demand:Record<string,unknown>|null=null;
  await page.addInitScript(()=>{localStorage.setItem('iorp.access_token','spec-test-token');localStorage.setItem('iorp.last_activity',String(Date.now()));});
  await page.context().addCookies([{name:'IORP_LOCALE',value:'ar',domain:'127.0.0.1',path:'/'}]);
  await page.route('**/api/v1/**',async route=>{
    const req=route.request(),path=new URL(req.url()).pathname.replace('/api/v1','');let result:unknown=[];
    if(path==='/auth/me')result={id:'user',organization_id:'org',organization_name:'Range test',organization_code:'TEST',organization_timezone:'UTC',full_name:'Browser tester',email:'test@example.test',status:'active',is_organization_root:false,roles:[],permissions:['commercial:quotes:read','commercial:quotes:create','commercial:customers:read','production:demands:read','production:demands:create','production:demands:release','production:planning:read','masterdata:products:read','masterdata:lists:read'],preferred_locale:'ar',effective_locale:'ar',organization:{id:'org',name:'Range test',code:'TEST',has_logo:false,default_locale:'ar'}};
    else if(path==='/masterdata/products')result=products;
    else if(path.endsWith('/customers/lookup')||path==='/production/demand-lookups/customers')result=[customer];
    else if(path==='/commercial/customers/customer')result=customer;
    else if(path==='/masterdata/settings')result={vat_rate:'15',default_currency:'SAR'};
    else if(path==='/commercial/quote-settings/validity')result={quote_validity_days:10,document_language:'ar'};
    else if(path==='/commercial/customers/customer/quotes'&&req.method()==='POST'){
      const body=req.postDataJSON();expect(body.items[0].requested_spec_json.thickness_mm).toEqual({min:.7,max:.75});
      quote={...body,customer_id:customer.id,id:'quote-range',quote_number:'Q-RANGE',status:'draft',sample_id:null,allowed_actions:[],history:[],orders:[],subtotal_amount:'20',discount_amount:'0',tax_amount:'3',total_amount:'23',items:body.items.map((item:Record<string,unknown>)=>({...item,line_total:'20'}))};result=quote;
    }else if(path==='/commercial/quotes/quote-range')result=quote;
    else if(path==='/production/demands'&&req.method()==='POST'){
      const body=req.postDataJSON();expect(body.items[0].target_spec_json.thickness_mm).toEqual({min:.7,max:.75});
      demand={...body,id:'demand-range',demand_number:'PD-RANGE',status:'draft',customer,quote:null,sales_order:null,item_count:1,total_quantity:'10',quantities_by_unit:{roll:'10'},created_by:'Browser tester',created_at:'2026-11-24T00:00:00Z',updated_at:'2026-11-24T00:00:00Z',total_required:'10',total_allocated:'0',total_active_allocated:'0',total_released_allocated:'0',total_remaining:'10',allocation_percentage:'0',spec_summary:body.items[0].target_spec_json,items:body.items.map((item:Record<string,unknown>)=>({...item,id:'item-range',allocated_quantity:'0',active_allocated_quantity:'0',released_allocated_quantity:'0',remaining_quantity:'10',planning_state:'ready_for_planning',allocations:[]}))};result=demand;
    }else if(path==='/production/demands/demand-range/status'){demand={...demand,status:req.postDataJSON().status};result=demand;}
    else if(path==='/production/demands/demand-range')result=demand;
    else if(path==='/production/planning/demands')result={items:demand?[demand]:[],total:demand?1:0,page:1,page_size:50,pages:1};
    else if(path.includes('/notifications'))result={items:[],total:0,pages:1,unread_count:0,ack_required_count:0,latest:[],pending_ack:[]};
    else if(req.method()!=='GET')throw new Error(`Unhandled fixture mutation: ${req.method()} ${path}`);
    await route.fulfill({status:req.method()==='POST'?201:200,contentType:'application/json',body:JSON.stringify(result)});
  });
}
test.beforeEach(async({page})=>fixture(page));
async function interval(page:Page){
  const field=page.getByRole('textbox',{name:/السماكة/});
  await field.pressSequentially('0.70');await expect(field).toHaveValue('0.70');
  await field.pressSequentially('-0.75');await expect(field).toHaveValue('0.70-0.75');
}
test('saves a range quotation and displays the padded range in its details',async({page})=>{
  await page.goto('/quotes/new');
  await page.getByRole('combobox',{name:c.customers.picker.choose,exact:true}).fill('النطاق');
  await page.getByRole('option',{name:/عميل النطاق/}).click();
  await page.getByRole('combobox',{name:c.quotes.items.fields.productType,exact:true}).click();
  await page.getByRole('option',{name:/منتج النطاق/}).click();
  await interval(page);
  await page.getByRole('spinbutton',{name:c.quotes.items.fields.quantity,exact:true}).fill('10');
  await page.getByRole('spinbutton',{name:c.quotes.items.fields.unitPrice,exact:true}).fill('2');
  await page.getByRole('button',{name:common.actions.create,exact:true}).click();
  await expect(page).toHaveURL(/\/quotes\/quote-range$/);
  await expect(page.getByText(`0.70 – 0.75 ${common.units.units.mm}`,{exact:true})).toBeVisible();
});
test('saves a production demand range and displays it in details and the planning list',async({page})=>{
  const t=p.demands;
  await page.goto('/production/demands/new');
  await page.getByRole('button',{name:t.fromSalesOrder.manualInstead,exact:true}).click();
  await page.getByRole('combobox',{name:t.customer,exact:true}).fill('النطاق');
  await page.getByRole('option',{name:/عميل النطاق/}).click();
  await page.getByRole('button',{name:t.addItem,exact:true}).click();
  await page.getByRole('combobox',{name:t.productType,exact:true}).click();
  await page.getByRole('option',{name:/منتج النطاق/}).click();
  await page.getByLabel(t.quantity,{exact:true}).fill('10');await interval(page);
  await page.getByRole('button',{name:t.saveAndReady,exact:true}).click();
  await expect(page).toHaveURL(/\/production\/demands\/demand-range$/);
  await expect(page.getByText('0.70 – 0.75',{exact:true})).toBeVisible();
  await page.goto('/production/planning');
  await expect(page.getByText('PD-RANGE',{exact:true})).toBeVisible();
  expect(await page.getByText('0.70 – 0.75',{exact:true}).count()).toBeGreaterThanOrEqual(2);
  await expect(page.getByText('[object Object]',{exact:true})).toHaveCount(0);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
});
