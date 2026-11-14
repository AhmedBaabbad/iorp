import {cleanup,fireEvent,render,screen,waitFor,act,within} from "@testing-library/react";
import {NextIntlClientProvider} from "next-intl";
import {afterEach,beforeAll,beforeEach,expect,it,vi} from "vitest";
import type {ReactNode} from "react";
import {loadMessages} from "@/i18n/messages";
import {ApiClientError} from "@/lib/api-client";
const mocks=vi.hoisted(()=>({allowed:true,remove:vi.fn(),list:vi.fn(),get:vi.fn(),presence:vi.fn(),push:vi.fn(),success:vi.fn(),error:vi.fn()}));
vi.mock("@/features/auth",()=>({usePermission:()=>mocks.allowed,useAuth:()=>({user:null})}));
vi.mock("next/navigation",()=>({useParams:()=>({id:"pending"}),useRouter:()=>({push:mocks.push,refresh:vi.fn()})}));
vi.mock("@/components/notify/Notifications",()=>({useNotify:()=>({success:mocks.success,error:mocks.error})}));
vi.mock("@/components/layout/page-frame",()=>({PageFrame:({children}:{children:ReactNode})=><main>{children}</main>}));
vi.mock("@/features/admin-users/api/admin-users-api",()=>({permanentlyDeleteAdminUser:mocks.remove,getAdminUser:mocks.get,getAdminUserPresence:mocks.presence,listAdminUsers:mocks.list,archiveAdminUser:vi.fn(),deactivateAdminUser:vi.fn(),getUserDeactivationImpact:vi.fn(),resetAdminUserPassword:vi.fn(),getAdminUserSessions:vi.fn(),endAdminUserSessions:vi.fn(),activateAdminUser:vi.fn(),lockAdminUser:vi.fn(),unlockAdminUser:vi.fn()}));
vi.mock("@/features/admin-users/components/UserOffboarding",()=>({UserOffboarding:()=>null}));
vi.mock("@/features/admin-users/components/AdminUserRolesManager",()=>({AdminUserRolesManager:()=>null}));
vi.mock("@/features/admin-users/components/EffectiveAccessPanel",()=>({EffectiveAccessPanel:()=>null}));
vi.mock("@/hooks/useFormatter",()=>({useFormatter:()=>({date:(value:string)=>value,dateTime:(value:string)=>`Full date ${value}`})}));
import {AdminUserDetail} from "@/features/admin-users/components/AdminUserDetail";
import {UserPresence} from "@/features/admin-users/components/UserPresence";
import {PermanentUserDelete} from "@/features/admin-users/components/PermanentUserDelete";
import {AdminUsersList} from "@/features/admin-users/components/AdminUsersList";
let en:Record<string,unknown>,ar:Record<string,unknown>;
beforeAll(async()=>{en=await loadMessages("en") as Record<string,unknown>;ar=await loadMessages("ar") as Record<string,unknown>;});
beforeEach(()=>{vi.clearAllMocks();mocks.allowed=true;mocks.list.mockResolvedValue([]);mocks.remove.mockResolvedValue({deleted:true});mocks.get.mockResolvedValue(detail);mocks.presence.mockResolvedValue({last_seen_at:detail.last_seen_at,is_online:true});});
afterEach(()=>{cleanup();vi.useRealTimers();});
const user={id:"pending",email:"pending@example.com",full_name:"Pending",status:"active" as const,phone:null,preferred_locale:null,is_organization_root:false,roles:[],created_at:"2026-11-12T10:00:00Z",can_delete_permanently:true};
const detail={...user,organization_id:"org",last_login_at:"2026-11-12T10:00:00Z",last_seen_at:"2026-11-12T11:59:00Z",is_online:true,
  failed_login_attempts:0,auto_locked_until:null,last_failed_login_at:null,permissions:[],updated_at:"2026-11-12T10:00:00Z",delete_block:null};
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
  ui(<PermanentUserDelete user={user}/>);expect(screen.getByRole("button",{name:"Delete permanently (cancel invitation)"})).toBeTruthy();
});

function confirm(){
  fireEvent.click(screen.getByRole("button",{name:"Delete permanently (cancel invitation)"}));
  expect(screen.getByText("This deletion cannot be undone.")).toBeTruthy();
  expect((screen.getAllByRole("button",{name:"Delete permanently (cancel invitation)"})[1] as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByRole("textbox",{name:"Reason"}),{target:{value:"Created by mistake"}});
  fireEvent.change(screen.getByRole("textbox",{name:/Type the user/}),{target:{value:user.email}});
}
it("requires reason, accepts uppercase confirmation email and closes before returning to the list",async()=>{
  ui(<PermanentUserDelete user={user}/>);confirm();
  fireEvent.change(screen.getByRole("textbox",{name:/Type the user/}),{target:{value:"wrong@example.com"}});
  expect((screen.getAllByRole("button",{name:"Delete permanently (cancel invitation)"})[1] as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByRole("textbox",{name:/Type the user/}),{target:{value:` ${user.email.toUpperCase()} `}});
  expect((screen.getAllByRole("button",{name:"Delete permanently (cancel invitation)"})[1] as HTMLButtonElement).disabled).toBe(false);
  fireEvent.click(screen.getAllByRole("button",{name:"Delete permanently (cancel invitation)"})[1]);
  await waitFor(()=>expect(mocks.remove).toHaveBeenCalledWith(user.id,"Created by mistake"));
  expect(mocks.push).toHaveBeenCalledWith("/admin/users");expect(mocks.success).toHaveBeenCalled();
  expect(screen.queryByRole("dialog")).toBeNull();
});

it("never offers permanent deletion in the list",async()=>{
  mocks.list.mockResolvedValue([user]);ui(<AdminUsersList/>);
  await screen.findByRole("link",{name:"Pending"});
  expect(screen.queryByRole("button",{name:"Delete permanently (cancel invitation)"})).toBeNull();
});

it("hides archived users until the show archived switch is selected",async()=>{
  mocks.list.mockResolvedValue([user,{...user,id:"archived",full_name:"Archived colleague",email:"archived@example.com",archived_at:"2026-11-14T12:00:00Z"}]);
  ui(<AdminUsersList/>);await screen.findByRole("link",{name:"Pending"});
  expect(screen.queryByRole("link",{name:"Archived colleague"})).toBeNull();
  fireEvent.click(screen.getByRole("checkbox"));expect(screen.getByRole("link",{name:"Archived colleague"})).toBeTruthy();
});

it.each(["USER_DELETE_ROOT","USER_DELETE_SELF","USER_DELETE_ACTIVATED"] as const)("disables protected deletion with a reason: %s",code=>{
  ui(<PermanentUserDelete showBlock user={{...user,delete_block:{code,tables:[]}}}/>);
  expect((screen.getByRole("button",{name:"Delete permanently (cancel invitation)"}) as HTMLButtonElement).disabled).toBe(true);
  const dictionary=(en.administration as {users:{permanentDelete:Record<string,string>}}).users.permanentDelete;
  expect(screen.getByText(dictionary[code])).toBeTruthy();
});

it.each(["ar","en"])("reports missing user in %s and returns from details to the list",async locale=>{
  mocks.remove.mockRejectedValueOnce(new ApiClientError("Not found",404));
  ui(<PermanentUserDelete user={user}/>,locale);
  const dictionary=((locale==="ar"?ar:en).administration as {users:{permanentDelete:Record<string,string>}}).users.permanentDelete;
  fireEvent.click(screen.getByRole("button",{name:dictionary.button}));
  const dialog=screen.getByRole("dialog");
  fireEvent.change(dialog.querySelector("textarea")!,{target:{value:"Created by mistake"}});
  fireEvent.change(dialog.querySelector("input")!,{target:{value:user.email}});
  fireEvent.submit(dialog);
  await waitFor(()=>expect(mocks.error).toHaveBeenCalledWith(dictionary.notFound));
  expect(screen.queryByRole("dialog")).toBeNull();expect(mocks.push).toHaveBeenCalledWith("/admin/users");
  expect(mocks.success).not.toHaveBeenCalled();
});
it.each(["USER_DELETE_ROOT","USER_DELETE_SELF","USER_DELETE_ACTIVATED","USER_DELETE_HAS_HISTORY"])("explains 409 %s",async code=>{
  mocks.remove.mockRejectedValueOnce(new ApiClientError("Conflict",409,{code,details:{tables:["commercial_customers"]}}));
  const deactivate=vi.fn();ui(<PermanentUserDelete user={user} onDeactivate={deactivate}/>);confirm();
  fireEvent.click(screen.getAllByRole("button",{name:"Delete permanently (cancel invitation)"})[1]);
  expect(await screen.findByRole("alert")).toBeTruthy();
  const dictionary=(en.administration as {users:{permanentDelete:Record<string,string>}}).users.permanentDelete;
  expect(screen.getByText(dictionary[code])).toBeTruthy();
  if(code==="USER_DELETE_HAS_HISTORY"){
    expect(screen.getByText("Deactivate the account instead.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button",{name:"Open deactivation"}));expect(deactivate).toHaveBeenCalled();
  }
});

it("keeps presence and periodic refresh out of the users list",async()=>{
  vi.useFakeTimers();vi.setSystemTime(new Date("2026-11-12T12:00:00Z"));mocks.list.mockResolvedValue([user]);
  ui(<AdminUsersList/>);await act(async()=>{await Promise.resolve();});
  expect(screen.queryByRole("columnheader",{name:"Presence"})).toBeNull();
  expect(screen.queryByText("Online now")).toBeNull();
  await act(async()=>{await vi.advanceTimersByTimeAsync(180000);});expect(mocks.list).toHaveBeenCalledTimes(1);
});

it("polls presence in the hero only while details are visible, retaining an open dialog",async()=>{
  vi.useFakeTimers();vi.setSystemTime(new Date("2026-11-12T12:00:00Z"));
  mocks.presence.mockResolvedValue({is_online:false,last_seen_at:"2026-11-12T11:50:00Z"});
  let hidden=false;const original=Object.getOwnPropertyDescriptor(document,"hidden");
  Object.defineProperty(document,"hidden",{configurable:true,get:()=>hidden});
  try{
    const view=ui(<AdminUserDetail/>);await act(async()=>{await Promise.resolve();});
    const hero=screen.getByRole("heading",{name:user.full_name}).closest("section")!;
    expect(within(hero).getByText("Online now")).toBeTruthy();
    expect(screen.getByText(`Full date ${detail.last_seen_at}`)).toBeTruthy();
    expect(screen.getAllByText(`Full date ${detail.last_login_at}`).length).toBeGreaterThan(0);
    confirm();
    await act(async()=>{await vi.advanceTimersByTimeAsync(60000);});expect(mocks.presence).toHaveBeenCalledTimes(1);expect(mocks.get).toHaveBeenCalledTimes(1);
    expect(within(hero).getByText(/Last seen:/)).toBeTruthy();
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect((screen.getByRole("textbox",{name:"Reason"}) as HTMLTextAreaElement).value).toBe("Created by mistake");
    hidden=true;fireEvent(document,new Event("visibilitychange"));
    await act(async()=>{await vi.advanceTimersByTimeAsync(120000);});expect(mocks.presence).toHaveBeenCalledTimes(1);expect(mocks.get).toHaveBeenCalledTimes(1);
    hidden=false;fireEvent(document,new Event("visibilitychange"));await act(async()=>{await Promise.resolve();});expect(mocks.presence).toHaveBeenCalledTimes(2);expect(mocks.get).toHaveBeenCalledTimes(1);
    view.unmount();await vi.advanceTimersByTimeAsync(60000);expect(mocks.presence).toHaveBeenCalledTimes(2);expect(mocks.get).toHaveBeenCalledTimes(1);
  }finally{if(original)Object.defineProperty(document,"hidden",original);else Reflect.deleteProperty(document,"hidden");}
});

it("shows a disabled detail deletion button with translated business types and deactivation",()=>{
  const onDeactivate=vi.fn();ui(<PermanentUserDelete showBlock user={{...user,can_delete_permanently:false,
    delete_block:{code:"USER_DELETE_HAS_HISTORY",tables:["customers","quotes"]}}} onDeactivate={onDeactivate}/>);
  expect((screen.getByRole("button",{name:"Delete permanently (cancel invitation)"}) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByText(/Customers.*Quotations/)).toBeTruthy();
  expect(screen.getByText("Transfer ownership first.")).toBeTruthy();
  fireEvent.click(screen.getByRole("button",{name:"Offboarding"}));expect(onDeactivate).toHaveBeenCalled();
});

it("enables detail deletion from the server block and hides protected accounts",()=>{
  const view=ui(<PermanentUserDelete showBlock user={{...user,activation_pending:false,delete_block:null}}/>);
  expect((screen.getByRole("button",{name:"Delete permanently (cancel invitation)"}) as HTMLButtonElement).disabled).toBe(false);view.unmount();
  ui(<PermanentUserDelete showBlock user={{...user,delete_block:{code:"USER_DELETE_SELF",tables:[]}}}/>);
  expect((screen.getByRole("button",{name:"Delete permanently (cancel invitation)"}) as HTMLButtonElement).disabled).toBe(true);
});
