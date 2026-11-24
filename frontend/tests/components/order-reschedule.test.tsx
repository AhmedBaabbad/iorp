import {cleanup,fireEvent,render,screen,waitFor,within} from "@testing-library/react";
import {NextIntlClientProvider} from "next-intl";
import {afterEach,beforeAll,beforeEach,expect,it,vi} from "vitest";
import {loadMessages} from "@/i18n/messages";
import {ApiClientError} from "@/lib/api-client";
import {RescheduleOrderButton,OrderRescheduleDialog} from "@/features/production-orders/components/OrderReschedule";
import {OrderStatusTimeline} from "@/features/production-orders/components/OrderStatusTimeline";
import {OrderLines} from "@/features/production-orders/components/OrderLines";
import {ExistingOrderDialog} from "@/features/production-demands/existing-order-dialog";
import type {ProductionOrderData} from "@/features/production-orders/types";
import {findRecordOption} from "./record-test-helpers";
const api=vi.hoisted(()=>({reschedule:vi.fn(),add:vi.fn(),orders:vi.fn(),items:vi.fn(),history:vi.fn(),push:vi.fn(),allowed:true}));
vi.mock("@/features/auth/permission-hooks",()=>({usePermission:(code:string)=>code==="production:production_orders:update"?api.allowed:true}));
vi.mock("next/navigation",()=>({useRouter:()=>({push:api.push})}));
vi.mock("@/hooks/useFormatter",()=>({useFormatter:()=>({date:String,dateTime:String,quantity:String})}));
vi.mock("@/features/customers/use-customer-names",()=>({useCustomerNames:()=> (_id:string,fallback:string)=>fallback??"Customer"}));
vi.mock("@/features/production-orders/api/production-orders-api",async original=>({...await original<object>(),rescheduleProductionOrder:api.reschedule,addOrderAllocation:api.add,
  getEligibleOrders:api.orders,getEligibleDemandItems:api.items,getProductionOrderStatusHistory:api.history}));
const order=(extra:Partial<ProductionOrderData>={}):ProductionOrderData=>({id:"po1",organization_id:"org",production_order_number:"PO-LATE",work_center_id:"wc1",product_type:"film",planned_quantity:"100",unit:"kg",priority:"normal",status:"in_progress",
  planned_start_date:"2026-10-01",planned_end_date:"2026-10-10",created_by_user_id:"u",created_at:"",updated_at:"",allocations:[],lines:[],allocation_open:true,editable:false,target_spec_json:null,notes:null,
  lifecycle:{status_version:1,actual_start_at:"2026-10-01T08:00:00Z",actual_end_at:null,start_overdue:false,finish_overdue:true,terminal:false,actions:[]},...extra});
const updated=()=>order({planned_end_date:"2030-01-10",lifecycle:{...order().lifecycle!,finish_overdue:false}});
let messages:Awaited<ReturnType<typeof loadMessages>>;
beforeAll(async()=>{messages=await loadMessages("en");});
beforeEach(()=>{vi.clearAllMocks();api.allowed=true;api.reschedule.mockReset().mockResolvedValue(updated());api.add.mockReset().mockResolvedValue(updated());api.orders.mockResolvedValue([{id:"po1",production_order_number:"PO-LATE",status:"in_progress",work_center_name:"Line",product_type:"film",unit:"kg",planned_quantity:"100",planned_start_date:"2026-10-01",planned_end_date:"2026-10-10",finish_overdue:true}]);api.items.mockResolvedValue([{production_demand_item_id:"item1",production_demand_id:"d1",demand_number:"PD-LATE",customer_name:"Customer",line_no:1,product_type:"film",unit:"kg",remaining_quantity:"50"}]);api.history.mockResolvedValue([]);});
afterEach(cleanup);
const ui=(node:React.ReactNode)=>render(<NextIntlClientProvider locale="en" messages={messages} timeZone="UTC">{node}</NextIntlClientProvider>);

it.each(["draft","released","in_progress","on_hold","completed","closed","cancelled"] as const)("gates planning actions for %s",status=>{
  ui(<RescheduleOrderButton order={order({status})}/>);
  expect(Boolean(screen.queryByRole("button",{name:"Edit planning"}))).toBe(["draft","released","in_progress","on_hold"].includes(status));
});
it("hides scheduling without ORDERS_UPDATE",()=>{api.allowed=false;ui(<RescheduleOrderButton order={order()}/>);expect(screen.queryByRole("button")).toBeNull();});

it("locks the start once started, requires a reason and saves only the end",async()=>{
  const close=vi.fn(),changed=vi.fn();ui(<OrderRescheduleDialog order={order()} onClose={close} onChanged={changed}/>);
  expect((screen.getByLabelText("Planned start date") as HTMLInputElement).disabled).toBe(true);
  expect(screen.getByText(/planned start date is locked/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Planned finish date"),{target:{value:"2030-01-10"}});
  expect((screen.getByRole("button",{name:"Save"}) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Reason for rescheduling"),{target:{value:"Material delayed"}});
  expect(screen.getByText(/Planned finish change:/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button",{name:"Save"}));
  await waitFor(()=>expect(close).toHaveBeenCalledOnce());
  expect(api.reschedule).toHaveBeenCalledWith("po1",{planned_end_date:"2030-01-10",reason:"Material delayed"});
  expect(changed).toHaveBeenCalledOnce();
});
it("allows planning both dates before start and keeps values after a failed save",async()=>{
  api.reschedule.mockRejectedValue(new ApiClientError("blocked",409,{detail:{code:"PLANNED_START_LOCKED"}}));
  const close=vi.fn();ui(<OrderRescheduleDialog order={order({status:"released",lifecycle:{...order().lifecycle!,actual_start_at:null}})} onClose={close}/>);
  const start=screen.getByLabelText("Planned start date") as HTMLInputElement;expect(start.disabled).toBe(false);
  fireEvent.change(start,{target:{value:"2026-10-02"}});
  fireEvent.change(screen.getByLabelText("Reason for rescheduling"),{target:{value:"Material delayed"}});
  fireEvent.click(screen.getByRole("button",{name:"Save"}));
  expect((await screen.findByRole("alert")).textContent).toContain("already started");
  expect(close).not.toHaveBeenCalled();expect(start.value).toBe("2026-10-02");
  expect((screen.getByLabelText("Reason for rescheduling") as HTMLTextAreaElement).value).toBe("Material delayed");
});

async function selectOverdue(){
  ui(<ExistingOrderDialog item={{id:"item1",line_no:1,required_quantity:"50",unit:"kg",product_type:"film",target_spec_json:null,notes:null}} quantity="50" onClose={()=>{}}/>);
  expect(await screen.findByText("Overdue")).toBeTruthy();
  fireEvent.click(screen.getByRole("button",{name:"Add to this order"}));
  fireEvent.click(screen.getByLabelText("Extend the planned finish date"));
  fireEvent.change(screen.getByLabelText("Planned finish date"),{target:{value:"2030-01-10"}});
  fireEvent.change(screen.getByLabelText("Reason for rescheduling"),{target:{value:"Additional demand"}});
  fireEvent.click(screen.getByRole("button",{name:"Confirm allocation"}));
}
it("extends before attaching inside the existing-order dialog",async()=>{
  const sequence:string[]=[];api.reschedule.mockImplementation(async()=>{sequence.push("extend");return updated();});api.add.mockImplementation(async()=>{sequence.push("attach");return updated();});
  await selectOverdue();await waitFor(()=>expect(api.push).toHaveBeenCalledWith("/production-orders/po1"));
  expect(sequence).toEqual(["extend","attach"]);
});
it("does not attach or leave the dialog when extending fails",async()=>{
  api.reschedule.mockRejectedValue(new ApiClientError("closed",409,{detail:{code:"RESCHEDULE_NOT_ALLOWED"}}));
  await selectOverdue();expect((await screen.findByRole("alert")).textContent).toContain("cannot be rescheduled");
  expect(api.add).not.toHaveBeenCalled();expect(api.push).not.toHaveBeenCalled();expect(screen.getByRole("dialog")).toBeTruthy();
});
it("retries a failed allocation without repeating an already saved extension",async()=>{
  api.add.mockRejectedValueOnce(new ApiClientError("unavailable",409,{detail:{code:"DEMAND_NOT_PLANNABLE"}})).mockResolvedValue(updated());
  await selectOverdue();await screen.findByRole("alert");
  expect(screen.queryByLabelText("Extend the planned finish date")).toBeNull();
  fireEvent.click(screen.getByRole("button",{name:"Confirm allocation"}));
  await waitFor(()=>expect(api.push).toHaveBeenCalledWith("/production-orders/po1"));
  expect(api.reschedule).toHaveBeenCalledOnce();expect(api.add).toHaveBeenCalledTimes(2);
});

it.each([true,false])("extends from the order before adding a demand (success: %s)",async(success)=>{
  if(!success)api.reschedule.mockRejectedValue(new ApiClientError("closed",409,{detail:{code:"RESCHEDULE_NOT_ALLOWED"}}));
  ui(<OrderLines order={order()}/>);
  fireEvent.click(await findRecordOption(/PD-LATE/));
  fireEvent.click(screen.getByLabelText("Extend the planned finish date"));
  fireEvent.change(screen.getByLabelText("Planned finish date"),{target:{value:"2030-01-10"}});
  fireEvent.change(screen.getByLabelText("Reason for rescheduling"),{target:{value:"Additional demand"}});
  fireEvent.click(screen.getByRole("button",{name:"Add to order"}));
  await waitFor(()=>expect(api.reschedule).toHaveBeenCalledOnce());
  if(success)await waitFor(()=>expect(api.add).toHaveBeenCalledWith("po1","item1","50"));
  else {await screen.findByRole("alert");expect(api.add).not.toHaveBeenCalled();}
});
it("renders rescheduling alongside status events, with actor, dates and reason",async()=>{
  api.history.mockResolvedValue([{id:"status",from_status:"released",to_status:"in_progress",action:"start",trigger:"manual",actor_name:"Operator",created_at:"2026-10-01T08:00:00Z"}]);
  ui(<OrderStatusTimeline orderId="po1" revision={1} reschedules={[{id:"schedule",actor_user_id:"u",actor_name:"Planner",created_at:"2026-10-02T08:00:00Z",old_start:"2026-10-01",new_start:"2026-10-01",old_end:"2026-10-10",new_end:"2030-01-10",reason:"Material delayed"}]}/>);
  await waitFor(()=>expect(screen.getAllByRole("listitem")).toHaveLength(2));
  const first=screen.getAllByRole("listitem")[0];expect(within(first).getByText("Planning rescheduled")).toBeTruthy();
  expect(first.textContent).toContain("Planner");expect(first.textContent).toContain("Material delayed");expect(first.textContent).toContain("2030-01-10");
});
