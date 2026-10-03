// QUAL-001: inspections close with balanced quantities, rejections need a final decision, and both keep a production order from closing.
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
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
import type { ProductionOrderData } from "@/features/production-orders/types";
import { Q, QUALITY_REPORT } from "@/lib/quality-permissions";
import { ReportForm } from "@/features/reports/ReportForm";
import { SpecificationForm } from "@/features/quality-specifications";
import { splitReadings } from "@/features/quality-checks/components/MeasurementsSection";
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

function check(over: Partial<QualityCheckData> = {}): QualityCheckData {
  return { id: "c1", inspection_code: "QI-2026-0001", check_type: "finished_product_inspection", status: "under_inspection", result: null,
    check_datetime: "2026-10-01T08:00:00Z", production_order_id: "po1", production_order_item_id: null, sample_id: null,
    qty_inspected: "100.000", qty_accepted: "0.000", qty_rejected: "0.000", unit: "kg", order_number: "PO-1", item_line_no: null, sample_code: null,
    checked_by_name: "Sara", actions: ["edit", "close", "cancel"], created_at: "", updated_at: "", notes: null, started_at: "2026-10-01T08:05:00Z",
    closed_at: null, closed_by_name: null, cancel_reason: null, history: [], rejections: [],
    specification_id: null, specification_code: null, specification_revision: null, measurements: [], ...over };
}
function rejection(over: Partial<QualityRejectionData> = {}): QualityRejectionData {
  return { id: "r1", rejection_code: "QR-2026-0001", quality_check_id: "c1", production_order_id: "po1", production_order_item_id: null,
    rejection_date: "2026-10-01", rejection_reason: "out_of_spec", disposition: null, disposition_status: "pending", quantity_rejected: "8.000", unit: "kg",
    order_number: "PO-1", item_line_no: null, inspection_code: "QI-2026-0001", unresolved: true, actions: ["edit", "decide"], created_at: "",
    quality_defect_id: null, rejection_notes: "Thickness below spec", rejected_by_name: "Sara", decision_notes: null, concession_approved_by: null,
    decided_at: null, decided_by_name: null, execution_notes: null, executed_at: null, executed_by_name: null, history: [], updated_at: "", ...over };
}

describe("quality checks", () => {
  it("lists checks with Arabic statuses, including cancelled", async () => {
    api.apiClient.mockResolvedValue([check({ status: "cancelled", actions: [] })]);
    ui(<QualityChecksList />, "ar");
    const table = await screen.findByRole("table", { name: "قائمة فحوصات الجودة" });
    expect(within(table).getAllByText("ملغى").length).toBeGreaterThan(0);
    expect(api.apiClient.mock.calls[0][0]).toBe("/quality/quality-checks");
  });

  it("closes with balanced quantities; a rejected quantity sends its reason", async () => {
    api.apiClient.mockImplementation((path: string, o?: { method?: string }) =>
      Promise.resolve(o?.method === "POST" ? check({ status: "closed", result: "rejected", qty_accepted: "92.000", qty_rejected: "8.000", actions: [] }) : check()));
    ui(<QualityCheckDetail qualityCheckId="c1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Close with result" }));
    const dialog = screen.getByRole("dialog", { name: "Close the check with its result" });
    fireEvent.change(within(dialog).getByLabelText("Result"), { target: { value: "accepted" } });
    // Accepted 92 of 100 leaves 8 rejected: an "accepted" result cannot carry it.
    fireEvent.change(within(dialog).getByLabelText(/^Accepted/), { target: { value: "92" } });
    expect(within(dialog).getByText("An accepted result cannot have a rejected quantity.")).toBeTruthy();
    expect((within(dialog).getByRole("button", { name: "Close with result" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(within(dialog).getByLabelText("Result"), { target: { value: "rejected" } });
    fireEvent.change(within(dialog).getByLabelText("Rejection reason"), { target: { value: "out_of_spec" } });
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
    fireEvent.change(within(dialog).getByLabelText("قرار التصرف"), { target: { value: "use_as_is" } });
    const save = within(dialog).getByRole("button", { name: "حفظ القرار" }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    fireEvent.change(within(dialog).getByLabelText("الموافق على الاستثناء"), { target: { value: "مدير الجودة" } });
    fireEvent.change(within(dialog).getByLabelText("مبرر الاستثناء"), { target: { value: "ضمن تفاوت مقبول لدى العميل" } });
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
    method: "Calibrated vernier caliper", requirement: null, acceptance: null, target: "5.0000", lower_limit: "4.8000", upper_limit: "5.2000",
    readings_required: 3, readings: null, attribute_result: null, observation: null, reading_count: 0, minimum: null, maximum: null, mean: null,
    status: "pending", measured_at: null, ...over };
}

describe("measurements", () => {
  it("splits readings typed with spaces, commas or Arabic separators", () => {
    expect(splitReadings("5.02, 4.98 ،5.01؛5")).toEqual(["5.02", "4.98", "5.01", "5"]);
  });

  it("records readings and shows the server's verdict with the limits", async () => {
    const planned = check({ specification_code: "ROF-TDS-PP-001", specification_revision: 1, actions: ["edit", "measure", "close", "cancel"],
      measurements: [measurement(), measurement({ id: "m2", parameter_code: "COLOR", name_ar: "اللون", name_en: "Color", kind: "attribute", unit: null,
        requirement: "As approved sample", acceptance: "Visual match required", target: null, lower_limit: null, upper_limit: null, readings_required: 1 })] });
    const measured = { ...planned, measurements: [measurement({ readings: ["5.02", "4.98", "5.01"], reading_count: 3, minimum: "4.98", maximum: "5.02",
      mean: "5.0033", status: "pass" }), planned.measurements[1]] };
    api.apiClient.mockImplementation((_path: string, o?: { method?: string }) => Promise.resolve(o?.method === "PUT" ? measured : planned));
    ui(<QualityCheckDetail qualityCheckId="c1" />, "ar");
    const section = await screen.findByRole("region", { name: "نتائج القياس" });
    expect(within(section).getByText("4.8 – 5.2")).toBeTruthy();
    expect(within(section).getByText("المواصفة المرجعية: ROF-TDS-PP-001 — rev 1")).toBeTruthy();
    fireEvent.change(within(section).getByLabelText("قراءات العرض"), { target: { value: "5.02 4.98, 5.01" } });
    await act(async () => { fireEvent.click(within(section).getAllByRole("button", { name: "حفظ" })[0]); });
    expect(api.apiClient.mock.calls.find(([p, o]) => p === "/quality/quality-checks/c1/measurements/m1" && o?.method === "PUT")?.[1]?.body)
      .toEqual({ readings: ["5.02", "4.98", "5.01"], observation: null });
    expect(await within(section).findByText("مطابق: 1 · غير مطابق: 0 · لم يُقَس: 1")).toBeTruthy();
  });

  it("will not close while the plan is not fully measured", async () => {
    api.apiClient.mockResolvedValue(check({ measurements: [measurement()] }));
    ui(<QualityCheckDetail qualityCheckId="c1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Close with result" }));
    const dialog = screen.getByRole("dialog", { name: "Close the check with its result" });
    fireEvent.change(within(dialog).getByLabelText("Result"), { target: { value: "accepted" } });
    expect(within(dialog).getByText("1 parameters of the plan are not measured yet.")).toBeTruthy();
    expect((within(dialog).getByRole("button", { name: "Close with result" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("offers the specifications in force when the inspection has no plan yet", async () => {
    const plain = check({ actions: ["edit", "measure", "close", "cancel"] });
    api.apiClient.mockImplementation((path: string) => Promise.resolve(path.endsWith("/specifications")
      ? [{ id: "s1", code: "ROF-TDS-PP-001", revision: 2, title: "PP strap", grade: null }]
      : path.endsWith("/plan") ? { ...plain, specification_code: "ROF-TDS-PP-001", specification_revision: 2, measurements: [measurement()] } : plain));
    ui(<QualityCheckDetail qualityCheckId="c1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Apply measurement plan" }));
    expect(await screen.findByText("Reference specification: ROF-TDS-PP-001 — rev 2")).toBeTruthy();
    expect(api.apiClient.mock.calls.some(([p, o]) => p === "/quality/quality-checks/c1/plan" && o?.body?.specification_id === "s1")).toBe(true);
  });
});

describe("specification form", () => {
  it("builds lines per parameter kind and sends a draft", async () => {
    const parameters = [
      { id: "p1", code: "WIDTH", name_ar: "العرض", name_en: "Width", kind: "numeric", unit: "mm", method: "Caliper", is_active: true, sort_order: 10 },
      { id: "p2", code: "COLOR", name_ar: "اللون", name_en: "Color", kind: "attribute", unit: null, method: "Visual", is_active: true, sort_order: 20 },
    ];
    api.apiClient.mockImplementation((path: string, o?: { method?: string }) => Promise.resolve(o?.method === "POST" ? { id: "s1" } : parameters));
    ui(<SpecificationForm />);
    fireEvent.change(await screen.findByLabelText("Specification no."), { target: { value: "ROF-TDS-PP-001" } });
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "PP strap" } });
    fireEvent.change(screen.getByLabelText("Product"), { target: { value: "PP strap" } });
    fireEvent.click(screen.getByRole("button", { name: "Add all parameters" }));
    fireEvent.change(screen.getByLabelText("Target from"), { target: { value: "order_line" } });
    fireEvent.change(screen.getByLabelText("Order line key"), { target: { value: "width_mm" } });
    fireEvent.change(screen.getByLabelText("Tolerance below (−)"), { target: { value: "0.2" } });
    fireEvent.change(screen.getByLabelText("Tolerance above (+)"), { target: { value: "0.2" } });
    fireEvent.change(screen.getByLabelText("Requirement"), { target: { value: "As approved sample" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Save draft" })); });
    const body = api.apiClient.mock.calls.find(([p, o]) => p === "/quality/quality-specifications" && o?.method === "POST")?.[1]?.body;
    expect(body).toMatchObject({ code: "ROF-TDS-PP-001", product_type: "PP strap", lines: [
      { parameter_id: "p1", target_source: "order_line", order_spec_key: "width_mm", tolerance_minus: "0.2", tolerance_plus: "0.2", requirement: null },
      { parameter_id: "p2", target_source: "none", requirement: "As approved sample", tolerance_minus: null } ] });
    expect(nav.push).toHaveBeenCalledWith("/quality-specifications/s1");
  });
});
