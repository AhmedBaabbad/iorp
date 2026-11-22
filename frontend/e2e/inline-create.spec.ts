import {test,expect} from '@playwright/test';
import ar from '../src/i18n/locales/ar/commercial.json';
import md from '../src/i18n/locales/ar/masterdata.json';
import directory from '../src/i18n/locales/ar/directory.json';
import common from '../src/i18n/locales/ar/common.json';

test('adds a product inside an Arabic quotation and keeps the draft on mobile',async({page},testInfo)=>{
  const products:Array<Record<string,unknown>>=[];let quoteWrites=0;
  await page.addInitScript(()=>{localStorage.setItem('iorp.access_token','inline-test-token');localStorage.setItem('iorp.last_activity',String(Date.now()));});
  await page.context().addCookies([{name:'IORP_LOCALE',value:'ar',domain:'127.0.0.1',path:'/'}]);
  await page.route('**/api/v1/**',async route=>{
    const req=route.request(),path=new URL(req.url()).pathname.replace('/api/v1','');let result:unknown=[];
    if(path==='/auth/me')result={id:'user',organization_id:'org',organization_name:'Inline test',organization_code:'TEST',organization_timezone:'UTC',full_name:'Browser tester',email:'test@example.test',status:'active',is_organization_root:true,roles:['organization_admin'],permissions:['commercial:quotes:read','commercial:quotes:create','masterdata:products:read','masterdata:products:create','masterdata:lists:read'],preferred_locale:'ar',effective_locale:'ar',organization:{id:'org',name:'Inline test',code:'TEST',has_logo:false,default_locale:'ar'}};
    else if(path==='/masterdata/products'&&req.method()==='POST'){result={...req.postDataJSON(),id:'product',code:'PRD-1',actions:['edit'],created_at:'',updated_at:''};products.push(result as Record<string,unknown>);}
    else if(path==='/masterdata/products')result=products;
    else if(path==='/masterdata/settings')result={vat_rate:'15',default_currency:'SAR'};
    else if(path==='/commercial/quote-settings/validity')result={quote_validity_days:10,document_language:'ar'};
    else if(path==='/commercial/quotes'&&req.method()==='POST'){quoteWrites++;result={id:'quote'};}
    else if(path.includes('/notifications'))result={items:[],total:0,pages:1,unread_count:0,ack_required_count:0,latest:[],pending_ack:[]};
    await route.fulfill({status:req.method()==='POST'?201:200,contentType:'application/json',body:JSON.stringify(result)});
  });
  await page.goto('/quotes/new');
  await page.addStyleTag({content:'nextjs-portal { display: none !important; }'});
  await page.getByRole('textbox',{name:ar.quotes.fields.notes,exact:true}).fill('ملاحظات العرض باقية');
  const add=page.getByRole('button',{name:md.select.add,exact:true});
  expect((await add.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await add.click();
  const dialog=page.getByRole('dialog',{name:md.products.createTitle,exact:true});
  await dialog.getByLabel(md.fields.name_ar,{exact:true}).fill('منتج جديد');
  await dialog.getByLabel(md.fields.name_en,{exact:true}).fill('Inline product');
  await dialog.getByRole('button',{name:md.template.add,exact:true}).click();
  const property=dialog.getByRole('group',{name:/^1\./});
  await property.getByLabel(md.template.name_ar,{exact:true}).fill('عرض إضافي');
  await property.getByLabel(md.template.name_en,{exact:true}).fill('Inline width');
  await property.getByLabel(md.template.name_en,{exact:true}).press('Tab');
  await expect(property.getByLabel(md.template.key,{exact:true})).toHaveValue('inline_width');
  if(testInfo.project.name==='mobile'){
    const bounds=await dialog.boundingBox();expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.x+bounds!.width).toBeLessThanOrEqual(page.viewportSize()!.width);
    await dialog.screenshot({path:testInfo.outputPath('arabic-inline-product-dialog.png')});
  }
  await dialog.getByRole('button',{name:directory.save,exact:true}).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByLabel(ar.quotes.items.fields.productType,{exact:true})).toHaveValue('inline_product');
  await expect(page.getByLabel('عرض إضافي',{exact:true})).toBeVisible();
  await expect(page.getByRole('textbox',{name:ar.quotes.fields.notes,exact:true})).toHaveValue('ملاحظات العرض باقية');
  await expect(page).toHaveURL(/\/quotes\/new$/);expect(quoteWrites).toBe(0);
  await page.getByRole('link',{name:ar.quotes.backToList,exact:true}).click();
  const warning=page.getByRole('alertdialog',{name:common.unsavedChanges.title,exact:true});
  await expect(warning).toBeVisible();await warning.getByRole('button',{name:common.unsavedChanges.stay,exact:true}).click();
  await expect(page).toHaveURL(/\/quotes\/new$/);
  await expect(page.getByRole('textbox',{name:ar.quotes.fields.notes,exact:true})).toHaveValue('ملاحظات العرض باقية');
  if(testInfo.project.name==='mobile'){
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    await page.screenshot({path:testInfo.outputPath('arabic-inline-quote.png'),fullPage:true});
  }
});
