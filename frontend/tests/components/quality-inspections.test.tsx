import {changeControl} from "./record-test-helpers";
// QUAL-001: inspections close with balanced quantities, rejections need a final decision, and both keep a production order from closing.
import { act, cleanup, fireEvent, render, screen, within, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";
import { ApiClientError } from "@/lib/api-client";
import type { Measurement, QualityCheckData } from "@/features/quality-checks/types";
import type { QualityRejectionData } from "@/features/quality-rejections/types";

const api = vi.hoisted(() => ({ apiClient: vi.fn() }));
const nav = vi.hoisted(() => ({ push: vi.fn(), params: new URLSearchParams() }));
const perms = vi.hoisted(() => ({ granted: new Set<string>() }));
vi.mock("@/lib/api-client", async importOriginal => ({ ...(await importOriginal<object>()), apiClient: api.apiClient }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: nav.push, replace: vi.fn() }), usePathname: () => "/", useSearchParams: () => nav.params }));
vi.mock("@/features/auth/permission-hooks", () => ({ usePermission: (code: string) => perms.granted.has(code) }));
vi.mock("@/hooks/useFormatter", () => ({ useFormatter: () => ({ date: (v: string) => v, dateTime: (v: string) => v, number: (v: string) => v, quantity: (v: string, u?: string) => `${v} ${u ?? ""}`.trim() }) }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) => <main><h1>{title}</h1>{action}{children}</main> }));
vi.mock("@/features/quality-defects", () => ({ QualityDefectsList: () => null }));

import { QualityCheckDetail } from "@/features/quality-checks/components/QualityCheckDetail";
import { QualityChecksList } from "@/features/quality-checks/components/QualityChecksList";
import { QualityRejectionDetail } from "@/features/quality-rejections/components/QualityRejectionDetail";
import { OrderStatusPanel } from "@/features/production-orders/components/OrderStatusPanel";
import { OrderQualitySection } from "@/features/order-quality/OrderQualitySection";
import type { ProductionOrderData } from "@/features/production-orders/types";
import { Q, QUALITY_REPORT } from "@/lib/quality-permissions";
import { ReportForm } from "@/features/reports/ReportForm";
import { SpecificationForm } from "@/features/quality-specifications";
import { CopySpecificationDialog } from "@/features/quality-specifications/components/CopySpecificationDialog";
import { bilingualText } from "@/lib/bilingual-text";
import { emptyLine, targetText } from "@/features/quality-specifications/spec-lines";
import { normalizeReading, splitReadings } from "@/features/quality-checks/components/MeasurementsSection";
import type { Definition } from "@/features/reports/api";

let en: Record<string, unknown>;
let ar: Record<string, unknown>;
beforeAll(async () => {
  en = await loadMessages("en") as Record<string, unknown>;
  ar = await loadMessages("ar") as Record<string, unknown>;
});
beforeEach(() => {
  api.apiClient.mockReset();
  nav.params = new URLSearchParams();
  perms.granted = new Set(Object.values(Q));
});
afterEach(cleanup);
const ui = (node: ReactNode, locale: "en" | "ar" = "en") =>
  render(<NextIntlClientProvider locale={locale} messages={locale === "en" ? en : ar} timeZone="UTC">{node}</NextIntlClientProvider>);
const posted = (path: string) => api.apiClient.mock.calls.find(([p, o]) => p === path && o?.method === "POST")?.[1]?.body;

it("creates a check in its order's dialog and refreshes the section without navigation",async()=>{
  nav.push.mockReset();
  api.apiClient.mockImplementation((path:string,options?:{method?:string})=>Promise.resolve(options?.method==='POST'?check()
    :path.includes('/lookups/orders')?[{id:'po1',number:'PO-1',status:'in_progress',product_type:'film',unit:'kg',items:[]}]
    :{items:[],total:0,page:1,pages:0,page_size:1}));
  ui(<OrderQualitySection order={{id:'po1',status:'in_progress',production_order_number:'PO-1'}}/>);
  fireEvent.click(screen.getByRole('button',{name:'New check for this order'}));
  const dialog=await screen.findByRole('dialog');
  expect((within(dialog).getByRole('combobox',{name:'Production order'}) as HTMLSelectElement).disabled).toBe(true);
  fireEvent.click(within(dialog).getByRole('button',{name:'Create check'}));
  await waitFor(()=>expect(screen.queryByRole('dialog')).toBeNull());
  expect(posted('/quality/quality-checks')).toMatchObject({production_order_id:'po1'});
  expect(api.apiClient.mock.calls.some(([path])=>String(path).includes('/lookups/orders?q=PO-1'))).toBe(true);
  await waitFor(()=>expect(api.apiClient.mock.calls.filter(([path])=>String(path).startsWith('/quality/quality-checks?')).length).toBe(6));
  expect(nav.push).not.toHaveBeenCalled();
});

it("records a rejection in the check dialog and updates its list without navigation",async()=>{
  nav.push.mockReset();let saved=false;
  const base=check({status:'closed',result:'rejected',qty_rejected:'10.000',actions:[]});
  api.apiClient.mockImplementation((path:string,options?:{method?:string})=>{
    if(path==='/quality/quality-rejections'&&options?.method==='POST'){saved=true;return Promise.resolve(rejection());}
    return Promise.resolve(path==='/quality/quality-checks/c1'?{...base,rejections:saved?[rejection({rejection_code:'QR-INLINE'})]:[]}:[]);
  });
  ui(<QualityCheckDetail qualityCheckId="c1"/>);
  fireEvent.click(await screen.findByRole('button',{name:'Record another rejection'}));
  const dialog=await screen.findByRole('dialog',{name:'Record a rejection'});
  await within(dialog).findByLabelText('Source');
  changeControl(within(dialog).getByLabelText('Rejected quantity (kg)'),{target:{value:'2'}});
  changeControl(within(dialog).getByLabelText('Reason details'),{target:{value:'Retained samples failed'}});
  fireEvent.click(within(dialog).getByRole('button',{name:'Record rejection'}));
  expect(await screen.findByRole('link',{name:'QR-INLINE'})).toBeTruthy();
  expect(posted('/quality/quality-rejections')).toMatchObject({quality_check_id:'c1',quantity_rejected:'2'});
  expect(nav.push).not.toHaveBeenCalled();
});

function check(over: Partial<QualityCheckData> = {}): QualityCheckData {
  return { id: "c1", inspection_code: "QI-2026-0001", check_type: "finished_product_inspection", status: "under_inspection", result: null,
    check_datetime: "2026-10-01T08:00:00Z", production_order_id: "po1", production_order_item_id: null, sample_id: null,
    qty_inspected: "100.000", qty_accepted: "0.000", qty_rejected: "0.000", unit: "kg", order_number: "PO-1", item_line_no: null, sample_code: null,
    checked_by_name: "Sara", actions: ["edit", "close", "cancel"], created_at: "", updated_at: "", notes: null, started_at: "2026-10-01T08:05:00Z",
    closed_at: null, closed_by_name: null, cancel_reason: null, history: [], rejections: [],
    specification_id: null, specification_code: null, specification_revision: null, lot_values: null, measurements: [], ...over };
}
function rejection(over: Partial<QualityRejectionData> = {}): QualityRejectionData {
  return { id: "r1", rejection_code: "QR-2026-0001", quality_check_id: "c1", production_order_id: "po1", production_order_item_id: null,
    rejection_date: "2026-10-01", rejection_reason: "out_of_spec", disposition: null, disposition_status: "pending", quantity_rejected: "8.000", unit: "kg",
    order_number: "PO-1", item_line_no: null, inspection_code: "QI-2026-0001", unresolved: true, actions: ["edit", "decide"], created_at: "",
    rejection_notes: "Thickness below spec", rejected_by_name: "Sara", decision_notes: null, concession_approved_by: null,
    decided_at: null, decided_by_name: null, execution_notes: null, executed_at: null, executed_by_name: null, history: [], updated_at: "", ...over };
}

describe("quality checks", () => {
  it("lists checks with Arabic statuses, including cancelled", async () => {
    api.apiClient.mockResolvedValue({ items: [check({ status: "cancelled", actions: [] })], total: 1, page: 1, page_size: 50, pages: 1 });
    ui(<QualityChecksList />, "ar");
    const table = await screen.findByRole("table", { name: "قائمة فحوصات الجودة" });
    expect(within(table).getAllByText("ملغى").length).toBeGreaterThan(0);
    // the list's own page (the defect-category filter also reads the organization's lists, MD-003)
    expect(api.apiClient.mock.calls.map(c => c[0])).toContain("/quality/quality-checks?page=1&page_size=50");
  });

  it("closes with balanced quantities; a rejected quantity sends its reason", async () => {
    api.apiClient.mockImplementation((path: string, o?: { method?: string }) =>
      Promise.resolve(o?.method === "POST" ? check({ status: "closed", result: "rejected", qty_accepted: "92.000", qty_rejected: "8.000", actions: [] }) : check()));
    ui(<QualityCheckDetail qualityCheckId="c1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Close with result" }));
    const dialog = screen.getByRole("dialog", { name: "Close the check with its result" });
    changeControl(within(dialog).getByLabelText("Result"), { target: { value: "accepted" } });
    // Accepted 92 of 100 leaves 8 rejected: an "accepted" result cannot carry it.
    changeControl(within(dialog).getByLabelText(/^Accepted/), { target: { value: "92" } });
    expect(within(dialog).getByText("An accepted result cannot have a rejected quantity.")).toBeTruthy();
    expect((within(dialog).getByRole("button", { name: "Close with result" }) as HTMLButtonElement).disabled).toBe(true);
    changeControl(within(dialog).getByLabelText("Result"), { target: { value: "rejected" } });
    changeControl(within(dialog).getByLabelText("Rejection reason"), { target: { value: "out_of_spec" } });
    await act(async () => { fireEvent.click(within(dialog).getByRole("button", { name: "Close with result" })); });
    expect(posted("/quality/quality-checks/c1/close")).toMatchObject({ result: "rejected", qty_inspected: "100.000", qty_accepted: "92", qty_rejected: "8", rejection_reason: "out_of_spec" });
  });

  it("shows only the actions the server offers", async () => {
    perms.granted = new Set([Q.CHECKS_READ]);
    api.apiClient.mockResolvedValue(check({ status: "closed", result: "accepted", actions: [] }));
    ui(<QualityCheckDetail qualityCheckId="c1" />);
    await screen.findByText("This check is final.");
    expect(screen.queryByRole("button", { name: "Close with result" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Cancel check" })).toBeNull();
  });
});

describe("quality rejections", () => {
  it("use as is needs the approver and a justification", async () => {
    api.apiClient.mockImplementation((path: string, o?: { method?: string }) =>
      Promise.resolve(o?.method === "POST" ? rejection({ disposition: "use_as_is", disposition_status: "decided", unresolved: false, actions: ["decide", "execute"] }) : rejection()));
    ui(<QualityRejectionDetail qualityRejectionId="r1" />, "ar");
    fireEvent.click(await screen.findByRole("button", { name: "اتخاذ القرار" }));
    const dialog = screen.getByRole("dialog", { name: "قرار التصرف" });
    changeControl(within(dialog).getByLabelText("قرار التصرف"), { target: { value: "use_as_is" } });
    const save = within(dialog).getByRole("button", { name: "حفظ القرار" }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    changeControl(within(dialog).getByLabelText("الموافق على الاستثناء"), { target: { value: "مدير الجودة" } });
    changeControl(within(dialog).getByLabelText("مبرر الاستثناء"), { target: { value: "ضمن تفاوت مقبول لدى العميل" } });
    await act(async () => { fireEvent.click(save); });
    expect(posted("/quality/quality-rejections/r1/decide")).toEqual({ disposition: "use_as_is", decision_notes: "ضمن تفاوت مقبول لدى العميل", concession_approved_by: "مدير الجودة" });
    expect(await screen.findByRole("button", { name: "تسجيل التنفيذ" })).toBeTruthy();
  });

  it("names a hold as blocking the order close", async () => {
    api.apiClient.mockResolvedValue(rejection({ disposition: "hold", disposition_status: "decided", actions: ["decide"] }));
    ui(<QualityRejectionDetail qualityRejectionId="r1" />, "ar");
    expect(await screen.findByText(/الحجز ليس نهائيًا/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "تسجيل التنفيذ" })).toBeNull();
  });
});

describe("production order close gate", () => {
  it("lists the quality blockers the server returns", async () => {
    api.apiClient.mockRejectedValue(new ApiClientError("blocked", 409, { detail: { code: "CLOSE_BLOCKED",
      blockers: [{ code: "QUALITY_CHECKS_OPEN", count: 2 }, { code: "QUALITY_REJECTIONS_UNRESOLVED", count: 1 }] } }));
    const order = { id: "po1", production_order_number: "PO-1", status: "completed",
      lifecycle: { status_version: 3, actual_start_at: null, actual_end_at: null, start_overdue: false, finish_overdue: false, terminal: false,
        actions: [{ action: "start", target: "in_progress", requires_reason: false, confirm: false }] } } as unknown as ProductionOrderData;
    ui(<OrderStatusPanel order={order} />, "ar");
    await act(async () => { fireEvent.click(screen.getAllByRole("button")[0]); });
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("لا يمكن إغلاق الأمر بعد:");
    expect(alert.textContent).toContain("فحوصات جودة مفتوحة أو قيد الفحص: 2");
    expect(alert.textContent).toContain("حالات رفض بلا قرار نهائي (بانتظار القرار أو محجوزة): 1");
  });
});

describe("quality reports", () => {
  const definition: Definition = { key: "quality.checks_summary", module: "quality", title_ar: "ملخص فحوصات الجودة", title_en: "Quality checks summary",
    default_orientation: "landscape", params_schema: { properties: {
      check_type: { type: "array", items: { enum: ["in_process_inspection", "finished_product_inspection"] } },
      grouping: { type: "string", enum: ["none", "check_type", "result"], default: "none" } }, required: [] },
    sections: [{ key: "totals", title_ar: "الإجماليات حسب الوحدة", title_en: "Totals by unit", default_enabled: true }] };

  it("labels the quality filters in Arabic", () => {
    ui(<ReportForm definition={definition} />, "ar");
    expect(screen.getByLabelText("نوع الفحص")).toBeTruthy();
    expect(screen.getByRole("option", { name: "فحص المنتج النهائي" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "النتيجة" })).toBeTruthy();
  });

  it("opens the inspection report from the check with the check fixed", async () => {
    perms.granted = new Set([Q.CHECKS_READ, QUALITY_REPORT.CHECK_FULL]);
    const report = { ...definition, key: "quality.check_full", title_en: "Quality check report", context_fields: ["check_id"],
      params_schema: { properties: { check_id: { type: "string", lookup: "checks" } }, required: ["check_id"] },
      sections: [{ key: "information", title_ar: "معلومات الفحص", title_en: "Inspection information", default_enabled: true }] };
    api.apiClient.mockImplementation((path: string) => {
      if (path.startsWith("/reports/definitions")) return Promise.resolve([report]);
      if (path.endsWith("/preview")) return Promise.resolve({ text: () => Promise.resolve("<html><body>QI</body></html>") });
      return Promise.resolve(check({ status: "closed", result: "accepted", actions: [] }));
    });
    ui(<QualityCheckDetail qualityCheckId="c1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Inspection report" }));
    const dialog = await screen.findByRole("dialog", { name: "Inspection report" });
    expect(api.apiClient.mock.calls.some(([p]) => String(p).includes("module=quality") && String(p).includes("check_id=c1"))).toBe(true);
    expect(within(dialog).queryByLabelText("Quality check")).toBeNull();  // fixed to this check
    await act(async () => { fireEvent.click(within(dialog).getByRole("button", { name: "Preview" })); });
    const sent = api.apiClient.mock.calls.find(([p]) => p === "/reports/quality.check_full/preview")?.[1]?.body;
    expect(sent).toMatchObject({ check_id: "c1", sections: ["information"] });
  });
});

function measurement(over: Partial<Measurement> = {}): Measurement {
  return { id: "m1", position: 1, parameter_code: "WIDTH", name_ar: "العرض", name_en: "Width", kind: "numeric", unit: "mm",
    method_ar:null,method_en: "Calibrated vernier caliper", requirement_ar:null,requirement_en: null, acceptance_ar:null,acceptance_en: null, target: "5.0000", lower_limit: "4.8000", upper_limit: "5.2000",
    readings_required: 3, readings: null, attribute_result: null, observation: null, reading_count: 0, minimum: null, maximum: null, mean: null,
    status: "pending", measured_at: null, ...over };
}

describe("measurements", () => {
  it("reads Arabic digits, the Arabic decimal separator and a decimal comma; splits pasted lists", () => {
    expect(normalizeReading("٥٫٠٢")).toBe("5.02");
    expect(normalizeReading("4,98")).toBe("4.98");
    expect(splitReadings("5.02 4.98 ،5.01؛٥")).toEqual(["5.02", "4.98", "5.01", "5"]);
  });

  it("records readings and shows the server's verdict with the limits", async () => {
    const planned = check({ specification_code: "ROF-TDS-PP-001", specification_revision: 1, actions: ["edit", "measure", "close", "cancel"],
      measurements: [measurement(), measurement({ id: "m2", parameter_code: "COLOR", name_ar: "اللون", name_en: "Color", kind: "attribute", unit: null,
        requirement_ar:null,requirement_en: "As approved sample", acceptance_ar:null,acceptance_en: "Visual match required", target: null, lower_limit: null, upper_limit: null, readings_required: 1 })] });
    const measured = { ...planned, measurements: [measurement({ readings: ["5.02", "4.98", "5.01"], reading_count: 3, minimum: "4.98", maximum: "5.02",
      mean: "5.0033", status: "pass" }), planned.measurements[1]] };
    api.apiClient.mockImplementation((_path: string, o?: { method?: string }) => Promise.resolve(o?.method === "PUT" ? measured : planned));
    ui(<QualityCheckDetail qualityCheckId="c1" />, "ar");
    const section = await screen.findByRole("region", { name: "نتائج القياس" });
    expect(within(section).getByText("4.8 – 5.2")).toBeTruthy();
    expect(within(section).getByText("المواصفة المرجعية: ROF-TDS-PP-001 — rev 1")).toBeTruthy();
    // One box per required reading, with a counter; nothing is sent until "save measurements".
    expect(within(section).getByText("0 من 3 قراءات")).toBeTruthy();
    expect((within(section).getByRole("button", { name: "حفظ القياسات" }) as HTMLButtonElement).disabled).toBe(true);
    changeControl(within(section).getByLabelText("القراءة 1 — العرض"), { target: { value: "٥٫٠٢" } });
    changeControl(within(section).getByLabelText("القراءة 2 — العرض"), { target: { value: "4,98" } });
    changeControl(within(section).getByLabelText("القراءة 3 — العرض"), { target: { value: "5.01" } });
    expect(within(section).getByText("3 من 3 قراءات")).toBeTruthy();
    changeControl(within(section).getByLabelText("نتيجة اللون"), { target: { value: "conforming" } });
    await act(async () => { fireEvent.click(within(section).getByRole("button", { name: "حفظ القياسات (2)" })); });
    const puts = api.apiClient.mock.calls.filter(([, o]) => o?.method === "PUT").map(([p, o]) => [p, o.body]);
    expect(puts).toEqual([
      ["/quality/quality-checks/c1/measurements/m1", { readings: ["5.02", "4.98", "5.01"], observation: null }],
      ["/quality/quality-checks/c1/measurements/m2", { attribute_result: "conforming", observation: null }]]);
    expect(within(section).getByText("حُفظت 2 خاصية.")).toBeTruthy();
    expect(await within(section).findByText("مطابق: 1 · غير مطابق: 0 · لم يُقَس: 1")).toBeTruthy();
  });

  it("will not close while the plan is not fully measured", async () => {
    api.apiClient.mockResolvedValue(check({ measurements: [measurement()] }));
    ui(<QualityCheckDetail qualityCheckId="c1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Close with result" }));
    const dialog = screen.getByRole("dialog", { name: "Close the check with its result" });
    changeControl(within(dialog).getByLabelText("Result"), { target: { value: "accepted" } });
    expect(within(dialog).getByText("1 parameters of the plan are not measured yet.")).toBeTruthy();
    expect((within(dialog).getByRole("button", { name: "Close with result" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("offers the specifications in force when the inspection has no plan yet", async () => {
    const plain = check({ actions: ["edit", "measure", "close", "cancel"] });
    api.apiClient.mockImplementation((path: string) => Promise.resolve(path.endsWith("/specifications")
      ? [{ id: "s1", code: "ROF-TDS-PP-001", revision: 2, title: "PP strap", product_type: "pp_strap", grade: null, matches_product: true, missing_keys: [] }]
      : path.endsWith("/plan") ? { ...plain, specification_code: "ROF-TDS-PP-001", specification_revision: 2, measurements: [measurement()] } : plain));
    ui(<QualityCheckDetail qualityCheckId="c1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Apply measurement plan" }));
    expect(await screen.findByText("Reference specification: ROF-TDS-PP-001 — rev 2")).toBeTruthy();
    expect(api.apiClient.mock.calls.some(([p, o]) => p === "/quality/quality-checks/c1/plan" && o?.body?.specification_id === "s1")).toBe(true);
  });
});

describe("specification form", () => {
  it("keeps a retired saved property visible with a warning and sends it unchanged",async()=>{
    const parameter={id:"p",code:"WIDTH",name_ar:"العرض",name_en:"Width",kind:"numeric",unit:"mm",method_ar:null,method_en:null,is_active:true,sort_order:1};
    const line={...emptyLine("p"),...parameter,id:"line",parameter_id:"p",position:1,target_source:"order_line",order_spec_key:"retired_key",parameter_method_ar:null,parameter_method_en:null};
    const spec={id:"legacy",code:"LEGACY",title:"Old specification",revision:1,status:"draft",product_type:"film",grade:null,notes:null,actions:["edit"],lines:[line]};
    api.apiClient.mockImplementation((path:string,o?:{method?:string})=>Promise.resolve(o?.method==="PATCH"?spec
      :path.endsWith("/numeric-properties")||path.startsWith("/masterdata/")?[]:path.endsWith("/legacy")?spec:[parameter]));
    ui(<SpecificationForm specId="legacy"/>);
    const input=await screen.findByRole("combobox",{name:"Order line key"});
    expect((input as HTMLInputElement).value).toBe("retired_key");
    expect(screen.getByRole("status").textContent).toMatch(/not found in product templates/);
    await act(async()=>{fireEvent.click(screen.getByRole("button",{name:"Save"}));});
    const payload=api.apiClient.mock.calls.find(([,options])=>options?.method==="PATCH")?.[1]?.body;
    expect(payload.lines[0].order_spec_key).toBe("retired_key");
  });
  it("uses catalog properties for every numeric parameter and keeps tolerance only for scalar orders", async () => {
    const parameter = {id:"weight",code:"WEIGHT",name_ar:"الوزن",name_en:"Weight",kind:"numeric",unit:"kg",method_ar:null,method_en:null,is_active:true,sort_order:1};
    api.apiClient.mockImplementation((path:string)=>Promise.resolve(path.endsWith("/numeric-properties")
      ? [{key:"custom_mass",name_ar:"كتلة المنتج",name_en:"Product mass"}]
      :path.startsWith("/masterdata/")?[]:[parameter]));
    ui(<SpecificationForm/>);
    await screen.findByLabelText("Specification no.");
    fireEvent.click(screen.getByRole("button",{name:"Add all parameters"}));
    expect(screen.getByLabelText("Minimum")).toBeTruthy();
    changeControl(screen.getByLabelText("Target from"),{target:{value:"order_line"}});
    expect(screen.queryByLabelText("Minimum")).toBeNull();
    expect(screen.queryByLabelText("Maximum")).toBeNull();
    const input=screen.getByRole("combobox",{name:"Order line key"});
    fireEvent.focus(input);
    fireEvent.change(input,{target:{value:"Product mass"}});
    fireEvent.click(screen.getByRole("option",{name:/Product mass/}));
    expect((input as HTMLInputElement).value).toBe("Product mass");
    expect(screen.getByLabelText("Tolerance below (−)")).toBeTruthy();
    expect(screen.getByText(/only when the order specification contains a single/)).toBeTruthy();
    expect(screen.getByLabelText("Test method (Arabic)")).toBeTruthy();
    expect(screen.getByLabelText("Test method (English)")).toBeTruthy();
  });
  it("builds lines per parameter kind and sends a draft", async () => {
    const parameters = [
      { id: "p1", code: "WIDTH", name_ar: "العرض", name_en: "Width", kind: "numeric", unit: "mm", method_ar:null,method_en: "Caliper", is_active: true, sort_order: 10 },
      { id: "p2", code: "COLOR", name_ar: "اللون", name_en: "Color", kind: "attribute", unit: null, method_ar:null,method_en: "Visual", is_active: true, sort_order: 20 },
    ];
    api.apiClient.mockImplementation((path: string, o?: { method?: string }) => Promise.resolve(o?.method === "POST" ? { id: "s1" }
      : path.endsWith("/numeric-properties") ? [{key:"width_mm",name_ar:"?????",name_en:"Width"}] : path.startsWith("/masterdata/") ? [] : parameters));  // no products defined yet: the product type is typed
    ui(<SpecificationForm />);
    changeControl(await screen.findByLabelText("Specification no."), { target: { value: "ROF-TDS-PP-001" } });
    changeControl(screen.getByLabelText("Title"), { target: { value: "PP strap" } });
    // ProductSelect first renders a disabled loading select; wait for its editable no-catalog input.
    changeControl(await screen.findByRole("textbox", { name: "Product" }), { target: { value: "PP strap" } });
    fireEvent.click(screen.getByRole("button", { name: "Add all parameters" }));
    changeControl(screen.getByLabelText("Target from"), { target: { value: "order_line" } });
    changeControl(screen.getByLabelText("Order line key"), { target: { value: "width_mm" } });
    changeControl(screen.getByLabelText("Tolerance below (−)"), { target: { value: "0.2" } });
    changeControl(screen.getByLabelText("Tolerance above (+)"), { target: { value: "0.2" } });
    changeControl(screen.getByLabelText("Requirement (English)"), { target: { value: "As approved sample" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Save draft" })); });
    const body = api.apiClient.mock.calls.find(([p, o]) => p === "/quality/quality-specifications" && o?.method === "POST")?.[1]?.body;
    expect(body).toMatchObject({ code: "ROF-TDS-PP-001", product_type: "PP strap", lines: [
      { parameter_id: "p1", target_source: "order_line", order_spec_key: "width_mm", tolerance_minus: "0.2", tolerance_plus: "0.2", requirement_ar:null,requirement_en: null },
      { parameter_id: "p2", target_source: "none", requirement_ar:null,requirement_en: "As approved sample", tolerance_minus: null } ] });
    expect(nav.push).toHaveBeenCalledWith("/quality-specifications/s1");
  });
});

describe("copy specification",()=>{
  it("keeps the dialog and entered title on failure, then opens the independent draft after saving",async()=>{
    nav.push.mockReset();
    const close=vi.fn();let fail=true;
    api.apiClient.mockImplementation((path:string,o?:{method?:string})=>{
      if(o?.method==="POST")return fail?Promise.reject(new ApiClientError("Duplicate",409,{code:"SPECIFICATION_CODE_TAKEN"})):Promise.resolve({id:"copy-id"});
      return Promise.resolve([]);
    });
    ui(<CopySpecificationDialog source={{id:"source",code:"SPEC-1",title:"Film",revision:3,status:"superseded",product_type:"film",grade:"A",activated_at:null,activated_by_name:null,created_by_name:null,actions:["copy"],updated_at:"2026-11-25T00:00:00Z"}} onClose={close}/>);
    const dialog=screen.getByRole("dialog");
    const title=within(dialog).getByLabelText("Title");
    expect((title as HTMLInputElement).value).toBe("Film - Copy");
    fireEvent.change(title,{target:{value:"Independent film"}});
    await act(async()=>{fireEvent.submit(dialog.querySelector("form")??dialog);});
    await waitFor(()=>expect(screen.getByRole("alert")).toBeTruthy());
    expect(close).not.toHaveBeenCalled();expect(nav.push).not.toHaveBeenCalled();
    expect((title as HTMLInputElement).value).toBe("Independent film");
    fail=false;
    await act(async()=>{fireEvent.submit(dialog.querySelector("form")??dialog);});
    await waitFor(()=>expect(nav.push).toHaveBeenCalledWith("/quality-specifications/copy-id/edit"));
    expect(posted("/quality/quality-specifications/source/copy")).toMatchObject({code:"SPEC-1-COPY",title:"Independent film",product_type:"film",grade:"A"});
  });
  it("displays translated wording with fallback and uses the property name for an order target",()=>{
    expect(bilingualText({method_ar:"طريقة",method_en:"Method"},"method","ar")).toBe("طريقة");
    expect(bilingualText({method_ar:null,method_en:"Method"},"method","ar")).toBe("Method");
    expect(targetText({parameter_id:"p",target_source:"order_line",order_spec_key:"raw_key",order_spec_name_en:"Product mass"} as Parameters<typeof targetText>[0],(_key,values)=>`From order: ${values?.key}`,"en")).toBe("From order: Product mass");
  });
});

describe("plan for a lot without sizes", () => {
  it("offers other specifications and asks for the values the order line lacks", async () => {
    const plain = check({ actions: ["edit", "measure", "close", "cancel"] });
    api.apiClient.mockImplementation((path: string) => Promise.resolve(path.endsWith("/specifications")
      ? [{ id: "s1", code: "ROF-TDS-PP-001", revision: 1, title: "PP Strap 5 × 0.35", product_type: "pp_strap", grade: null, matches_product: false,
        missing_keys: ["thickness_mm", "width_mm"] }]
      : path.endsWith("/plan") ? { ...plain, specification_code: "ROF-TDS-PP-001", specification_revision: 1, lot_values: { width_mm: "5", thickness_mm: "0.35" },
        measurements: [measurement()] } : plain));
    ui(<QualityCheckDetail qualityCheckId="c1" />, "ar");
    expect(await screen.findByText(/وليست لمنتج الأمر/)).toBeTruthy();
    const apply = screen.getByRole("button", { name: "تطبيق خطة القياس" }) as HTMLButtonElement;
    expect(apply.disabled).toBe(true);
    changeControl(screen.getByLabelText("العرض (مم)"), { target: { value: "5" } });
    changeControl(screen.getByLabelText("السماكة (مم)"), { target: { value: "0.35" } });
    await act(async () => { fireEvent.click(apply); });
    expect(api.apiClient.mock.calls.find(([p]) => p === "/quality/quality-checks/c1/plan")?.[1]?.body)
      .toEqual({ specification_id: "s1", lot_values: { thickness_mm: "0.35", width_mm: "5" } });
    expect(await screen.findByText("قيم الدفعة التي أدخلها الفاحص: العرض (مم): 5 · السماكة (مم): 0.35")).toBeTruthy();
  });
});

describe("invalid readings", () => {
  it("flags a reading that is not a number and does not save", async () => {
    api.apiClient.mockResolvedValue(check({ actions: ["edit", "measure", "close", "cancel"], specification_code: "X", specification_revision: 1, measurements: [measurement()] }));
    ui(<QualityCheckDetail qualityCheckId="c1" />);
    changeControl(await screen.findByLabelText("Width reading 1"), { target: { value: "5 mm" } });
    expect(screen.getByText("Invalid reading: enter a number only (e.g. 5.02).")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Save measurements (1)" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Add a reading for Width" }));
    expect(screen.getByLabelText("Width reading 4")).toBeTruthy();
  });
});

// QUAL-RET-001: returned goods — the list awaiting quality, the inspection's source and containment, the split decision.
import { QualityReturnsList } from "@/features/quality-checks/components/QualityReturnsList";

const returnCheck = (over: Partial<QualityCheckData> = {}) => check({ check_type: "issue_triggered", qty_inspected: "18.000", unit: "roll",
  actions: ["edit", "measure", "return_decision", "cancel"], return_id: "ret1", return_line_id: "rl1",
  return_source: { return_id: "ret1", return_no: "RT-2026-0001", kind: "customer", reason: "quality_defect", responsibility: "factory",
    details: "Crushed cores", shipment_id: "s1", shipment_no: "DN-2026-0001", customer_name: "UCIC Company", line_no: 1,
    description: "PP Strap 5 mm", production_order_no: "PO-2026-000014" }, ...over });

describe("returned goods", () => {
  it("lists returns awaiting quality and opens an inspection for a returned item", async () => {
    api.apiClient.mockImplementation((path: string, o?: { method?: string }) => Promise.resolve(o?.method === "POST" ? returnCheck({ id: "c9" }) : [{
      return_id: "ret1", return_no: "RT-2026-0001", kind: "customer", reason: "quality_defect", responsibility: "factory", details: null,
      customer_name: "UCIC Company", received_at: "", shipment_id: "s1", shipment_no: "DN-2026-0001",
      lines: [{ line_id: "rl1", line_no: 1, description: "PP Strap 5 mm", width_mm: "5.000", thickness_mm: "0.350", unit: "roll",
        production_order_id: "po1", production_order_no: "PO-2026-000014", received_quantity: "18.000", inspection_id: null,
        inspection_code: null, inspection_status: null }] }]));
    ui(<QualityReturnsList />, "ar");
    fireEvent.click(await screen.findByRole("button", { name: "فتح الفحص" }));
    await act(async () => {});
    expect(api.apiClient.mock.calls.some(([p, o]) => p === "/quality/returns/lines/rl1/inspection" && o?.method === "POST")).toBe(true);
    expect(nav.push).toHaveBeenCalledWith("/quality-checks/c9");
  });

  it("shows where the goods came from, the batch's other notes, and splits the decision", async () => {
    api.apiClient.mockImplementation((path: string, o?: { method?: string }) => Promise.resolve(
      path.endsWith("/specifications") ? [] : path.endsWith("/batch-shipments") ? [
        { shipment_id: "s1", shipment_no: "DN-2026-0001", status: "delivered", shipment_date: "2026-10-04", customer_name: "UCIC Company", quantity: "100.000", delivered_quantity: "100.000", unit: "roll" },
        { shipment_id: "s3", shipment_no: "DN-2026-0003", status: "ready", shipment_date: "2026-10-05", customer_name: "Other Co", quantity: "30.000", delivered_quantity: null, unit: "roll" }]
        : o?.method === "POST" ? returnCheck({ status: "closed", result: "rejected", actions: [] }) : returnCheck()));
    ui(<QualityCheckDetail qualityCheckId="c1" />);
    expect(await screen.findByRole("link", { name: "RT-2026-0001" })).toBeTruthy();
    expect(await screen.findByText("Ready to leave from this batch: DN-2026-0003. Hold them until the decision.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Close inspection" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Decide on the returned goods" }));
    const dialog = screen.getByRole("dialog", { name: "Decision on the returned goods" });
    const confirm = within(dialog).getByRole("button", { name: "Record the decision" }) as HTMLButtonElement;
    changeControl(within(dialog).getByLabelText(/^Back to stock/), { target: { value: "8" } });
    changeControl(within(dialog).getByLabelText(/^Scrap/), { target: { value: "5" } });
    expect(within(dialog).getByText("Total 13 of 18")).toBeTruthy();
    expect(confirm.disabled).toBe(true);
    changeControl(within(dialog).getByLabelText(/^Rework/), { target: { value: "5" } });
    await act(async () => { fireEvent.click(confirm); });
    expect(posted("/quality/quality-checks/c1/return-decision")).toEqual({ to_stock: "8", use_as_is: "0", rework: "5", return_to_process: "0",
      scrap: "5", hold: "0", notes: null, concession_approved_by: null, open_ncr: true });
  });
});
