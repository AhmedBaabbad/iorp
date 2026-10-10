// PROC-003: purchase orders — written in riyals with VAT or in dollars without, approved, and received against.
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";
import type { Material, OpenOrder, Order } from "@/features/procurement/types";

const api = vi.hoisted(() => ({ apiClient: vi.fn() }));
const nav = vi.hoisted(() => ({ push: vi.fn() }));
const perms = vi.hoisted(() => ({ granted: new Set<string>() }));
vi.mock("@/lib/api-client", async importOriginal => ({ ...(await importOriginal<object>()), apiClient: api.apiClient }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: nav.push, replace: vi.fn() }), usePathname: () => "/", useSearchParams: () => new URLSearchParams() }));
vi.mock("@/features/auth/permission-hooks", () => ({ usePermission: (code: string) => perms.granted.has(code),
  useHasAnyPermission: (codes: string[]) => codes.some(code => perms.granted.has(code)) }));
vi.mock("@/hooks/useFormatter", () => ({ useFormatter: () => ({ date: (v: string) => v, dateTime: (v: string) => v, number: (v: string) => v,
  decimal: (v: string | number, places = 2) => Number(v).toFixed(places), quantity: (v: string, u?: string) => `${Number(v)} ${u ?? ""}`.trim() }) }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) => <main><h1>{title}</h1>{action}{children}</main> }));

import { OrderDetail, OrderForm } from "@/features/procurement/components/PurchaseOrders";
import { ReceiptForm } from "@/features/procurement/components/Receipts";
import { PR } from "@/lib/procurement-permissions";

let en: Record<string, unknown>;
let ar: Record<string, unknown>;
beforeAll(async () => { en = await loadMessages("en") as Record<string, unknown>; ar = await loadMessages("ar") as Record<string, unknown>; });
beforeEach(() => { api.apiClient.mockReset(); nav.push.mockReset(); perms.granted = new Set(Object.values(PR)); });
afterEach(cleanup);
const ui = (node: ReactNode, locale: "en" | "ar" = "en") =>
  render(<NextIntlClientProvider locale={locale} messages={locale === "en" ? en : ar} timeZone="UTC">{node}</NextIntlClientProvider>);
const sent = (path: string, method: string) => api.apiClient.mock.calls.find(([p, o]) => p === path && o?.method === method)?.[1]?.body;

const material: Material = { id: "m1", material_code: "MAT-0001", name: "PP homopolymer H030", category: "resin", unit: "kg", inspection_required: true,
  spec_product_type: "pp_resin", active: true, notes: null };
const supplierOption = { id: "s1", supplier_code: "SUP-0001", name: "Gulf Polymers", status: "approved" };
const order = (over: Partial<Order> = {}): Order => ({ id: "o1", po_number: "PO-2026-0001", status: "approved", order_date: "2026-10-05", required_date: "2026-10-20",
  supplier_id: "s1", supplier_name: "Gulf Polymers", supplier_status: "approved", supplier_quote_ref: "Q-GP-118", subject: "PP resin for October", currency: "SAR",
  tax_rate: "15.00", total_amount: "126500.00", line_count: 1, received_pct: "40.0", actions: ["send", "receive", "close", "cancel"], created_at: "",
  attention: "Omar", payment_terms: "net_30", payment_terms_note: null, incoterm: null, delivery_place: "Factory", notes: null, subtotal_amount: "110000.00",
  discount_amount: "0.00", tax_amount: "16500.00", approved_at: "2026-10-05T10:00:00Z", approved_by_name: "Sara", sent_at: null, sent_by_name: null, closed_at: null,
  close_reason: null, cancel_reason: null, created_by_name: "Sara", updated_at: "",
  lines: [{ id: "l1", line_no: 1, material_id: "m1", description: "PP homopolymer H030", notes: "MFI 3", quantity: "20000.000", unit: "kg", unit_price: "5.5000",
    line_total: "110000.00" }],
  line_received: { l1: { received: "8000.000", remaining: "12000.000" } }, receipts: [{ id: "r1", receipt_no: "GRN-2026-0001", receipt_date: "2026-10-06", status: "received" }],
  history: [], ...over });

function answer(path: string, o?: { method?: string }) {
  if (o?.method) return Promise.resolve(order({ status: "draft" }));
  if (path.startsWith("/procurement/materials")) return Promise.resolve([material]);
  if (path.startsWith("/procurement/suppliers/lookup")) return Promise.resolve([supplierOption]);
  return Promise.resolve([]);
}

describe("purchase order form", () => {
  it("writes a local order in riyals with 15% VAT", async () => {
    api.apiClient.mockImplementation(answer);
    ui(<OrderForm supplierId="s1" />);
    await screen.findByRole("option", { name: "Gulf Polymers — SUP-0001" });
    await screen.findByRole("option", { name: "PP homopolymer H030 — MAT-0001" });
    expect((screen.getByLabelText("Apply VAT (15%)") as HTMLInputElement).checked).toBe(true);
    fireEvent.change(screen.getByLabelText("Material"), { target: { value: "m1" } });
    expect((screen.getByLabelText("Description") as HTMLInputElement).value).toBe("PP homopolymer H030");
    fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "20000" } });
    fireEvent.change(screen.getByLabelText("Unit price (SAR)"), { target: { value: "5.425" } });
    const totals = screen.getByRole("region", { name: "Totals" });
    expect(within(totals).getByText("Total including VAT").parentElement!.textContent).toContain("124775.00");  // 108,500 + 15%
    expect(within(totals).getAllByRole("img", { name: "Saudi Riyal" }).length).toBeGreaterThan(0);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Save draft" })); });
    expect(sent("/procurement/purchase-orders", "POST")).toMatchObject({ supplier_id: "s1", currency: "SAR", tax_rate: 15, discount_amount: "0",
      lines: [{ material_id: "m1", description: "PP homopolymer H030", quantity: "20000", unit: "kg", unit_price: "5.425", notes: null }] });
    expect(nav.push).toHaveBeenCalledWith("/purchase-orders/o1");
  });

  it("an import in dollars has no VAT unless chosen", async () => {
    api.apiClient.mockImplementation(answer);
    ui(<OrderForm supplierId="s1" />);
    await screen.findByRole("option", { name: "Gulf Polymers — SUP-0001" });
    fireEvent.change(screen.getByLabelText("Currency"), { target: { value: "USD" } });
    expect((screen.getByLabelText("Apply VAT (15%)") as HTMLInputElement).checked).toBe(false);
    expect(screen.getByText(/an import from abroad/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "LLDPE 218W" } });
    fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "24" } });
    fireEvent.change(screen.getByLabelText("Unit"), { target: { value: "ton" } });
    fireEvent.change(screen.getByLabelText("Unit price (USD)"), { target: { value: "1180" } });
    fireEvent.change(screen.getByLabelText("Delivery terms (Incoterms)"), { target: { value: "CIF" } });
    const totals = screen.getByRole("region", { name: "Totals" });
    expect(within(totals).getByText("Total").parentElement!.textContent).toBe("Total$ 28320.00");
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Save draft" })); });
    expect(sent("/procurement/purchase-orders", "POST")).toMatchObject({ currency: "USD", tax_rate: 0, incoterm: "CIF",
      lines: [{ description: "LLDPE 218W", quantity: "24", unit: "ton", unit_price: "1180" }] });
  });
});

describe("purchase order detail", () => {
  it("shows what has arrived and opens a receipt against the order", async () => {
    api.apiClient.mockResolvedValue(order());
    ui(<OrderDetail orderId="o1" />, "ar");
    expect((await screen.findByRole("link", { name: "استلام المواد" })).getAttribute("href")).toBe("/goods-receipts/new?supplier=s1&order=o1");
    expect(screen.getByText("المستلم 40%")).toBeTruthy();
    expect(screen.getByText("12000 كجم")).toBeTruthy();
    expect(screen.getByText("الإجمالي شامل الضريبة")).toBeTruthy();
    expect(screen.getByRole("link", { name: "GRN-2026-0001" }).getAttribute("href")).toBe("/goods-receipts/r1");
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "تسجيل الإرسال للمورد" })); });
    expect(api.apiClient).toHaveBeenCalledWith("/procurement/purchase-orders/o1/send", { method: "POST", body: undefined });
  });

  it("closes an order only with a reason", async () => {
    api.apiClient.mockResolvedValue(order({ status: "partially_received", actions: ["receive", "close"] }));
    ui(<OrderDetail orderId="o1" />);
    expect(screen.queryByRole("button", { name: "Cancel order" })).toBeNull();
    fireEvent.click(await screen.findByRole("button", { name: "Close order" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByRole("textbox"), { target: { value: "The supplier cannot deliver the rest" } });
    await act(async () => { fireEvent.click(within(dialog).getByRole("button", { name: "Close order" })); });
    expect(sent("/procurement/purchase-orders/o1/close", "POST")).toEqual({ reason: "The supplier cannot deliver the rest" });
  });
});

describe("goods receipt against a purchase order", () => {
  it("fills the lines with what the order still expects", async () => {
    const open: OpenOrder[] = [{ id: "o1", po_number: "PO-2026-0001", order_date: "2026-10-05", status: "sent",
      lines: [{ id: "l1", line_no: 1, material_id: "m1", description: "PP homopolymer H030", unit: "kg", quantity: "20000.000", remaining: "12000.000" },
        { id: "l2", line_no: 2, material_id: null, description: "Pallets", unit: "pallet", quantity: "10.000", remaining: "0.000" }] }];
    api.apiClient.mockImplementation((path: string, o?: { method?: string }) => path.startsWith("/procurement/purchase-orders/open-for-receipt")
      ? Promise.resolve(open) : o?.method ? Promise.resolve({ id: "r9" }) : answer(path));
    ui(<ReceiptForm supplierId="s1" orderId="o1" />);
    expect(await screen.findByDisplayValue("12000")).toBeTruthy();
    expect(screen.getByText(/order line 1/)).toBeTruthy();
    expect(screen.queryByLabelText("Purchase reference")).toBeNull();
    fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "11950" } });
    await screen.findByRole("option", { name: "Gulf Polymers — SUP-0001" });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Save draft" })); });
    expect(sent("/procurement/receipts", "POST")).toMatchObject({ supplier_id: "s1", purchase_order_id: "o1",
      lines: [{ material_id: "m1", quantity: "11950", unit: "kg", po_line_id: "l1" }] });
  });
});
