import {test,expect} from "@playwright/test";
import {mockLogin} from "./fixtures/auth";
import ar from "../src/i18n/locales/ar/administration.json";

test("deletes an activated user without work after Arabic name confirmation",async({page},info)=>{
  await mockLogin(page);
  await page.context().addCookies([{name:"IORP_LOCALE",value:"ar",domain:"127.0.0.1",path:"/"}]);
  let deleted=false;
  const user={id:"unused-user",organization_id:"org",email:"unused@example.test",full_name:"مستخدم للتجربة",phone:null,preferred_locale:"ar",status:"active",is_organization_root:false,roles:[],permissions:[],created_at:"2026-11-25T00:00:00Z",updated_at:"2026-11-25T00:00:00Z",last_login_at:"2026-11-25T10:00:00Z",last_seen_at:"2026-11-25T10:00:00Z",is_online:true,failed_login_attempts:0,last_failed_login_at:null,auto_locked_until:null,activation_pending:false,archived_at:null,delete_block:null,can_delete_permanently:true};
  await page.route("**/api/v1/**",async route=>{
    const request=route.request(),path=new URL(request.url()).pathname.replace("/api/v1","");let result:unknown=[];
    if(path==="/auth/me")result={id:"actor",organization_id:"org",organization_code:"TEST",organization_name:"UI test",organization_timezone:"UTC",full_name:"Browser tester",email:"tester@example.test",status:"active",is_organization_root:true,roles:[],permissions:["foundation:users:read","foundation:users:delete","foundation:users:deactivate"],preferred_locale:"ar",effective_locale:"ar",organization:{id:"org",name:"UI test",code:"TEST",has_logo:false,logo_url:null,default_locale:"ar"}};
    else if(path==="/admin/users/unused-user/permanent"&&request.method()==="DELETE"){
      expect(request.postDataJSON()).toEqual({reason:"لا توجد سجلات عمل"});deleted=true;result={deleted:true};
    }else if(path==="/admin/users/unused-user")result=user;
    else if(path==="/admin/users/unused-user/roles")result={user_id:user.id,roles:[]};
    else if(path==="/admin/users/unused-user/assignable-roles")result={roles:[],restricted_count:0};
    else if(path==="/admin/users/unused-user/effective-access")result={user_id:user.id,user_full_name:user.full_name,is_organization_root:false,generated_at:user.updated_at,total_roles:0,total_permissions:0,missing_permissions_count:0,roles:[],permissions_by_module:{},missing_permissions:[]};
    else if(path==="/admin/users/unused-user/presence")result={last_seen_at:user.last_seen_at,is_online:true};
    else if(path==="/admin/users/unused-user/deactivation-impact")result={user_id:user.id,user_full_name:user.full_name,dependencies:{assigned_customers:0,open_follow_ups:0,active_workforce_link:false},can_deactivate:true,total_blocking_items:0};
    else if(path==="/admin/users")result={items:deleted?[]:[user],total:deleted?0:1,page:1,page_size:50,pages:deleted?0:1};
    else if(path.includes("/notifications"))result={items:[],total:0,pages:1,unread_count:0,ack_required_count:0,latest:[],pending_ack:[]};
    else if(request.method()!=="GET")throw new Error(`Unhandled fixture mutation: ${request.method()} ${path}`);
    await route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(result)});
  });
  const t=ar.users.permanentDelete;
  await page.goto("/admin/users/unused-user");
  await page.getByRole("button",{name:t.button,exact:true}).click();
  const dialog=page.getByRole("dialog");
  await dialog.getByLabel(t.reason,{exact:true}).fill("لا توجد سجلات عمل");
  const name=dialog.getByRole("textbox").last(),save=dialog.getByRole("button",{name:t.button,exact:true});
  await name.fill(user.email);await expect(save).toBeDisabled();
  await name.fill(user.full_name);await expect(save).toBeEnabled();
  expect((await dialog.boundingBox())!.width).toBeLessThanOrEqual(page.viewportSize()!.width);
  await page.screenshot({path:info.outputPath("user-delete-ar.png")});
  await save.click();
  await expect(page).toHaveURL(/\/admin\/users$/);expect(deleted).toBe(true);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
});
