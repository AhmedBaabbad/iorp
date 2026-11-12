import {cleanup,fireEvent,render,screen,waitFor,act} from "@testing-library/react";
import {NextIntlClientProvider} from "next-intl";
import {afterEach,beforeAll,beforeEach,expect,it,vi} from "vitest";
import type {ReactNode} from "react";
import {loadMessages} from "@/i18n/messages";
import {ApiClientError} from "@/lib/api-client";
const mocks=vi.hoisted(()=>({allowed:true,remove:vi.fn(),list:vi.fn(),push:vi.fn(),success:vi.fn()}));
vi.mock("@/features/auth",()=>({usePermission:()=>mocks.allowed,useAuth:()=>({user:null})}));
vi.mock("next/navigation",()=>({useRouter:()=>({push:mocks.push,refresh:vi.fn()})}));
vi.mock("@/components/notify/Notifications",()=>({useNotify:()=>({success:mocks.success})}));
vi.mock("@/components/layout/page-frame",()=>({PageFrame:({children}:{children:ReactNode})=><main>{children}</main>}));
vi.mock("@/features/admin-users/api/admin-users-api",()=>({permanentlyDeleteAdminUser:mocks.remove,listAdminUsers:mocks.list,activateAdminUser:vi.fn(),lockAdminUser:vi.fn(),unlockAdminUser:vi.fn()}));
import {UserPresence} from "@/features/admin-users/components/UserPresence";
import {PermanentUserDelete} from "@/features/admin-users/components/PermanentUserDelete";
import {AdminUsersList} from "@/features/admin-users/components/AdminUsersList";
let en:Record<string,unknown>,ar:Record<string,unknown>;
beforeAll(async()=>{en=await loadMessages("en") as Record<string,unknown>;ar=await loadMessages("ar") as Record<string,unknown>;});
beforeEach(()=>{vi.clearAllMocks();mocks.allowed=true;mocks.list.mockResolvedValue([]);mocks.remove.mockResolvedValue({deleted:true});});
afterEach(()=>{cleanup();vi.useRealTimers();});
const user={id:"pending",email:"pending@example.com",full_name:"Pending",status:"active" as const,phone:null,preferred_locale:null,is_organization_root:false,roles:[],created_at:"2026-11-12T10:00:00Z",can_delete_permanently:true};
const ui=(children:ReactNode,locale="en")=>render(<NextIntlClientProvider locale={locale} messages={locale==="en"?en:ar} timeZone="UTC">{children}</NextIntlClientProvider>);

it.each(["ar","en"])("renders online, relative and never presence in %s",locale=>{
  vi.useFakeTimers();vi.setSystemTime(new Date("2026-11-12T12:00:00Z"));
  const view=ui(<UserPresence user={{is_online:true,last_seen_at:"2026-11-12T11:59:00Z"}}/>,locale);
  expect(screen.getByText(locale==="en"?"Online now":"متصل الآن")).toBeTruthy();view.unmount();
  const relative=ui(<UserPresence user={{is_online:false,last_seen_at:"2026-11-12T11:50:00Z"}}/>,locale);
  expect(screen.getByText(locale==="en"?/Last seen:.*10 minutes ago/:/آخر ظهور:/)).toBeTruthy();relative.unmount();
  ui(<UserPresence user={{last_seen_at:null,is_online:false}}/>,locale);
  expect(screen.getByText(locale==="en"?"Has not signed in yet":"لم يسجّل الدخول بعد")).toBeTruthy();
});

it("shows permanent deletion only with permission and server eligibility",()=>{
  mocks.allowed=false;const denied=ui(<PermanentUserDelete user={user}/>);expect(screen.queryByRole("button")).toBeNull();denied.unmount();
  mocks.allowed=true;const ineligible=ui(<PermanentUserDelete user={{...user,can_delete_permanently:false}}/>);expect(screen.queryByRole("button")).toBeNull();ineligible.unmount();
  ui(<PermanentUserDelete user={user}/>);expect(screen.getByRole("button",{name:"Delete permanently"})).toBeTruthy();
});

function confirm(){
  fireEvent.click(screen.getByRole("button",{name:"Delete permanently"}));
  expect(screen.getByText("This deletion cannot be undone.")).toBeTruthy();
  expect((screen.getAllByRole("button",{name:"Delete permanently"})[1] as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByRole("textbox",{name:"Reason"}),{target:{value:"Created by mistake"}});
  fireEvent.change(screen.getByRole("textbox",{name:/Type the user/}),{target:{value:user.email}});
}
it("requires reason and exact email before deleting and returns to the list",async()=>{
  ui(<PermanentUserDelete user={user}/>);confirm();
  fireEvent.change(screen.getByRole("textbox",{name:/Type the user/}),{target:{value:"wrong@example.com"}});
  expect((screen.getAllByRole("button",{name:"Delete permanently"})[1] as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByRole("textbox",{name:/Type the user/}),{target:{value:user.email}});
  fireEvent.click(screen.getAllByRole("button",{name:"Delete permanently"})[1]);
  await waitFor(()=>expect(mocks.remove).toHaveBeenCalledWith(user.id,"Created by mistake"));
  expect(mocks.push).toHaveBeenCalledWith("/admin/users");expect(mocks.success).toHaveBeenCalled();
});
it.each(["USER_DELETE_ROOT","USER_DELETE_SELF","USER_DELETE_ACTIVATED","USER_DELETE_HAS_HISTORY"])("explains 409 %s",async code=>{
  mocks.remove.mockRejectedValueOnce(new ApiClientError("Conflict",409,{code,details:{tables:["commercial_customers"]}}));
  const deactivate=vi.fn();ui(<PermanentUserDelete user={user} onDeactivate={deactivate}/>);confirm();
  fireEvent.click(screen.getAllByRole("button",{name:"Delete permanently"})[1]);
  expect(await screen.findByRole("alert")).toBeTruthy();
  const dictionary=(en.administration as {users:{permanentDelete:Record<string,string>}}).users.permanentDelete;
  expect(screen.getByText(dictionary[code])).toBeTruthy();
  if(code==="USER_DELETE_HAS_HISTORY"){
    expect(screen.getByText("Deactivate the account instead.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button",{name:"Open deactivation"}));expect(deactivate).toHaveBeenCalled();
  }
});

it("polls every minute only while the users tab is visible and cleans up",async()=>{
  vi.useFakeTimers();vi.setSystemTime(new Date("2026-11-12T12:00:00Z"));
  let hidden=false;const original=Object.getOwnPropertyDescriptor(document,"hidden");
  Object.defineProperty(document,"hidden",{configurable:true,get:()=>hidden});
  try{
    const view=ui(<AdminUsersList/>);
    await act(async()=>{await Promise.resolve();});expect(mocks.list).toHaveBeenCalledTimes(1);
    await act(async()=>{await vi.advanceTimersByTimeAsync(60000);});expect(mocks.list).toHaveBeenCalledTimes(2);
    hidden=true;fireEvent(document,new Event("visibilitychange"));
    await act(async()=>{await vi.advanceTimersByTimeAsync(120000);});expect(mocks.list).toHaveBeenCalledTimes(2);
    hidden=false;fireEvent(document,new Event("visibilitychange"));await act(async()=>{await Promise.resolve();});expect(mocks.list).toHaveBeenCalledTimes(3);
    view.unmount();await vi.advanceTimersByTimeAsync(60000);expect(mocks.list).toHaveBeenCalledTimes(3);
  }finally{if(original)Object.defineProperty(document,"hidden",original);else Reflect.deleteProperty(document,"hidden");}
});
