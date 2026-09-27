// PROD-PLAN-003 planning UI: queue views, progress, allocation history, release and cancel.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";
import type { Demand, DemandItemAllocation } from "@/features/production-demands/api";
import type { ProductionOrderData } from "@/features/production-orders/types";

const api = vi.hoisted(() => ({ apiClient: vi.fn() }));
const nav = vi.hoisted(() => ({ replace: vi.fn(), search: "" }));
const perms = vi.hoisted(() => ({ granted: new Set<string>() }));

vi.mock("@/lib/api-client", async importOriginal => ({ ...(await importOriginal<object>()), apiClient: api.apiClient }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: nav.replace, push: vi.fn() }),
  usePathname: () => "/production/planning",
  useSearchParams: () => new URLSearchParams(nav.search),
}));
vi.mock("@/features/auth/permission-hooks", () => ({ usePermission: (code: string) => perms.granted.has(code) }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ title, children }: { title: string; children: ReactNode }) => <main><h1>{title}</h1>{children}</main> }));
vi.mock("@/features/work-centers", () => ({ getWorkCenters: () => Promise.resolve([]) }));

import { DemandList } from "@/features/production-demands/list";
import { DemandAllocations } from "@/features/production-demands/demand-allocations";
import { OrderAllocations } from "@/features/production-orders/components/OrderAllocations";

let messages: Record<string, unknown>;
beforeAll(async () => { messages = await loadMessages("en") as Record<string, unknown>; });
beforeEach(() => {
  api.apiClient.mockReset(); nav.replace.mockReset(); nav.search = "";
  perms.granted = new Set(["production:planning:read", "production:demands:read", "production:planning:release_allocation", "production:orders:cancel"]);
});
afterEach(cleanup);

function ui(node: ReactNode) {
  return render(<NextIntlClientProvider locale="en" messages={messages} timeZone="UTC">{node}</NextIntlClientProvider>);
}

function allocation(overrides: Partial<DemandItemAllocation> = {}): DemandItemAllocation {
  return { id: "a1", production_order_id: "po1", production_order_number: "PO-2026-000001", production_order_status: "draft", allocated_quantity: "600.000",
           status: "active", created_at: "2026-09-26T10:00:00Z", released_at: null, release_reason: null, ...overrides };
}

function demand(overrides: Partial<Demand> = {}, item: Partial<Demand["items"][number]> = {}): Demand {
  return {
    id: "d1", demand_number: "PD-2026-000001", customer: { id: "c1", code: "C-1", name: "Acme Films" }, quote: null,
    request_date: "2026-09-20", requested_delivery_date: "2099-01-01", priority: "normal", status: "partially_planned", planning_sequence: null,
    notes: null, item_count: 1, total_quantity: "1000.000", quantities_by_unit: { kg: "1000.000" }, created_by: null,
    created_at: "2026-09-20T10:00:00Z", updated_at: "2026-09-20T10:00:00Z", total_required: "1000.000", total_allocated: "600.000",
    total_active_allocated: "600.000", total_released_allocated: "0", total_remaining: "400.000", allocation_percentage: "60", spec_summary: { width_mm: 12 },
    items: [{ id: "i1", line_no: 1, product_type: "film", target_spec_json: { width_mm: 12 }, required_quantity: "1000.000", unit: "kg", notes: null,
              allocated_quantity: "600.000", active_allocated_quantity: "600.000", released_allocated_quantity: "0", remaining_quantity: "400.000",
              planning_state: "partially_planned", allocations: [allocation()], ...item }],
    ...overrides,
  };
}

const page = (items: Demand[]) => ({ items, total: items.length, page: 1, page_size: 20 });
const planningCalls = () => api.apiClient.mock.calls.map(([path]) => String(path)).filter(path => path.startsWith("/production/planning/demands"));
const viewOf = (path: string) => new URLSearchParams(path.split("?")[1]).get("view");

function routeApi(queue: (view: string | null) => Demand[]) {
  api.apiClient.mockImplementation((path: string) => {
    if (path.startsWith("/production/planning/demands")) return Promise.resolve(page(queue(viewOf(path))));
    if (path.startsWith("/production/demand-lookups/customers")) return Promise.resolve([]);
    return Promise.resolve({});
  });
}

describe("planning queue", () => {
  it("requests the active view by default so completed planning is hidden", async () => {
    const planned = demand({ id: "d2", demand_number: "PD-PLANNED", status: "planned", total_remaining: "0" });
    routeApi(view => (view === "active" ? [demand()] : [demand(), planned]));
    ui(<DemandList planning />);
    expect(await screen.findByText("PD-2026-000001")).toBeTruthy();
    expect(viewOf(planningCalls()[0])).toBe("active");
    expect(screen.queryByText("PD-PLANNED")).toBeNull();
    expect(screen.getByRole("tab", { name: "Active queue" }).getAttribute("aria-selected")).toBe("true");
  });

  it("shows partial progress and the remaining quantity", async () => {
    routeApi(() => [demand()]);
    ui(<DemandList planning />);
    expect(await screen.findByText("600 / 1000 kg planned")).toBeTruthy();
    expect(screen.getByText("400 kg remaining")).toBeTruthy();
    expect(Number(screen.getByRole("progressbar", { name: "Planning progress, line 1" }).getAttribute("value"))).toBe(60);
  });

  it("switches between active, planned and all views on the server", async () => {
    const planned = demand({ id: "d2", demand_number: "PD-PLANNED", status: "planned", total_remaining: "0" }, { remaining_quantity: "0", active_allocated_quantity: "1000" });
    routeApi(view => (view === "planned" ? [planned] : view === "all" ? [demand(), planned] : [demand()]));
    ui(<DemandList planning />);
    await screen.findByText("PD-2026-000001");

    fireEvent.click(screen.getByRole("tab", { name: "Fully planned" }));
    expect(await screen.findByText("PD-PLANNED")).toBeTruthy();
    await waitFor(() => expect(screen.queryByText("PD-2026-000001")).toBeNull());
    expect(nav.replace).toHaveBeenLastCalledWith("/production/planning?view=planned", { scroll: false });
    // Fully planned demands cannot be allocated, so the allocation panel is not offered.
    expect(screen.queryByText("Select demand items to allocate")).toBeNull();

    fireEvent.click(screen.getByRole("tab", { name: "All demands" }));
    await waitFor(() => expect(screen.getByText("PD-2026-000001")).toBeTruthy());
    expect(screen.getByText("PD-PLANNED")).toBeTruthy();
    expect(planningCalls().map(viewOf)).toEqual(expect.arrayContaining(["active", "planned", "all"]));
  });

  it("opens the view named in the URL", async () => {
    nav.search = "view=planned";
    routeApi(() => []);
    ui(<DemandList planning />);
    await waitFor(() => expect(planningCalls().length).toBeGreaterThan(0));
    expect(viewOf(planningCalls()[0])).toBe("planned");
    expect(await screen.findByText("No fully planned demands")).toBeTruthy();
  });
});

describe("demand planning / allocations", () => {
  it("keeps released allocation history visible with its reason", () => {
    const released = allocation({ id: "a2", production_order_id: "po2", production_order_number: "PO-2026-000002", production_order_status: "cancelled",
                                  allocated_quantity: "400.000", status: "released", released_at: "2026-09-26T12:00:00Z", release_reason: "Customer withdrew" });
    ui(<DemandAllocations demand={demand({ total_released_allocated: "400.000" }, { allocations: [allocation(), released], released_allocated_quantity: "400.000" })} />);
    const history = screen.getByRole("table", { name: "Allocation history" });
    const rows = within(history).getAllByRole("row");
    expect(within(rows[1]).getByText("Active")).toBeTruthy();
    expect(within(rows[2]).getByText("Released")).toBeTruthy();
    expect(within(rows[2]).getByText("Customer withdrew")).toBeTruthy();
    expect(within(rows[1]).getByRole("button", { name: "Release" })).toBeTruthy();
    expect(within(rows[2]).queryByRole("button", { name: "Release" })).toBeNull();
    const summary = screen.getByLabelText("Planning summary");
    const releasedCell = within(summary).getByText("Released allocated").nextElementSibling;
    expect(releasedCell?.textContent).toBe("400.000 kg");
  });

  it("releases with a reason and shows the updated remaining quantity", async () => {
    api.apiClient.mockResolvedValue({});
    const onChanged = vi.fn();
    const view = ui(<DemandAllocations demand={demand()} onChanged={onChanged} />);
    fireEvent.click(screen.getByRole("button", { name: "Release" }));
    const dialog = screen.getByRole("dialog", { name: "Release allocation from PO-2026-000001" });
    const confirm = within(dialog).getByRole("button", { name: "Release" });
    expect((confirm as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(within(dialog).getByLabelText("Reason"), { target: { value: "  Wrong line  " } });
    await act(async () => { fireEvent.click(confirm); });
    expect(api.apiClient).toHaveBeenCalledWith("/production/allocations/a1/release", { method: "POST", body: { reason: "Wrong line" } });
    expect(onChanged).toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByRole("status").textContent).toContain("Allocation released");

    const after = demand({ status: "ready_for_planning", total_active_allocated: "0", total_released_allocated: "600.000", total_remaining: "1000.000", allocation_percentage: "0" },
      { active_allocated_quantity: "0", released_allocated_quantity: "600.000", remaining_quantity: "1000.000", allocations: [allocation({ status: "released", released_at: "2026-09-26T12:00:00Z", release_reason: "Wrong line" })] });
    view.rerender(<NextIntlClientProvider locale="en" messages={messages} timeZone="UTC"><DemandAllocations demand={after} onChanged={onChanged} /></NextIntlClientProvider>);
    expect(screen.getByText(/Remaining quantity: 1000 kg/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Release" })).toBeNull();
  });

  it("does not offer release once execution has started", () => {
    ui(<DemandAllocations demand={demand({}, { allocations: [allocation({ production_order_status: "in_progress" })] })} />);
    expect(screen.queryByRole("button", { name: "Release" })).toBeNull();
  });

  it("shows the server reason when a release is refused", async () => {
    const { ApiClientError } = await import("@/lib/api-client");
    api.apiClient.mockRejectedValue(new ApiClientError("conflict", 409, { detail: { code: "LAST_ACTIVE_ALLOCATION" } }));
    ui(<DemandAllocations demand={demand()} />);
    fireEvent.click(screen.getByRole("button", { name: "Release" }));
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "x" } });
    await act(async () => { fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Release" })); });
    expect(screen.getByRole("alert").textContent).toContain("last active allocation");
  });
});

describe("production order allocation sources", () => {
  function order(overrides: Partial<ProductionOrderData> = {}): ProductionOrderData {
    return {
      id: "po1", organization_id: "o1", production_order_number: "PO-2026-000001", work_center_id: "wc1", product_type: "film",
      planned_quantity: "600.000", unit: "kg", priority: "normal", status: "draft", planned_start_date: "2026-10-01", planned_end_date: "2026-10-02",
      created_by_user_id: "u1", created_at: "2026-09-26T10:00:00Z", updated_at: "2026-09-26T10:00:00Z", target_spec_json: null, notes: null,
      active_allocated_quantity: "600.000",
      allocations: [{ id: "a1", production_demand_id: "d1", production_demand_item_id: "i1", demand_number: "PD-2026-000001", customer_name: "Acme Films",
                      demand_item_line_no: 1, allocated_quantity: "600.000", unit: "kg", status: "active", allocated_at: "2026-09-26T10:00:00Z", released_at: null, release_reason: null }],
      ...overrides,
    };
  }

  it("cancels a pre-execution order and keeps the released sources visible", async () => {
    api.apiClient.mockResolvedValue({});
    const onChanged = vi.fn();
    const view = ui(<OrderAllocations order={order()} onChanged={onChanged} />);
    fireEvent.click(screen.getByRole("button", { name: "Cancel order and release allocations" }));
    const dialog = screen.getByRole("dialog", { name: "Cancel production order PO-2026-000001" });
    fireEvent.change(within(dialog).getByLabelText("Reason"), { target: { value: "Customer withdrew" } });
    await act(async () => { fireEvent.click(within(dialog).getByRole("button", { name: "Cancel order and release allocations" })); });
    expect(api.apiClient).toHaveBeenCalledWith("/production/production-orders/po1/cancel", { method: "POST", body: { reason: "Customer withdrew" } });
    expect(onChanged).toHaveBeenCalled();

    const cancelled = order({ status: "cancelled", active_allocated_quantity: "0",
      allocations: [{ ...order().allocations[0], status: "released", released_at: "2026-09-26T12:00:00Z", release_reason: "Customer withdrew" }] });
    view.rerender(<NextIntlClientProvider locale="en" messages={messages} timeZone="UTC"><OrderAllocations order={cancelled} onChanged={onChanged} /></NextIntlClientProvider>);
    expect(screen.getByText("Released")).toBeTruthy();
    expect(screen.getByText("Customer withdrew")).toBeTruthy();
    expect(screen.getByRole("link", { name: "PD-2026-000001" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Cancel order and release allocations" })).toBeNull();
  });

  it("hides cancel without permission or after execution starts", () => {
    ui(<OrderAllocations order={order({ status: "in_progress" })} />);
    expect(screen.queryByRole("button", { name: "Cancel order and release allocations" })).toBeNull();
    cleanup();
    perms.granted.delete("production:orders:cancel");
    ui(<OrderAllocations order={order()} />);
    expect(screen.queryByRole("button", { name: "Cancel order and release allocations" })).toBeNull();
  });
});
