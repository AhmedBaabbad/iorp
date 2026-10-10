// Mixed-specification orders: review arrangement before creating, and draft-order line editing.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";
import type { Demand } from "@/features/production-demands/api";
import type { ProductionOrderData } from "@/features/production-orders/types";

const api = vi.hoisted(() => ({ apiClient: vi.fn() }));
const perms = vi.hoisted(() => ({ granted: new Set<string>() }));
vi.mock("@/lib/api-client", async importOriginal => ({ ...(await importOriginal<object>()), apiClient: api.apiClient }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/", useSearchParams: () => new URLSearchParams() }));
vi.mock("@/features/auth/permission-hooks", () => ({ usePermission: (code: string) => perms.granted.has(code) }));
vi.mock("@/features/work-centers", () => ({ getWorkCenters: () => Promise.resolve([{ id: "wc1", name: "Line 1" }]) }));

import { PlanningAllocation } from "@/features/production-demands/planning-allocation";
import { OrderLines } from "@/features/production-orders/components/OrderLines";

let messages: Record<string, unknown>;
beforeAll(async () => {
  messages = await loadMessages("en") as Record<string, unknown>;
  // jsdom has no modal dialogs; the review content is in the DOM either way.
  HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  HTMLDialogElement.prototype.close = function () { this.open = false; };
});
beforeEach(() => {
  api.apiClient.mockReset();
  perms.granted = new Set(["production:planning:allocate", "production:production_orders:create", "production:planning:release_allocation"]);
});
afterEach(cleanup);
const ui = (node: ReactNode) => render(<NextIntlClientProvider locale="en" messages={messages} timeZone="UTC">{node}</NextIntlClientProvider>);

function demand(id: string, number: string, items: { id: string; spec: Record<string, unknown>; unit?: string; product?: string; remaining?: string }[]): Demand {
  return {
    id, demand_number: number, customer: { id: "c1", code: "C1", name: "Acme" }, quote: null, request_date: "2026-09-20", requested_delivery_date: null,
    priority: "normal", status: "ready_for_planning", planning_sequence: null, notes: null, item_count: items.length, total_quantity: "0", quantities_by_unit: {},
    created_by: null, created_at: "2026-09-20T00:00:00Z", updated_at: "2026-09-20T00:00:00Z", total_required: "0", total_allocated: "0",
    total_active_allocated: "0", total_released_allocated: "0", total_remaining: "0", allocation_percentage: "0",
    items: items.map((it, n) => ({ id: it.id, line_no: n + 1, product_type: it.product ?? "film", unit: it.unit ?? "kg", target_spec_json: it.spec, required_quantity: "1000",
      remaining_quantity: it.remaining ?? "1000", allocated_quantity: "0", active_allocated_quantity: "0", released_allocated_quantity: "0", notes: null, allocations: [] })),
  };
}
const previewLine = (line_no: number, spec: Record<string, unknown>, qty: string, entries: [string, string, string][]) => ({
  line_no, target_spec_json: spec, planned_quantity: qty, unit: "kg",
  allocations: entries.map(([item, number, q]) => ({ production_demand_item_id: item, demand_number: number, customer_name: "Acme", demand_item_line_no: 1, allocated_quantity: q })),
});

describe("review before creating an order", () => {
  const demands = [
    demand("d1", "PD-1", [{ id: "wide", spec: { width_mm: 20, color: "red" } }]),
    demand("d2", "PD-2", [{ id: "narrow", spec: { width_mm: 10, color: "red" } }]),
    demand("d3", "PD-3", [{ id: "meters", spec: { width_mm: 10 }, unit: "m" }]),
  ];

  function select(label: string) {
    fireEvent.click(screen.getByRole("checkbox", { name: `Select demand items to allocate ${label}` }));
  }

  it("accepts differing specifications and shows the server arrangement", async () => {
    api.apiClient.mockResolvedValue({ lines: [previewLine(1, { width_mm: 10, color: "red" }, "1000", [["narrow", "PD-2", "1000"]]), previewLine(2, { width_mm: 20, color: "red" }, "1000", [["wide", "PD-1", "1000"]])] });
    ui(<PlanningAllocation demands={demands} busy={false} onRefresh={() => {}} />);
    select("PD-1 1"); select("PD-2 1");
    expect(screen.queryByText(/same product type and unit/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Create production order" }));
    const table = await screen.findByRole("table", { name: "Production arrangement" });
    await within(table).findByText(/PD-2/);  // lines arrive from the debounced preview
    const rows = within(table).getAllByRole("row").map(r => r.textContent ?? "");
    expect(rows.findIndex(r => r.includes("PD-2"))).toBeLessThan(rows.findIndex(r => r.includes("PD-1")));
    expect(within(table).getByRole("rowheader", { name: "1" })).toBeTruthy();
    const call = api.apiClient.mock.calls.find(([path]) => path === "/production/planning/preview-production-order")!;
    expect(call[1].body.allocations.map((a: { production_demand_item_id: string }) => a.production_demand_item_id).sort()).toEqual(["narrow", "wide"]);
  });

  it("re-arranges when a quantity is edited or a demand is removed in the review", async () => {
    api.apiClient.mockResolvedValue({ lines: [previewLine(1, { width_mm: 10 }, "1000", [["narrow", "PD-2", "1000"]]), previewLine(2, { width_mm: 20 }, "1000", [["wide", "PD-1", "1000"]])] });
    ui(<PlanningAllocation demands={demands} busy={false} onRefresh={() => {}} />);
    select("PD-1 1"); select("PD-2 1");
    fireEvent.click(screen.getByRole("button", { name: "Create production order" }));
    const table = await screen.findByRole("table", { name: "Production arrangement" });
    await within(table).findByText(/PD-2/);
    fireEvent.change(within(table).getByRole("spinbutton", { name: "Allocate now PD-2 1" }), { target: { value: "400" } });
    await waitFor(() => expect(api.apiClient.mock.calls.some(([, o]) => JSON.stringify(o?.body).includes('"400"'))).toBe(true));
    const removeWide = within(table).getAllByRole("button", { name: "Remove" })[1];
    await act(async () => { fireEvent.click(removeWide); });
    await waitFor(() => {
      const last = api.apiClient.mock.calls.filter(([path]) => path === "/production/planning/preview-production-order").at(-1)!;
      expect(last[1].body.allocations.map((a: { production_demand_item_id: string }) => a.production_demand_item_id)).toEqual(["narrow"]);
    });
  });

  it("still refuses different units in one order", () => {
    ui(<PlanningAllocation demands={demands} busy={false} onRefresh={() => {}} />);
    select("PD-2 1"); select("PD-3 1");
    expect(screen.getByText(/same product type and unit/)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Create production order" }) as HTMLButtonElement).disabled).toBe(true);
  });
});

describe("order lines on a production order", () => {
  function order(overrides: Partial<ProductionOrderData> = {}): ProductionOrderData {
    const alloc = (id: string, item: string, number: string, qty: string, line: string) => ({ id, production_demand_id: "d", production_demand_item_id: item, demand_number: number,
      customer_name: "Acme", demand_item_line_no: 1, allocated_quantity: qty, unit: "kg", status: "active" as const, allocated_at: "2026-09-26T00:00:00Z",
      released_at: null, release_reason: null, production_order_item_id: line });
    return {
      id: "po1", organization_id: "o", production_order_number: "PO-1", work_center_id: "wc1", product_type: "film", planned_quantity: "500", unit: "kg",
      priority: "normal", status: "draft", planned_start_date: "2026-10-01", planned_end_date: "2026-10-02", created_by_user_id: "u", created_at: "", updated_at: "",
      target_spec_json: null, notes: null, editable: true, allocation_open: true,
      allocations: [alloc("a1", "i1", "PD-1", "300", "L1"), alloc("a2", "i2", "PD-2", "200", "L2")],
      lines: [{ id: "L1", line_no: 1, target_spec_json: { width_mm: 10, color: "blue" }, planned_quantity: "300", unit: "kg", allocation_ids: ["a1"] },
              { id: "L2", line_no: 2, target_spec_json: { width_mm: 20, color: "red" }, planned_quantity: "200", unit: "kg", allocation_ids: ["a2"] }],
      ...overrides,
    };
  }
  const queue = { items: [demand("d9", "PD-9", [{ id: "new-item", spec: { width_mm: 15 }, remaining: "250" }, { id: "wrong-unit", spec: {}, unit: "m" }])], total: 1, page: 1, page_size: 100 };

  it("shows lines in order with their specifications and quantities", async () => {
    api.apiClient.mockResolvedValue(queue);
    ui(<OrderLines order={order()} />);
    const table = screen.getByRole("table", { name: "Order lines" });
    const heads = within(table).getAllByRole("rowheader").map(h => h.textContent);
    expect(heads).toEqual(["1", "2"]);
    expect(within(table).getByText("blue")).toBeTruthy();
    expect(within(table).getByText("300 kg")).toBeTruthy();
  });

  it("changes a quantity on a draft order", async () => {
    const onChanged = vi.fn();
    api.apiClient.mockImplementation((path: string) => Promise.resolve(path.startsWith("/production/planning/demands") ? queue : {}));
    ui(<OrderLines order={order()} onChanged={onChanged} />);
    fireEvent.change(screen.getByRole("spinbutton", { name: "Allocate now PD-1 1" }), { target: { value: "250" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Save" })); });
    expect(api.apiClient).toHaveBeenCalledWith("/production/allocations/a1", { method: "PATCH", body: { allocated_quantity: "250" } });
    expect(onChanged).toHaveBeenCalled();
  });

  it("adds only compatible demand items that still have quantity", async () => {
    const onChanged = vi.fn();
    api.apiClient.mockImplementation((path: string) => Promise.resolve(path.startsWith("/production/planning/demands") ? queue : {}));
    ui(<OrderLines order={order()} onChanged={onChanged} />);
    const form = screen.getByRole("form", { name: "Add a demand" });
    const picker = within(form).getByRole("combobox");
    await waitFor(() => expect(within(picker).getAllByRole("option").length).toBe(2));
    expect(within(picker).queryByText(/wrong-unit/)).toBeNull();
    fireEvent.change(picker, { target: { value: "new-item" } });
    expect((within(form).getByRole("spinbutton") as HTMLInputElement).value).toBe("250");
    await act(async () => { fireEvent.click(within(form).getByRole("button", { name: "Add to order" })); });
    expect(api.apiClient).toHaveBeenCalledWith("/production/orders/po1/allocations", { method: "POST", body: { production_demand_item_id: "new-item", allocated_quantity: "250" } });
    const listCall = api.apiClient.mock.calls.find(([path]) => String(path).startsWith("/production/planning/demands"))![0] as string;
    expect(new URLSearchParams(listCall.split("?")[1]).get("product_type")).toBe("film");
  });

  it("is read-only once the order is completed (allocations locked by the server)", () => {
    ui(<OrderLines order={order({ status: "completed", editable: false, allocation_open: false })} />);
    expect(screen.queryByRole("spinbutton")).toBeNull();
    expect(screen.queryByRole("form", { name: "Add a demand" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Remove" })).toBeNull();
    expect(screen.getByRole("table", { name: "Order lines" })).toBeTruthy();
  });

  it("keeps an in-progress order open for allocations and marks quantities added after start", async () => {
    api.apiClient.mockImplementation((path: string) => Promise.resolve(path.startsWith("/production/planning/demands") ? queue : {}));
    const base = order();
    const started = order({ status: "in_progress", editable: false, allocation_open: true,
      allocations: base.allocations.map(a => a.id === "a2" ? { ...a, order_status_at_allocation: "in_progress", added_after_start: true } : { ...a, order_status_at_allocation: "draft", added_after_start: false }) });
    ui(<OrderLines order={started} />);
    expect(screen.getByText(/Order on the floor/)).toBeTruthy();
    expect(screen.getAllByText("Added after start")).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "Remove" })).toHaveLength(2);
    expect(screen.getByRole("form", { name: "Add a demand" })).toBeTruthy();
  });

  it("offers release with the release permission alone", () => {
    perms.granted = new Set(["production:planning:release_allocation"]);
    ui(<OrderLines order={order({ status: "on_hold", editable: false, allocation_open: true })} />);
    expect(screen.getAllByRole("button", { name: "Remove" })).toHaveLength(2);
    expect(screen.queryByRole("spinbutton")).toBeNull();
  });
});

describe("add to an existing production order from planning", () => {
  const demands = [demand("d1", "PD-1", [{ id: "item-1", spec: { width_mm: 10 }, remaining: "200" }])];

  it("lists the open orders the server offers, whatever their status, and adds the item", async () => {
    perms.granted = new Set(["production:planning:allocate"]);
    api.apiClient.mockImplementation((path: string) => Promise.resolve(path.startsWith("/production/planning/eligible-orders") ? [
      { id: "po7", production_order_number: "PO-7", status: "in_progress", work_center_name: "Line 1", product_type: "film", unit: "kg", planned_quantity: "600", planned_start_date: "2026-10-01", planned_end_date: "2026-10-03" },
    ] : {}));
    ui(<PlanningAllocation demands={demands} busy={false} onRefresh={() => undefined} />);
    fireEvent.click(screen.getByRole("checkbox", { name: "Select demand items to allocate PD-1 1" }));
    // Creating a new order needs the create permission; adding to an existing one does not.
    expect(screen.queryByRole("button", { name: "Create production order" })).toBeNull();
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Add to an existing order" })); });
    expect(api.apiClient).toHaveBeenCalledWith("/production/planning/eligible-orders?demand_item_id=item-1");
    const dialog = screen.getByRole("dialog", { name: "Add to an existing production order" });
    expect(within(dialog).getByText("PO-7")).toBeTruthy();
    expect(within(dialog).getByText("In progress")).toBeTruthy();
    await act(async () => { fireEvent.click(within(dialog).getByRole("button", { name: "Add to this order" })); });
    expect(api.apiClient).toHaveBeenCalledWith("/production/orders/po7/allocations", { method: "POST", body: { production_demand_item_id: "item-1", allocated_quantity: "200" } });
  });

  it("says so when no open order can take the item", async () => {
    api.apiClient.mockImplementation((path: string) => Promise.resolve(path.startsWith("/production/planning/eligible-orders") ? [] : {}));
    ui(<PlanningAllocation demands={demands} busy={false} onRefresh={() => undefined} />);
    fireEvent.click(screen.getByRole("checkbox", { name: "Select demand items to allocate PD-1 1" }));
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Add to an existing order" })); });
    expect(screen.getByText("No open production order can take this demand item.")).toBeTruthy();
  });
});
