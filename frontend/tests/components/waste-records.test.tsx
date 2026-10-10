// PROD-WASTE-001: waste records tied to a production order, optionally a run; Arabic labels use «هالك».
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";
import { ApiClientError } from "@/lib/api-client";
import type { WasteRecordData, WasteSummary } from "@/features/waste-records/types";

const api = vi.hoisted(() => ({ apiClient: vi.fn() }));
const nav = vi.hoisted(() => ({ push: vi.fn(), params: new URLSearchParams() }));
const perms = vi.hoisted(() => ({ granted: new Set<string>() }));
vi.mock("@/lib/api-client", async importOriginal => ({ ...(await importOriginal<object>()), apiClient: api.apiClient }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: nav.push, replace: vi.fn() }), usePathname: () => "/", useSearchParams: () => nav.params }));
vi.mock("@/features/auth/permission-hooks", () => ({ usePermission: (code: string) => perms.granted.has(code) }));
vi.mock("@/hooks/useFormatter", () => ({ useFormatter: () => ({ date: (v: string) => v, dateTime: (v: string) => v, number: (v: string) => v, quantity: (v: string, u?: string) => `${v} ${u ?? ""}`.trim() }) }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) => <main><h1>{title}</h1>{action}{children}</main> }));
vi.mock("@/features/work-centers", () => ({ getWorkCenters: () => Promise.resolve([{ id: "wc1", code: "EX1", name: "Extruder 1" }, { id: "wc2", code: "EX2", name: "Extruder 2" }]) }));

import { OrderWasteSection } from "@/features/waste-records/components/OrderWasteSection";
import { WasteRecordDetail } from "@/features/waste-records/components/WasteRecordDetail";
import { WasteRecordForm } from "@/features/waste-records/components/WasteRecordForm";
import { WasteRecordsList } from "@/features/waste-records/components/WasteRecordsList";

let en: Record<string, unknown>;
let ar: Record<string, unknown>;
beforeAll(async () => {
  en = await loadMessages("en") as Record<string, unknown>;
  ar = await loadMessages("ar") as Record<string, unknown>;
});
beforeEach(() => {
  api.apiClient.mockReset();
  nav.push.mockReset();
  nav.params = new URLSearchParams();
  perms.granted = new Set(["production:waste_records:read", "production:waste_records:create", "production:waste_records:update", "production:waste_records:delete", "production:runs:read"]);
});
afterEach(cleanup);
const ui = (node: ReactNode, locale: "en" | "ar" = "en") =>
  render(<NextIntlClientProvider locale={locale} messages={locale === "en" ? en : ar} timeZone="UTC">{node}</NextIntlClientProvider>);
const respond = (handler: (path: string, options?: { method?: string; body?: unknown }) => unknown) =>
  api.apiClient.mockImplementation((path: string, options?: { method?: string; body?: unknown }) => {
    try { return Promise.resolve(handler(path, options)); } catch (e) { return Promise.reject(e); }
  });
const posted = (path: string) => api.apiClient.mock.calls.find(([p, o]) => p === path && o?.method === "POST")?.[1]?.body;

function record(over: Partial<WasteRecordData> = {}): WasteRecordData {
  return { id: "w1", organization_id: "o", production_order_id: "po1", production_order_item_id: null, production_run_id: null, work_center_id: "wc1",
    waste_date: "2026-10-01", quantity_wasted: "12.5", unit: "kg", categories: [{ category: "startup_setup", quantity: "12.5" }], reason_code: "WARM-UP", created_by_user_id: "u",
    updated_by_user_id: null, created_at: "2026-10-01T08:00:00Z", updated_at: "2026-10-01T08:00:00Z", notes: null,
    labels: { order_number: "PO-1", order_status: "in_progress", line_no: null, work_center_name: "Extruder 1", run_date: null, created_by_name: "Sara", actions: ["edit", "delete"] },
    ...over };
}
const order = { id: "po1", production_order_number: "PO-1", product_type: "film", status: "in_progress", unit: "kg", work_center_id: "wc1",
  lines: [{ id: "l1", line_no: 1, target_spec_json: null, planned_quantity: "400", unit: "kg", allocation_ids: [] }], allocations: [] };

describe("waste list", () => {
  it("shows records with Arabic waste types named «هالك»", async () => {
    respond(path => (path.startsWith("/production/waste-records") ? [record()] : []));
    ui(<WasteRecordsList />, "ar");
    const table = await screen.findByRole("table", { name: "قائمة سجلات الهدر" });
    expect(within(table).getByText("هالك بدء التشغيل والضبط")).toBeTruthy();
    expect(within(table).getByRole("link", { name: "PO-1" }).getAttribute("href")).toBe("/production-orders/po1");
    const types = Array.from((screen.getByLabelText("نوع الهدر") as HTMLSelectElement).options).map(o => o.textContent);
    expect(types.slice(1)).toEqual(["هالك بدء التشغيل والضبط", "هالك تغيير المنتج", "هالك العملية (قص وحواف)", "هالك عيب المادة الخام",
      "هالك عطل الماكينة", "هالك المناولة والكسر", "هالك التلوث", "هالك آخر"]);
    expect(types.some(t => t?.includes("خسارة"))).toBe(false);
  });
});

describe("recording waste", () => {
  beforeEach(() => { respond((path, o) => {
    if (path === "/production/waste-records" && o?.method === "POST") return record({ id: "new1" });
    if (path === "/production/production-orders") return [order, { ...order, id: "po2", production_order_number: "PO-2", status: "draft" }, { ...order, id: "po3", production_order_number: "PO-3", status: "closed" }];
    if (path === "/production/production-orders/po1") return order;
    if (path.startsWith("/production/runs")) return [{ id: "r1", run_date: "2026-10-01", status: "in_progress", work_center_id: "wc2" }, { id: "r2", run_date: "2026-10-02", status: "cancelled", work_center_id: "wc1" }];
    return [];
  }); });

  it("offers only running orders and requires the order", async () => {
    ui(<WasteRecordForm />);
    const select = await screen.findByLabelText("Production order");
    await waitFor(() => expect((select as HTMLSelectElement).options.length).toBe(2));
    expect(Array.from((select as HTMLSelectElement).options).map(o => o.textContent)).toEqual(["Select a production order", "PO-1 — film"]);
    expect((screen.getByRole("button", { name: "Record waste" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("uses the run's work center and posts the record", async () => {
    nav.params = new URLSearchParams("order=po1");
    ui(<WasteRecordForm />);
    const run = await screen.findByLabelText("Production run (optional)");
    await waitFor(() => expect((run as HTMLSelectElement).options.length).toBe(2));  // the cancelled run is not offered
    fireEvent.change(run, { target: { value: "r1" } });
    const center = screen.getByLabelText("Work center") as HTMLSelectElement;
    expect(center.disabled).toBe(true);
    expect(center.value).toBe("wc2");
    // One type alone takes the whole quantity.
    fireEvent.click(screen.getByRole("checkbox", { name: "Process waste (trim, edges)" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Changeover waste" }));
    expect(screen.getByText(/Material lost when changing product, colour, die or mould./)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Quantity wasted"), { target: { value: "8.25" } });
    fireEvent.click(screen.getByRole("button", { name: "Record waste" }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/waste-records/new1"));
    expect(posted("/production/waste-records")).toMatchObject({ production_order_id: "po1", production_run_id: "r1", work_center_id: null,
      categories: [{ category: "changeover" }], quantity_wasted: "8.25", unit: "kg" });
  });

  it("splits the quantity across several types and only saves when the shares add up", async () => {
    nav.params = new URLSearchParams("order=po1");
    ui(<WasteRecordForm />);
    fireEvent.change(await screen.findByLabelText("Quantity wasted"), { target: { value: "10" } });
    fireEvent.click(screen.getByRole("checkbox", { name: "Changeover waste" }));
    const save = screen.getByRole("button", { name: "Record waste" }) as HTMLButtonElement;
    fireEvent.change(screen.getByRole("spinbutton", { name: "Quantity Process waste (trim, edges)" }), { target: { value: "6" } });
    fireEvent.change(screen.getByRole("spinbutton", { name: "Quantity Changeover waste" }), { target: { value: "3" } });
    expect(screen.getByText("Shares: 9 of 10 — remaining 1")).toBeTruthy();
    expect(save.disabled).toBe(true);
    fireEvent.change(screen.getByRole("spinbutton", { name: "Quantity Changeover waste" }), { target: { value: "4" } });
    expect(save.disabled).toBe(false);
    fireEvent.click(save);
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/waste-records/new1"));
    expect(posted("/production/waste-records")).toMatchObject({ categories: [{ category: "process", quantity: "6" }, { category: "changeover", quantity: "4" }] });
  });

  it("explains a closed order in Arabic", async () => {
    respond((path, o) => {
      if (o?.method === "POST") throw new ApiClientError("locked", 409, { detail: { code: "WASTE_LOCKED", order_status: "closed" } });
      if (path === "/production/production-orders") return [order];
      if (path === "/production/production-orders/po1") return order;
      return [];
    });
    nav.params = new URLSearchParams("order=po1");
    ui(<WasteRecordForm />, "ar");
    fireEvent.change(await screen.findByLabelText("الكمية المهدرة"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "تسجيل هدر" }));
    expect((await screen.findByRole("alert")).textContent).toBe("الأمر مغلق، فلا يمكن تغيير سجلات الهدر الخاصة به.");
  });
});

describe("waste categories in the list and detail", () => {
  it("shows every category of a record as a chip, and each share on the detail", async () => {
    const mixed = record({ categories: [{ category: "changeover", quantity: "8" }, { category: "process", quantity: "4.5" }], quantity_wasted: "12.5" });
    respond(path => (path.startsWith("/production/waste-records/w1") ? mixed : path.startsWith("/production/waste-records") ? [mixed] : []));
    ui(<WasteRecordsList />);
    const table = await screen.findByRole("table", { name: "Waste records list" });
    expect(within(table).getByText("Changeover waste")).toBeTruthy();
    expect(within(table).getByText("Process waste (trim, edges)")).toBeTruthy();
    cleanup();
    ui(<WasteRecordDetail recordId="w1" />);
    const list = await screen.findByRole("list", { name: "Waste types" });
    expect(within(list).getByText("8 kg")).toBeTruthy();
    expect(within(list).getByText("4.5 kg")).toBeTruthy();
  });
});

describe("waste unit from the central list", () => {
  it("offers the unit list and makes a record awaiting review choose a unit before saving", async () => {
    respond((path, o) => {
      if (path === "/production/waste-records/w1" && o?.method === "PATCH") return record();
      if (path === "/production/waste-records/w1") return record({ unit: "بالة", legacy_unit_text: "بالة", unit_needs_review: true });
      if (path === "/production/production-orders/po1") return order;
      return [];
    });
    ui(<WasteRecordForm recordId="w1" />);
    const unit = await screen.findByRole("combobox", { name: "Unit" }) as HTMLSelectElement;
    expect(await screen.findByText(/written as “بالة”/)).toBeTruthy();
    expect(unit.value).toBe("");
    expect(Array.from(unit.options).some(o => o.value === "roll")).toBe(true);
    expect((screen.getByRole("button", { name: "Save changes" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(unit, { target: { value: "roll" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(api.apiClient.mock.calls.some(([p, o]) => p === "/production/waste-records/w1" && o?.method === "PATCH")).toBe(true));
    const body = api.apiClient.mock.calls.find(([p, o]) => p === "/production/waste-records/w1" && o?.method === "PATCH")![1].body;
    expect(body.unit).toBe("roll");
  });

  it("marks records awaiting a unit review in the list and prints known units as symbols", async () => {
    respond(path => (path.startsWith("/production/waste-records") ? [record({ id: "w2", unit: "بالة", legacy_unit_text: "بالة", unit_needs_review: true }), record()] : []));
    ui(<WasteRecordsList />, "ar");
    const table = await screen.findByRole("table", { name: "قائمة سجلات الهدر" });
    expect(within(table).getByText("وحدة تحتاج مراجعة")).toBeTruthy();
    expect(within(table).getByText("12.5 كجم")).toBeTruthy();
  });
});

describe("waste detail", () => {
  it("shows the actions the server allows and deletes after confirmation", async () => {
    respond((path, o) => (o?.method === "DELETE" ? undefined : record()));
    ui(<WasteRecordDetail recordId="w1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/waste-records?order=po1"));
  });

  it("is read-only when the order is closed", async () => {
    respond(() => record({ labels: { ...record().labels!, order_status: "closed", actions: [] } }));
    ui(<WasteRecordDetail recordId="w1" />);
    expect(await screen.findByText(/The order is closed/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Delete" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Edit" })).toBeNull();
  });
});

describe("waste on the order page", () => {
  const summary: WasteSummary = { order: { id: "po1", number: "PO-1", status: "in_progress", unit: "kg" }, available: true, locked: false,
    totals: [{ unit: "kg", quantity: "18.5", count: 3 }], by_category: [{ category: "process", unit: "kg", quantity: "15.5", count: 2 }, { category: "startup_setup", unit: "kg", quantity: "3", count: 1 }],
    actions: ["create"] };

  it("shows totals by type apart from the result, with a record link", async () => {
    respond(() => summary);
    ui(<OrderWasteSection order={{ id: "po1", status: "in_progress" }} />, "ar");
    // Units are codes, printed in the screen's language (UNIT-SYM-001): kg -> كجم.
    expect(await screen.findByText("18.5 كجم")).toBeTruthy();
    expect(screen.getByText("هالك العملية (قص وحواف)")).toBeTruthy();
    expect(screen.getByRole("link", { name: "تسجيل هدر" }).getAttribute("href")).toBe("/waste-records/new?order=po1");
    expect(screen.getByText(/لا تُضاف إلى هالكها/)).toBeTruthy();
  });

  it("stays hidden before production starts", () => {
    ui(<OrderWasteSection order={{ id: "po1", status: "released" }} />);
    expect(screen.queryByText("Operational waste")).toBeNull();
    expect(api.apiClient).not.toHaveBeenCalled();
  });
});
