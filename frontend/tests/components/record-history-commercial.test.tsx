import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {NextIntlClientProvider} from "next-intl";
import {afterEach,beforeAll,beforeEach,expect,it,vi} from "vitest";
import {loadMessages} from "@/i18n/messages";
import {RecordHistory} from "@/components/RecordHistory";
import {Tabs} from "@/components/ui/Tabs";
const api=vi.hoisted(()=>({history:vi.fn()}));
vi.mock("@/hooks/useFormatter",()=>({useFormatter:()=>({dateTime:(v:string)=>`DT(${v})`,date:(v:string)=>`D(${v})`})}));
vi.mock("@/lib/api-client",async original=>({...await original<object>(),apiClient:api.history}));
vi.mock("@/features/masterdata",()=>({useProducts:()=>[{key:"pp_strap",properties:[{key:"width_mm",name_ar:"العرض",name_en:"Width",kind:"number"}]}]}));
type Messages=Awaited<ReturnType<typeof loadMessages>>;
let en:Messages,ar:Messages;
beforeAll(async()=>{en=await loadMessages("en");ar=await loadMessages("ar");});
beforeEach(()=>{vi.clearAllMocks();api.history.mockResolvedValue({items:[],total:0,pages:0});});
afterEach(()=>{cleanup();window.history.replaceState(null,"","/");});
const ui=(node:React.ReactNode,locale:"en"|"ar"="en")=>render(<NextIntlClientProvider locale={locale} messages={locale==="en"?en:ar} timeZone="UTC">{node}</NextIntlClientProvider>);

it("words a quotation's lines, statuses and reason in the reader's language",async()=>{
  api.history.mockResolvedValue({total:2,pages:1,items:[
    {id:"2",action:"quote.rejected",actor_name:"Sara",created_at:"2026-11-28T10:00:00Z",details:{schema_version:1,reason:"Price too high",
      changes:[{field:"status",old:"issued",new:"rejected"}],related:{}}},
    {id:"1",action:"quote.updated",actor_name:"Sara",created_at:"2026-11-27T10:00:00Z",details:{schema_version:1,related:{},changes:[
      {field:"valid_until",old:"2026-06-19T10:00:00+00:00",new:"2026-06-29T10:00:00+00:00"},
      {field:"requested_spec_json.width_mm",old:19,new:25,line:1,line_change:"changed"},
      {field:"quantity",old:"500",new:null,line:2,line_change:"removed"}]}}]});
  ui(<RecordHistory entityType="quote" entityId="q1"/>);
  expect((await screen.findAllByText("Rejected")).length).toBe(2);  // the step, and the status it led to
  expect(screen.getByText("Issued")).toBeTruthy();expect(screen.getByText(/Price too high/)).toBeTruthy();
  expect(screen.getByText("Line 1 · Width")).toBeTruthy();expect(screen.getByText("Line 2 (removed) · Quantity")).toBeTruthy();
  expect(screen.getByText("DT(2026-06-29T10:00:00+00:00)")).toBeTruthy();
  expect(api.history).toHaveBeenCalledWith("/record-history/quote/q1?page=1&page_size=50",{notify:false});
});

it("names the child record a customer entry is about and its own enumerations, in Arabic",async()=>{
  api.history.mockResolvedValue({total:2,pages:1,items:[
    {id:"2",action:"followup.completed",actor_name:"سارة",created_at:"2026-11-28T10:00:00Z",details:{schema_version:1,
      changes:[{field:"status",old:"pending",new:"completed"}],related:{subject_kind:"follow_up",subject_name:"إرسال السعر"}}},
    {id:"1",action:"customer.contact_added",actor_name:"سارة",created_at:"2026-11-27T10:00:00Z",details:{schema_version:1,
      changes:[{field:"is_default",old:null,new:true}],related:{subject_kind:"contact",subject_name:"Sara"}}}]});
  ui(<RecordHistory entityType="customer" entityId="c1"/>,"ar");
  expect(await screen.findByText("إنجاز متابعة")).toBeTruthy();
  expect(screen.getByText("المتابعة: إرسال السعر")).toBeTruthy();expect(screen.getByText("جهة الاتصال: Sara")).toBeTruthy();
  expect(screen.getByText("مكتمل")).toBeTruthy();expect(screen.getByText("نعم")).toBeTruthy();
  expect(screen.getByRole("heading",{name:"السجل"})).toBeTruthy();
});

it("builds a lazy tab only while it is open, so its history is read again on every visit",async()=>{
  ui(<Tabs label="Quote" items={[{id:"data",label:"Details",content:<p>data</p>},{id:"history",label:"History",lazy:true,content:<RecordHistory entityType="quote" entityId="q1"/>}]}/>);
  expect(api.history).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("tab",{name:"History"}));
  expect(await screen.findByText("No recorded events.")).toBeTruthy();
  fireEvent.click(screen.getByRole("tab",{name:"Details"}));fireEvent.click(screen.getByRole("tab",{name:"History"}));
  await screen.findByText("No recorded events.");
  expect(api.history).toHaveBeenCalledTimes(2);
});

it("shows one line per entry: what changed by name, the values only behind Details",async()=>{
  api.history.mockResolvedValue({total:1,pages:1,items:[{id:"1",action:"quote.updated",actor_name:"Sara",created_at:"2026-11-27T10:00:00Z",
    details:{schema_version:1,related:{},changes:[{field:"notes",old:"a",new:"b"},{field:"quantity",old:"1",new:"2",line:1,line_change:"changed"}]}}]});
  const {container}=ui(<RecordHistory entityType="quote" entityId="q1"/>);
  expect(await screen.findByText("Changed: Notes, Line 1 · Quantity")).toBeTruthy();
  const details=container.querySelector("details")!;
  expect(details.open).toBe(false);expect(details.querySelector("summary")!.textContent).toBe("Details (previous and new values)");
  expect(details.querySelector("table")).toBeTruthy();
});
