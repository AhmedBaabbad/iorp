import {cleanup,fireEvent,render,screen,waitFor,within} from "@testing-library/react";
import {NextIntlClientProvider} from "next-intl";
import {afterEach,beforeAll,beforeEach,expect,it,vi} from "vitest";
import {loadMessages} from "@/i18n/messages";
import {RecordHistory} from "@/components/RecordHistory";
import {DemandItemDialog} from "@/features/production-demands/item-dialog";
import {DemandDetail} from "@/features/production-demands/detail";
const api=vi.hoisted(()=>({history:vi.fn(),save:vi.fn(),quantity:vi.fn(),get:vi.fn(),remove:vi.fn(),allowed:true}));
vi.mock("next/navigation",()=>({useRouter:()=>({push:vi.fn()})}));
vi.mock("@/components/layout/page-frame",()=>({PageFrame:({children}:{children:React.ReactNode})=><main>{children}</main>}));
vi.mock("@/hooks/useFormatter",()=>({useFormatter:()=>({dateTime:String})}));
vi.mock("@/features/auth/permission-hooks",()=>({usePermission:()=>api.allowed}));
vi.mock("@/lib/api-client",async original=>({...await original<object>(),apiClient:api.history}));
vi.mock("@/features/production-demands/api",()=>({demandsApi:{get:api.get,saveItem:api.save,setItemQuantity:api.quantity,removeItem:api.remove}}));
vi.mock("@/features/masterdata",()=>({useProducts:()=>[{key:"film",properties:[{key:"thickness",name_ar:"السماكة",name_en:"Thickness",kind:"number",allows_range:true}]}],ProductSelect:({value,onChange,disabled,ariaLabel}:{value:string;onChange:(s:string)=>void;disabled?:boolean;ariaLabel:string})=><input aria-label={ariaLabel} value={value} disabled={disabled} onChange={e=>onChange(e.target.value)}/>}));
let messages:Awaited<ReturnType<typeof loadMessages>>;
beforeAll(async()=>{messages=await loadMessages("en");});
beforeEach(()=>{vi.clearAllMocks();api.allowed=true;api.save.mockResolvedValue({});api.quantity.mockResolvedValue({});api.history.mockResolvedValue({items:[],total:0,pages:0});});
afterEach(()=>{cleanup();window.history.replaceState(null,"","/");});
const ui=(node:React.ReactNode)=>render(<NextIntlClientProvider locale="en" messages={messages} timeZone="UTC">{node}</NextIntlClientProvider>);
const item={id:"i1",line_no:1,product_type:"film",target_spec_json:{thickness:{min:.7,max:.75}},required_quantity:"50",unit:"kg",notes:null};

it("renders translated old/new specifications and allocation status, with server pagination",async()=>{
  api.history.mockResolvedValue({items:[{id:"e",action:"production_allocation.released",actor_name:"Planner",created_at:"2026-11-26T10:00:00Z",details:{changes:[{field:"target_spec_json.thickness",old:{min:.7,max:.75},new:{min:.8,max:.85}},{field:"allocation_status",old:"active",new:"released"}],reason:"Correct thickness",related:{production_order_number:"PO-1"}}}],total:51,pages:2});
  ui(<RecordHistory entityType="production_demand" entityId="d1"/>);
  expect(await screen.findByText("0.70 – 0.75")).toBeTruthy();expect(screen.getByText("0.80 – 0.85")).toBeTruthy();
  expect(screen.getByText("0.70 – 0.75").getAttribute('dir')).toBe('ltr');
  expect(screen.getByRole("columnheader",{name:"Previous value"})).toBeTruthy();expect(screen.getByText("Thickness")).toBeTruthy();
  expect(screen.getAllByText("Returned to planning").length).toBe(2);expect(screen.getByText(/Correct thickness/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button",{name:"Next"}));
  await waitFor(()=>expect(api.history).toHaveBeenLastCalledWith("/record-history/production_demand/d1?page=2&page_size=50",{notify:false}));
});

it("keeps edited values after a failed save and normalizes ranges only on save",async()=>{
  api.save.mockRejectedValueOnce(new Error("unavailable"));const close=vi.fn(),saved=vi.fn();
  ui(<DemandItemDialog demandId="d1" item={item} salesOrder={false} onClose={close} onSaved={saved}/>);
  const thickness=screen.getByLabelText("Thickness");
  fireEvent.change(thickness,{target:{value:"0.70"}});expect((thickness as HTMLInputElement).value).toBe("0.70");
  fireEvent.change(thickness,{target:{value:"0.70-0.75"}});
  fireEvent.click(screen.getByRole("button",{name:"Save"}));await screen.findByRole("alert");
  expect(close).not.toHaveBeenCalled();expect((thickness as HTMLInputElement).value).toBe("0.70-0.75");
  fireEvent.click(screen.getByRole("button",{name:"Save"}));await waitFor(()=>expect(close).toHaveBeenCalledOnce());
  expect(api.save).toHaveBeenLastCalledWith("d1",{product_type:"film",target_spec_json:{thickness:{min:.7,max:.75}},required_quantity:"50",unit:"kg",notes:null},"i1");
});

it("keeps sales order product, unit and specifications locked",()=>{
  ui(<DemandItemDialog demandId="d1" item={item} salesOrder onClose={vi.fn()} onSaved={vi.fn()}/>);
  expect((screen.getByLabelText("Thickness") as HTMLInputElement).disabled).toBe(true);
  expect((screen.getByLabelText("Quantity") as HTMLInputElement).disabled).toBe(false);
});

it("saves a sales-order item quantity without resending locked legacy null fields",async()=>{
  const close=vi.fn();
  ui(<DemandItemDialog demandId="d1" item={{...item,product_type:null,target_spec_json:null}} salesOrder onClose={close} onSaved={vi.fn()}/>);
  fireEvent.change(screen.getByLabelText('Quantity'),{target:{value:'40'}});
  fireEvent.click(screen.getByRole('button',{name:'Save'}));
  await waitFor(()=>expect(close).toHaveBeenCalledOnce());
  expect(api.quantity).toHaveBeenCalledWith('d1','i1','40',null);
  expect(api.save).not.toHaveBeenCalled();
});

it("edits historical properties outside the current template without losing a stored range",async()=>{
  ui(<DemandItemDialog demandId="d1" item={{...item,target_spec_json:{...item.target_spec_json,color:"blue"}}} salesOrder={false} onClose={vi.fn()} onSaved={vi.fn()}/>);
  fireEvent.change(screen.getByLabelText("Value"),{target:{value:"red"}});
  fireEvent.click(screen.getByRole("button",{name:"Save"}));
  await waitFor(()=>expect(api.save).toHaveBeenCalledWith("d1",expect.objectContaining({target_spec_json:{color:"red",thickness:{min:.7,max:.75}}}),"i1"));
});

it("offers an item dialog only for unallocated lines in a partially planned demand",async()=>{
  const active={...item,id:"i2",line_no:2,allocations:[{id:"a2",status:"active",production_order_number:"PO-LOCKED",production_order_status:"draft",allocated_quantity:"50",created_at:"2026-11-26T10:00:00Z"}]};
  api.get.mockResolvedValue({id:"d1",demand_number:"PD-1",customer:{id:"c",code:"C",name:"Customer"},quote:null,request_date:"2026-11-26",priority:"normal",status:"partially_planned",items:[item,active],total_remaining:"50",total_required:"100",total_active_allocated:"50",total_released_allocated:"0",allocation_percentage:"50",created_at:"2026-11-26T10:00:00Z"});
  ui(<DemandDetail id="d1"/>);
  const edit=await screen.findByRole("button",{name:"Edit item"});expect(screen.getByText(/Return it to planning from/)).toBeTruthy();
  fireEvent.click(edit);expect(await screen.findByRole("dialog",{name:"Edit item"})).toBeTruthy();
  expect(screen.queryByRole("link",{name:"Edit demand"})).toBeNull();
  const dialog=screen.getByRole("dialog");fireEvent.click(within(dialog).getByRole("button",{name:"Cancel"}));
  fireEvent.click(screen.getByRole("tab",{name:"History"}));expect(screen.getByRole("tabpanel").textContent).toContain("History");
});
