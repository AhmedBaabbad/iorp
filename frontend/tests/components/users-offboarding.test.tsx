import {render,screen,fireEvent,waitFor,cleanup} from "@testing-library/react";
import {beforeAll,beforeEach,afterEach,it,expect,vi} from "vitest";
import {NextIntlClientProvider} from "next-intl";
import {loadMessages} from "@/i18n/messages";
import type {AdminUserDetail} from "@/features/admin-users/types";
const mocks=vi.hoisted(()=>({impact:vi.fn(),owners:vi.fn(),assignees:vi.fn(),customers:vi.fn(),followUps:vi.fn(),deactivate:vi.fn(),archive:vi.fn(),denied:new Set<string>()}));
vi.mock("@/features/auth",()=>({usePermission:(code:string)=>!mocks.denied.has(code)}));
vi.mock("@/hooks/useFormatter",()=>({useFormatter:()=>({dateTime:(value:string)=>value})}));
vi.mock("@/features/admin-users/api/admin-users-api",()=>({getUserDeactivationImpact:mocks.impact,deactivateAdminUser:mocks.deactivate,archiveAdminUser:mocks.archive}));
vi.mock("@/features/customers/customer-api",()=>({getEligibleSalesOwners:mocks.owners,reassignCustomersByOwner:mocks.customers}));
vi.mock("@/features/followups/followup-api",()=>({getEligibleAssignees:mocks.assignees,reassignFollowUpsByUser:mocks.followUps}));
import {UserOffboarding} from "@/features/admin-users/components/UserOffboarding";
let messages:Record<string,unknown>;
beforeAll(async()=>{messages=await loadMessages("en") as Record<string,unknown>;});
const user:AdminUserDetail={id:"target",organization_id:"org",email:"person@example.com",full_name:"Person",phone:null,preferred_locale:null,status:"active",is_organization_root:false,roles:[],created_at:"2026-11-14T12:00:00Z",updated_at:"2026-11-14T12:00:00Z",last_login_at:null,failed_login_attempts:0,last_failed_login_at:null,auto_locked_until:null,permissions:[],delete_block:{code:"USER_DELETE_ACTIVATED",tables:[]}};
const clear={user_id:user.id,user_full_name:user.full_name,dependencies:{assigned_customers:0,open_follow_ups:0,active_workforce_link:false},can_deactivate:true,total_blocking_items:0,message:""};
const blocked={...clear,dependencies:{...clear.dependencies,assigned_customers:1},can_deactivate:false,total_blocking_items:1};
const candidate={id:"replacement",full_name:"Replacement",email:"next@example.com"};
beforeEach(()=>{vi.clearAllMocks();mocks.denied.clear();mocks.impact.mockResolvedValue(clear);mocks.owners.mockResolvedValue([candidate]);mocks.assignees.mockResolvedValue([candidate]);mocks.customers.mockResolvedValue({reassigned_count:1});mocks.followUps.mockResolvedValue({reassigned_count:1});mocks.deactivate.mockResolvedValue({...user,status:"inactive"});mocks.archive.mockResolvedValue({...user,status:"inactive",archived_at:"2026-11-14T13:00:00Z"});});
afterEach(cleanup);
function ui(person=user,onChanged=vi.fn(),onReload=vi.fn()){return <NextIntlClientProvider locale="en" messages={messages} timeZone="UTC"><UserOffboarding user={person} onChanged={onChanged} onReload={onReload}/></NextIntlClientProvider>;}
function confirm(){const dialog=screen.getByRole("dialog");fireEvent.change(dialog.querySelector("textarea")!,{target:{value:"Employment ended"}});fireEvent.submit(dialog);}

it("locks deactivation until transfer refreshes impact, then allows archive only after deactivation",async()=>{
  mocks.impact.mockResolvedValueOnce(blocked).mockResolvedValue(clear);
  const changed=vi.fn(),reload=vi.fn();const view=render(ui(user,changed,reload));
  await screen.findByText("Assigned customers: 1");
  expect((screen.getByRole("button",{name:"Deactivate"}) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole("button",{name:"Archive"}) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(await screen.findByRole("combobox",{name:"To user"}),{target:{value:candidate.id}});
  fireEvent.click(screen.getByRole("button",{name:"Transfer"}));
  await waitFor(()=>expect(mocks.customers).toHaveBeenCalledWith(user.id,candidate.id));
  await waitFor(()=>expect(mocks.impact).toHaveBeenCalledTimes(2));expect(reload).toHaveBeenCalledTimes(1);
  await waitFor(()=>expect((screen.getByRole("button",{name:"Deactivate"}) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole("button",{name:"Deactivate"}));confirm();
  await waitFor(()=>expect(mocks.deactivate).toHaveBeenCalledWith(user.id,"Employment ended"));
  await waitFor(()=>expect(screen.queryByRole("dialog")).toBeNull());expect(changed).toHaveBeenCalled();
  view.rerender(ui({...user,status:"inactive"},changed,reload));
  await waitFor(()=>expect((screen.getByRole("button",{name:"Archive"}) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole("button",{name:"Archive"}));confirm();
  await waitFor(()=>expect(mocks.archive).toHaveBeenCalledWith(user.id,"Employment ended",false));
});

it("transfers follow-ups through their module API and reloads impact",async()=>{
  mocks.impact.mockResolvedValueOnce({...blocked,dependencies:{...clear.dependencies,open_follow_ups:1}}).mockResolvedValue(clear);
  render(ui());await screen.findByText("Open follow-ups: 1");
  fireEvent.change(screen.getByRole("combobox",{name:"To user"}),{target:{value:candidate.id}});fireEvent.click(screen.getByRole("button",{name:"Transfer"}));
  await waitFor(()=>expect(mocks.followUps).toHaveBeenCalledWith(user.id,candidate.id));
  await waitFor(()=>expect(mocks.impact).toHaveBeenCalledTimes(2));
});

it("explains absent transfer permissions and links to the employee record without moving the link",async()=>{
  mocks.denied.add("commercial:customers:assign_owner");
  mocks.impact.mockResolvedValue({...blocked,workforce_member_id:"employee",dependencies:{...blocked.dependencies,active_workforce_link:true},total_blocking_items:2});
  render(ui());await screen.findByText(/You need the category/);
  expect(screen.queryByRole("button",{name:"Transfer"})).toBeNull();expect(mocks.owners).not.toHaveBeenCalled();
  expect(screen.getByRole("link",{name:"Open employee record"}).getAttribute("href")).toBe("/workforce/employee");
  expect((screen.getByRole("button",{name:"Deactivate"}) as HTMLButtonElement).disabled).toBe(true);
});

it("shows archive author and reason, and restores through the existing API",async()=>{
  render(ui({...user,status:"inactive",archived_at:"2026-11-14T13:00:00Z",archived_by_name:"Admin",archived_reason:"Employment ended"}));
  expect(screen.getByText(/Archived on .* by Admin. Reason: Employment ended/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button",{name:"Restore"}));confirm();
  await waitFor(()=>expect(mocks.archive).toHaveBeenCalledWith(user.id,"Employment ended",true));
});

it("hides restoration without activate permission",()=>{
  mocks.denied.add("foundation:users:activate");render(ui({...user,status:"inactive",archived_at:"2026-11-14T13:00:00Z"}));expect(screen.queryByRole("button",{name:"Restore"})).toBeNull();
});

it("allows archive restoration without deactivation permission and makes no impact request",async()=>{
  mocks.denied.add("foundation:users:deactivate");
  render(ui({...user,status:"inactive",archived_at:"2026-11-14T13:00:00Z",archived_by_name:"Admin",archived_reason:"Employment ended"}));
  expect(screen.getByRole("heading",{name:"Archive details"})).toBeTruthy();
  expect(screen.queryByRole("button",{name:"Deactivate"})).toBeNull();
  expect(mocks.impact).not.toHaveBeenCalled();expect(mocks.owners).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button",{name:"Restore"}));confirm();
  await waitFor(()=>expect(mocks.archive).toHaveBeenCalledWith(user.id,"Employment ended",true));
});
