import type {Page} from "@playwright/test";

/** Browser fixtures mock /auth/me and API routes; this value is never a real credential. */
export async function mockLogin(page:Page){
  await page.addInitScript(()=>{
    localStorage.setItem("iorp.access_token","ui-test-token");
    localStorage.setItem("iorp.last_activity",String(Date.now()));
  });
}
