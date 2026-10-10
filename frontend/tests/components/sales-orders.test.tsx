// SALES-001: the internal sales order and the quotation lifecycle — confirmed orders are locked, actions come from the
// server, every step is in the history, and production takes part of a confirmed order's lines.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";
import { ApiClientError } from "@/lib/api-client";
import type { CommercialOrderData } from "@/features/commercial-orders/types";
import type { QuoteData } from "@/features/quotes/types";

const api = vi.hoisted(() => ({ apiClient: vi.fn() }));
const nav = vi.hoisted(() => ({ push: vi.fn(), params: new URLSearchParams() }));
vi.mock("@/lib/api-client", async importOriginal => ({ ...(await importOriginal<object>()), apiClient: api.apiClient }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: nav.push, replace: vi.fn() }), usePathname: () => "/",
  useParams: () => ({ id: "o1" }), useSearchParams: () => nav.params }));
vi.mock("@/features/auth/permission-hooks", () => ({ usePermission: () => true, useHasAnyPermission: () => true }));
vi.mock("@/hooks/useFormatter", () => ({ useFormatter: () => ({ date: (v: string) => v, dateTime: (v: string) => v, number: (v: string) => v,
  decimal: (v: string | number, places = 2) => Number(v).toFixed(places), quantity: (v: string, u?: string) => `${Number(v)} ${u ?? ""}`.trim(),
  currency: (v: string) => v }) }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ title, subtitle, action, children }: { title: string; subtitle?: string; action?: ReactNode; children: ReactNode }) =>
  <main><h1>{title}</h1><p>{subtitle}</p>{action}{children}</main> }));

import { CommercialOrderDetail } from "@/features/commercial-orders/components/CommercialOrderDetail";
import { CommercialOrderForm } from "@/features/commercial-orders/components/CommercialOrderForm";
import { QuoteLifecycle } from "@/features/quotes/components/QuoteLifecycle";
import { DemandFromSalesOrder } from "@/features/production-demands/from-sales-order";

let en: Record<string, unknown>;
let ar: Record<string, unknown>;
beforeAll(async () => { en = await loadMessages("en") as Record<string, unknown>; ar = await loadMessages("ar") as Record<string, unknown>; });
beforeEach(() => { api.apiClient.mockReset(); nav.push.mockReset(); nav.params = new URLSearchParams(); });
afterEach(cleanup);
const ui = (node: ReactNode, locale: "en" | "ar" = "en") =>
  render(<NextIntlClientProvider locale={locale} messages={locale === "en" ? en : ar} timeZone="UTC">{node}</NextIntlClientProvider>);
const call = (path: string, method: string) => api.apiClient.mock.calls.find(([p, o]) => p === path && o?.method === method);

const order = (over: Partial<CommercialOrderData> = {}): CommercialOrderData => ({
  id: "o1", organization_id: "org", customer_id: "c1", quote_id: null, order_number: "RFS-2026-0007", order_date: "2026-10-01T00:00:00Z",
  status: "confirmed", requested_delivery_date: null, customer_reference: "PO-55", revision: 1, created_by_user_id: "u", created_at: "", updated_at: "",
  currency: "SAR", confirmed_at: "2026-10-02T08:00:00Z", allowed_actions: ["transfer"], fulfilment: "partial",
  transferred_quantities: { i1: "600.000" }, notes: null,
  history: [{ action: "create", from_status: null, to_status: "draft", revision: 1, reason: null, actor_name: "Sara", created_at: "2026-10-01T08:00:00Z" },
    { action: "confirm", from_status: "draft", to_status: "confirmed", revision: 1, reason: null, actor_name: "Sara", created_at: "2026-10-02T08:00:00Z" }],
  items: [{ id: "i1", line_no: 1, product_type: "pp_strap", requested_spec_json: { width_mm: 19 }, quantity: "1000.00", unit: "kg",
    agreed_unit_price: null, line_total: null }],
  ...over,
});

function answer(o: CommercialOrderData) {
  return (path: string, opts?: { method?: string }) => {
    if (path === "/commercial/orders/o1" && !opts?.method) return Promise.resolve(o);
    if (path.startsWith("/commercial/customers/c1") && !path.includes("quotes")) return Promise.resolve({ id: "c1", name: "Acme Films" });
    if (path.startsWith("/masterdata/")) return Promise.resolve([]);
    if (opts?.method === "POST") return Promise.resolve(order({ status: "draft", revision: 2, allowed_actions: ["edit", "confirm", "cancel"] }));
    return Promise.resolve([]);
  };
}

describe("sales order detail", () => {
  it("shows what was sent to production and what remains, and offers only the server's actions", async () => {
    api.apiClient.mockImplementation(answer(order()));
    ui(<CommercialOrderDetail />);
    expect(await screen.findByText("RFS-2026-0007")).toBeTruthy();
    expect(screen.getByText("Partly sent to production")).toBeTruthy();
    expect(screen.getByText(/^600 /)).toBeTruthy();   // sent
    expect(screen.getByText(/^400 /)).toBeTruthy();   // remaining
    const send = screen.getByRole("link", { name: "Send to production" });
    expect(send.getAttribute("href")).toBe("/production/demands/new?sales_order=o1&customer=c1");
    expect(screen.queryByRole("link", { name: "Edit" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Back to draft" })).toBeNull();
    const history = screen.getByRole("region", { name: "Status history" });
    expect(history.textContent).toContain("Created");
    expect(history.textContent).toContain("Confirmed");
  });

  it("takes a confirmed order back to a draft with a reason", async () => {
    api.apiClient.mockImplementation(answer(order({ fulfilment: "none", transferred_quantities: {}, allowed_actions: ["transfer", "revise", "cancel"] })));
    ui(<CommercialOrderDetail />);
    fireEvent.click(await screen.findByRole("button", { name: "Back to draft" }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Customer changed the width" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Back to draft" }).at(-1)!);
    await waitFor(() => expect(call("/commercial/orders/o1/revise", "POST")?.[1]?.body).toEqual({ reason: "Customer changed the width" }));
    expect(await screen.findByText("Revision 2")).toBeTruthy();
  });

  it("explains a refusal in Arabic", async () => {
    api.apiClient.mockImplementation((path: string, opts?: { method?: string }) => {
      if (opts?.method === "POST") return Promise.reject(new ApiClientError("x", 400, { detail: "ORDER_SOURCE_REQUIRED" }));
      return answer(order({ status: "draft", customer_reference: null, allowed_actions: ["edit", "confirm"] }))(path, opts);
    });
    ui(<CommercialOrderDetail />, "ar");
    fireEvent.click(await screen.findByRole("button", { name: "اعتماد الأمر" }));
    expect((await screen.findByRole("alert")).textContent).toContain("مرجع العميل");
  });
});

describe("sales order form", () => {
  it("has no JSON field and the screen's new subtitle; a direct order needs the customer's reference", async () => {
    api.apiClient.mockImplementation((path: string) => Promise.resolve(path.startsWith("/commercial/customers") && !path.includes("/quotes")
      ? [{ id: "c1", name: "Acme Films", customer_code: "C-1" }] : path.startsWith("/masterdata/settings") ? { vat_rate: "15", default_currency: "SAR", currencies: [] } : []));
    ui(<CommercialOrderForm />, "ar");
    expect(await screen.findByText("تسجيل طلب العميل الداخلي وتحديد المنتجات والكميات والمواصفات المطلوبة")).toBeTruthy();
    expect(screen.queryByText(/JSON/)).toBeNull();
    fireEvent.click(screen.getByLabelText("طلب مباشر من العميل"));
    expect(screen.getByText("سعر الوحدة (اختياري)")).toBeTruthy();
    const reference = screen.getByPlaceholderText("مثال: PO-2026-118") as HTMLInputElement;
    expect(reference.required).toBe(true);
  });
});

describe("quotation lifecycle", () => {
  const quote = (over: Partial<QuoteData> = {}): QuoteData => ({ id: "q1", organization_id: "o", customer_id: "c1", sample_id: null, quote_number: "QT-2026-0004",
    issue_date: "", valid_until: "", status: "issued", currency: "USD", subtotal_amount: "0", discount_amount: "0", tax_amount: "0", total_amount: "0",
    created_by_user_id: "u", created_at: "", updated_at: "", notes: null, items: [], revision: 1, allowed_actions: ["accept", "reject", "expire", "revise"],
    history: [{ action: "issue", from_status: "draft", to_status: "issued", revision: 1, reason: null, actor_name: "Sara", created_at: "" }], orders: [], ...over });

  it("accepts through its own step and then offers the sales order", async () => {
    const changed = vi.fn();
    api.apiClient.mockResolvedValue(quote({ status: "accepted", allowed_actions: ["create_order"] }));
    ui(<QuoteLifecycle quote={quote()} onChange={changed} />);
    expect(screen.queryByRole("link", { name: "Edit" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Customer accepted" }));
    await waitFor(() => expect(changed).toHaveBeenCalled());
    expect(call("/commercial/quotes/q1/accept", "POST")).toBeTruthy();
  });

  it("makes the sales order from an accepted quotation", async () => {
    api.apiClient.mockResolvedValue(order({ id: "o9", status: "draft" }));
    ui(<QuoteLifecycle quote={quote({ status: "accepted", allowed_actions: ["create_order"] })} onChange={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Create sales order" }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/commercial-orders/o9"));
    expect(call("/commercial/quotes/q1/sales-order", "POST")).toBeTruthy();
  });
});

describe("production demand from a sales order", () => {
  it("sends part of a line and never more than what remains", async () => {
    nav.params = new URLSearchParams("sales_order=o1&customer=c1");
    api.apiClient.mockImplementation((path: string, opts?: { method?: string }) => {
      if (path.startsWith("/production/demand-lookups/customers")) return Promise.resolve([{ id: "c1", code: "C-1", name: "Acme Films" }]);
      if (path.startsWith("/production/demand-lookups/sales-orders")) return Promise.resolve([{ id: "o1", number: "RFS-2026-0007", quote_id: null,
        requested_delivery_date: null, lines: [{ id: "i1", line_no: 1, product_type: "pp_strap", target_spec_json: { width_mm: 19 }, unit: "kg",
          ordered_quantity: "1000.00", transferred_quantity: "600.000", remaining_quantity: "400.000" }] }]);
      if (opts?.method === "POST") return Promise.resolve({ id: "d1" });
      return Promise.resolve([]);
    });
    ui(<DemandFromSalesOrder />);
    const input = await screen.findByLabelText("Quantity sent now for line 1") as HTMLInputElement;
    await waitFor(() => expect(input.value).toBe("400"));
    fireEvent.change(input, { target: { value: "500" } });
    fireEvent.submit(input.closest("form")!);  // past the browser's own max check
    expect((await screen.findByRole("alert")).textContent).toContain("more than what remains");
    fireEvent.change(input, { target: { value: "250" } });
    fireEvent.click(screen.getByRole("button", { name: "Create production demand" }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/production/demands/d1"));
    const body = call("/production/demands/from-sales-order", "POST")?.[1]?.body;
    expect(body.lines).toEqual([{ order_item_id: "i1", quantity: "250" }]);
    expect(body.transfer_key).toBeTruthy();
  });
});
