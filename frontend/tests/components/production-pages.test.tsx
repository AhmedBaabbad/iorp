// PROD-QUALITY-FIX-001 item 2: production lists are server pages kept in the address; pickers search the server.
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";

const api = vi.hoisted(() => ({ apiClient: vi.fn() }));
const nav = vi.hoisted(() => ({ replace: vi.fn(), params: new URLSearchParams() }));
vi.mock("@/lib/api-client", async importOriginal => ({ ...(await importOriginal<object>()), apiClient: api.apiClient }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: nav.replace }), usePathname: () => "/production-orders", useSearchParams: () => nav.params }));
vi.mock("@/features/auth/permission-hooks", () => ({ usePermission: () => true }));
vi.mock("@/features/work-centers", () => ({ getWorkCenters: () => Promise.resolve([]) }));
vi.mock("@/features/masterdata", () => ({ useProductName: () => (key: string) => key }));
vi.mock("@/hooks/useFormatter", () => ({ useFormatter: () => ({ date: (v: string) => v, quantity: (v: string, u?: string) => `${v} ${u ?? ""}`.trim() }) }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ title, children }: { title: string; children: ReactNode }) => <main><h1>{title}</h1>{children}</main> }));

import { ProductionOrderPicker } from "@/features/production-orders/components/ProductionOrderPicker";
import { ProductionOrdersList } from "@/features/production-orders/components/ProductionOrdersList";

let en: Record<string, unknown>;
beforeAll(async () => { en = await loadMessages("en") as Record<string, unknown>; });
beforeEach(() => { api.apiClient.mockReset(); nav.replace.mockReset(); nav.params = new URLSearchParams(); });
afterEach(cleanup);
const ui = (node: ReactNode) => render(<NextIntlClientProvider locale="en" messages={en} timeZone="UTC">{node}</NextIntlClientProvider>);
const order = (n: number, status = "in_progress") => ({ id: `po${n}`, organization_id: "o", production_order_number: `PO-${n}`, work_center_id: "wc", product_type: "strap",
  planned_quantity: "10", unit: "roll", priority: "normal", status, planned_start_date: "2026-10-01", planned_end_date: "2026-10-02",
  created_by_user_id: "u", created_at: "", updated_at: "" });

describe("production orders list", () => {
  it("asks the server for the page in the address and shows where it is among all matches", async () => {
    nav.params = new URLSearchParams("page=2&page_size=25&status=draft");
    api.apiClient.mockResolvedValue({ items: [order(26, "draft")], total: 60, page: 2, page_size: 25, pages: 3 });
    ui(<ProductionOrdersList />);
    expect(await screen.findByText("PO-26")).toBeTruthy();
    expect(api.apiClient).toHaveBeenCalledWith("/production/production-orders?page=2&page_size=25&status=draft");
    expect(screen.getByRole("status").textContent).toBe("Showing 26 to 50 of 60");
    // A new filter goes back to page 1 (in the address).
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "released" } });
    expect(nav.replace).toHaveBeenCalledWith("/production-orders?page_size=25&status=released", { scroll: false });
    fireEvent.click(screen.getByRole("button", { name: "Page 3" }));
    expect(nav.replace).toHaveBeenLastCalledWith("/production-orders?page=3&page_size=25&status=draft", { scroll: false });
  });
});

describe("production order picker", () => {
  it("searches the server with a limit and the allowed statuses, never a page of the list", async () => {
    api.apiClient.mockImplementation((path: string) => Promise.resolve(path.includes("search=PO-7") ? [order(7)] : [order(1), order(2)]));
    const onChange = vi.fn();
    ui(<ProductionOrderPicker value="" onChange={onChange} statuses={["in_progress", "on_hold"]} ariaLabel="Order" />);
    const select = await screen.findByRole("combobox", { name: "Order" }) as HTMLSelectElement;
    await waitFor(() => expect(select.options.length).toBe(3));
    await act(async () => { fireEvent.change(screen.getByRole("searchbox"), { target: { value: "PO-7" } }); await new Promise(r => setTimeout(r, 300)); });
    await waitFor(() => expect(Array.from(select.options).map(o => o.textContent)).toEqual(["Choose an order", "PO-7 — strap"]));
    const asked = api.apiClient.mock.calls.map(([p]) => String(p));
    expect(asked.every(p => p.startsWith("/production/production-orders/lookup?"))).toBe(true);
    const last = new URLSearchParams(asked[asked.length - 1].split("?")[1]);
    expect([last.get("search"), last.get("limit"), last.getAll("statuses")]).toEqual(["PO-7", "20", ["in_progress", "on_hold"]]);
    fireEvent.change(select, { target: { value: "po7" } });
    expect(onChange).toHaveBeenCalledWith("po7", expect.objectContaining({ production_order_number: "PO-7" }));
  });

  it("shows an order chosen earlier by its number even when it is not among the matches", async () => {
    api.apiClient.mockImplementation((path: string) => Promise.resolve(path.includes("ids=po9") ? [order(9, "completed")] : []));
    ui(<ProductionOrderPicker value="po9" onChange={() => undefined} ariaLabel="Order" />);
    await waitFor(() => expect(screen.getByRole("option", { name: "PO-9 — strap" })).toBeTruthy());
  });
});
