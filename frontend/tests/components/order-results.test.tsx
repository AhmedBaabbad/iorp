// PROD-OUTPUT-001: the final result section, its dialogs, and the close confirmation.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";
import type { OrderResult, ResultOriginal, ResultSummary } from "@/features/production-results/types";

const api = vi.hoisted(() => ({ apiClient: vi.fn() }));
const perms = vi.hoisted(() => ({ granted: new Set<string>() }));
vi.mock("@/lib/api-client", async importOriginal => ({ ...(await importOriginal<object>()), apiClient: api.apiClient }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/", useSearchParams: () => new URLSearchParams() }));
vi.mock("@/features/auth/permission-hooks", () => ({ usePermission: (code: string) => perms.granted.has(code) }));
vi.mock("@/hooks/useFormatter", () => ({ useFormatter: () => ({ date: (v: string) => v, dateTime: (v: string) => v, number: (v: string) => v, quantity: (v: string, u?: string) => `${v} ${u ?? ""}`.trim() }) }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) => <main><h1>{title}</h1>{action}{children}</main> }));
vi.mock("@/features/work-centers", () => ({ getWorkCenters: () => Promise.resolve([]) }));

import { OrderResultSection } from "@/features/production-results/components/OrderResultSection";
import { CloseResultDialog } from "@/features/production-results/components/CloseResultDialog";
import { ResultsList } from "@/features/production-results/components/ResultsList";

let en: Record<string, unknown>;
let ar: Record<string, unknown>;
beforeAll(async () => {
  en = await loadMessages("en") as Record<string, unknown>;
  ar = await loadMessages("ar") as Record<string, unknown>;
});
beforeEach(() => {
  api.apiClient.mockReset();
  perms.granted = new Set(["production:results:read", "production:results:create", "production:results:update", "production:results:delete", "production:results:correct"]);
});
afterEach(cleanup);
const ui = (node: ReactNode, locale: "en" | "ar" = "en") =>
  render(<NextIntlClientProvider locale={locale} messages={locale === "en" ? en : ar} timeZone="UTC">{node}</NextIntlClientProvider>);

function summary(over: Partial<ResultSummary> = {}): ResultSummary {
  return { customer_good: "300", stock_good: "50", good_total: "350", samples_total: "10", samples_loss: "10", scrap_total: "20", loss_total: "30",
    rework_total: "5", total_output: "385", planned_qty: "400", allocated_qty: "400", fulfillment_pct: "75.00", yield_pct: "90.91", loss_pct: "7.79",
    variance_qty: "-50", secondary_totals: [], ...over };
}
function entry(over: Partial<ResultOriginal> = {}): ResultOriginal {
  return { id: "e1", production_order_item_id: "i1", line_no: 1, disposition: "customer_good", quantity: "300", unit: "kg", secondary_quantity: null,
    secondary_unit: null, counts_as_loss: false, reason_code: null, notes: null, entry_type: "original", corrects_entry_id: null, correction_reason: null,
    created_by_user_id: "u1", created_by_name: "Sara", updated_by_user_id: null, created_at: "2026-09-30T08:00:00Z", updated_at: "2026-09-30T08:00:00Z",
    effective_quantity: "300", corrections: [], actions: ["edit", "delete"], ...over };
}
function view(over: Partial<OrderResult> = {}): OrderResult {
  return {
    order: { id: "po1", number: "PO-1", status: "completed", product_type: "film", unit: "kg" }, available: true, editable: true, locked: false,
    allocation_level: "item",
    items: [{ id: "i1", line_no: 1, unit: "kg", planned_quantity: "400", target_spec_json: { width_mm: 10 }, allocated_quantity: "400", summary: summary() }],
    totals: [{ unit: "kg", ...summary() }], entries: [entry()], close_check: { ready: true, has_entries: true, missing_item_ids: [] }, actions: ["create"], ...over,
  };
}
const respond = (handler: (path: string, options?: { method?: string; body?: unknown }) => unknown) =>
  api.apiClient.mockImplementation((path: string, options?: { method?: string; body?: unknown }) => Promise.resolve(handler(path, options)));
const posted = (suffix: string) => api.apiClient.mock.calls.find(([p, o]) => String(p).endsWith(suffix) && o?.method === "POST")?.[1]?.body;

describe("availability by order status", () => {
  it("shows only a hint before completion and nothing for a cancelled order", () => {
    const { rerender } = ui(<OrderResultSection order={{ id: "po1", status: "in_progress" }} />, "ar");
    expect(screen.getByText("تُسجَّل النتيجة بعد إكمال الأمر.")).toBeTruthy();
    expect(api.apiClient).not.toHaveBeenCalled();
    rerender(<NextIntlClientProvider locale="ar" messages={ar} timeZone="UTC"><OrderResultSection order={{ id: "po1", status: "cancelled" }} /></NextIntlClientProvider>);
    expect(screen.queryByText("النتيجة النهائية للإنتاج")).toBeNull();
  });

  it("is hidden without the read permission", () => {
    perms.granted = new Set();
    ui(<OrderResultSection order={{ id: "po1", status: "completed" }} />);
    expect(screen.queryByText("Final production result")).toBeNull();
  });
});

describe("completed order", () => {
  it("shows the summary cards and the entries with Arabic labels", async () => {
    respond(() => view());
    ui(<OrderResultSection order={{ id: "po1", status: "completed" }} />, "ar");
    const cards = await screen.findByLabelText("ملخص النتيجة بوحدة kg");
    for (const [label, value] of [["الكمية المخططة", "400 kg"], ["جيد للعملاء", "300 kg"], ["جيد للمخزون", "50 kg"], ["العينات", "10 kg"],
      ["الهالك", "20 kg"], ["إعادة التشغيل", "5 kg"], ["نسبة الإنجاز", "75.00%"], ["نسبة الهالك", "7.79%"]]) {
      expect(within(cards).getByText(label).nextElementSibling?.textContent).toBe(value);
    }
    const table = screen.getByRole("table", { name: "قيود النتيجة" });
    expect(within(table).getByText("التصنيف")).toBeTruthy();
    expect(within(table).getByText("Sara")).toBeTruthy();
    expect(within(table).getByRole("button", { name: "تعديل" })).toBeTruthy();
  });

  it("requires the sample loss choice and sends it", async () => {
    respond((path, o) => (o?.method === "POST" ? view() : view()));
    ui(<OrderResultSection order={{ id: "po1", status: "completed" }} />);
    fireEvent.click(await screen.findByRole("button", { name: "Add entry" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Disposition"), { target: { value: "sample" } });
    fireEvent.change(within(dialog).getByLabelText("Quantity (kg)"), { target: { value: "4" } });
    const save = within(dialog).getByRole("button", { name: "Save" }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    fireEvent.click(within(dialog).getByLabelText(/intentional sample/));
    expect(save.disabled).toBe(false);
    fireEvent.click(save);
    await waitFor(() => expect(posted("/result/entries")).toMatchObject({ disposition: "sample", quantity: "4", counts_as_loss: false, production_order_item_id: "i1" }));
  });

  it("shows the customer allocation and warns above it", async () => {
    respond(() => view());
    ui(<OrderResultSection order={{ id: "po1", status: "completed" }} />);
    fireEvent.click(await screen.findByRole("button", { name: "Add entry" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Disposition"), { target: { value: "customer_good" } });
    expect(within(dialog).getByRole("status").textContent).toBe("Allocated to customers: 400 kg · already recorded: 300 · remaining: 100");
    fireEvent.change(within(dialog).getByLabelText("Quantity (kg)"), { target: { value: "120" } });
    expect(within(dialog).getByRole("status").textContent).toContain("only 100 kg remain of 400");
  });

  it("shows the server's rejection with its figures", async () => {
    const { ApiClientError } = await import("@/lib/api-client");
    api.apiClient.mockImplementation((_p: string, o?: { method?: string }) => o?.method === "POST"
      ? Promise.reject(new ApiClientError("x", 422, { detail: { code: "CUSTOMER_GOOD_EXCEEDS_ALLOCATION", allocated_quantity: "400.000", excess_quantity: "20.000" } }))
      : Promise.resolve(view()));
    ui(<OrderResultSection order={{ id: "po1", status: "completed" }} />, "ar");
    fireEvent.click(await screen.findByRole("button", { name: "إضافة قيد" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("الكمية (kg)"), { target: { value: "5" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "حفظ" }));
    expect((await within(dialog).findByRole("alert")).textContent).toBe("«جيد للعملاء» يتجاوز المخصص 400.000 بمقدار 20.000. سجّل الزيادة «جيد للمخزون».");
  });
});

describe("closed order", () => {
  const closed = () => view({
    order: { id: "po1", number: "PO-1", status: "closed", product_type: "film", unit: "kg" }, editable: false, locked: true, actions: [],
    entries: [entry({ actions: ["correct"], effective_quantity: "290",
      corrections: [{ ...entry({ id: "c1", entry_type: "correction", quantity: "-10", corrects_entry_id: "e1", correction_reason: "Returned roll" }) }] })],
  });

  it("is read-only, shows corrections under the original, and posts a signed correction with a reason", async () => {
    respond(() => closed());
    ui(<OrderResultSection order={{ id: "po1", status: "closed" }} />);
    await screen.findByText(/its result is locked/);
    expect(screen.queryByRole("button", { name: "Add entry" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Edit" })).toBeNull();
    expect(screen.getByText("Returned roll")).toBeTruthy();
    expect(screen.getByText("Effective quantity after corrections: 290 kg")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Correct" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Change (kg)"), { target: { value: "-300" } });
    expect(within(dialog).getByRole("status").textContent).toContain("negative");
    fireEvent.change(within(dialog).getByLabelText("Change (kg)"), { target: { value: "-5" } });
    const submit = within(dialog).getByRole("button", { name: "Correct" }) as HTMLButtonElement;
    expect(submit.disabled).toBe(true);  // reason still missing
    fireEvent.change(within(dialog).getByLabelText("Correction reason"), { target: { value: "Scale drift" } });
    fireEvent.click(submit);
    await waitFor(() => expect(posted("/entries/e1/corrections")).toEqual({ quantity: "-5", secondary_quantity: null, correction_reason: "Scale drift" }));
  });
});

describe("close confirmation", () => {
  it("shows the summary and variance, then closes", async () => {
    respond(() => view());
    const onConfirm = vi.fn();
    ui(<CloseResultDialog orderId="po1" orderNumber="PO-1" busy={false} error="" onConfirm={onConfirm} onClose={() => {}} />);
    await screen.findByLabelText("Result summary in kg");
    expect(screen.getByText(/Variance against plan/).parentElement?.textContent).toContain("-50 kg");
    fireEvent.click(screen.getByRole("button", { name: "Close order" }));
    expect(onConfirm).toHaveBeenCalledWith({ reason: undefined, zeroOutput: false });
  });

  it("offers zero output with a mandatory reason when nothing was recorded", async () => {
    respond(() => view({ entries: [], close_check: { ready: false, has_entries: false, missing_item_ids: [] } }));
    const onConfirm = vi.fn();
    ui(<CloseResultDialog orderId="po1" orderNumber="PO-1" busy={false} error="" onConfirm={onConfirm} onClose={() => {}} />);
    expect(await screen.findByText("This order has no result entries.")).toBeTruthy();
    const confirm = screen.getByRole("button", { name: "Close order" }) as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);
    fireEvent.click(screen.getByLabelText(/zero output/));
    expect(confirm.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Why was nothing produced?"), { target: { value: "Material never arrived" } });
    fireEvent.click(confirm);
    expect(onConfirm).toHaveBeenCalledWith({ reason: "Material never arrived", zeroOutput: true });
  });

  it("names the items still missing a result", async () => {
    respond(() => view({ items: [...view().items, { ...view().items[0], id: "i2", line_no: 2 }], close_check: { ready: false, has_entries: true, missing_item_ids: ["i2"] } }));
    ui(<CloseResultDialog orderId="po1" orderNumber="PO-1" busy={false} error="" onConfirm={() => {}} onClose={() => {}} />);
    expect(await screen.findByText("These items have no result entries yet: 2.")).toBeTruthy();
    expect(screen.queryByLabelText(/zero output/)).toBeNull();
  });
});

describe("results screen", () => {
  it("lists completed and closed orders with their totals, in Arabic, linking to each order's result", async () => {
    respond(() => [
      { id: "po1", number: "PO-1", status: "completed", product_type: "film", entry_count: 2, correction_count: 0, ready_to_close: true, totals: [{ unit: "kg", ...summary() }] },
      { id: "po2", number: "PO-2", status: "closed", product_type: "film", entry_count: 1, correction_count: 1, ready_to_close: false, totals: [{ unit: "kg", ...summary({ customer_good: "90" }) }] },
    ]);
    ui(<ResultsList />, "ar");
    const table = await screen.findByRole("table", { name: "المخرجات الإنتاجية" });
    expect(within(table).getByText("PO-1")).toBeTruthy();
    expect(within(table).getByText("جاهز للإغلاق")).toBeTruthy();
    expect(within(table).getByRole("link", { name: "تسجيل النتيجة" }).getAttribute("href")).toBe("/production-orders/po1#result");
    expect(within(table).getByRole("link", { name: "عرض النتيجة" }).getAttribute("href")).toBe("/production-orders/po2#result");
    expect(within(table).getByText("90")).toBeTruthy();
    expect(screen.queryByRole("link", { name: "السجلات السابقة" })).toBeNull();  // the legacy design is gone
    fireEvent.change(screen.getByLabelText("حالة الأمر"), { target: { value: "closed" } });
    await waitFor(() => expect(api.apiClient).toHaveBeenLastCalledWith("/production/production-results?status=closed"));
  });

  it("explains what to do when nothing is completed yet", async () => {
    respond(() => []);
    ui(<ResultsList />);
    expect(await screen.findByText("No completed or closed orders yet")).toBeTruthy();
  });
});
