// Production order status panel and history: buttons come from the server, never from the client.
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";
import type { OrderLifecycle, ProductionOrderData } from "@/features/production-orders/types";

const api = vi.hoisted(() => ({ apiClient: vi.fn() }));
const perms = vi.hoisted(() => ({ granted: new Set<string>() }));
vi.mock("@/lib/api-client", async importOriginal => ({ ...(await importOriginal<object>()), apiClient: api.apiClient }));
vi.mock("@/features/auth/permission-hooks", () => ({ usePermission: (code: string) => perms.granted.has(code) }));
// Dates are formatted with the organization's timezone from the auth context; a plain stand-in suffices here.
vi.mock("@/hooks/useFormatter", () => ({ useFormatter: () => ({ date: (v: string) => v, dateTime: (v: string) => v }) }));

import { OrderStatusPanel } from "@/features/production-orders/components/OrderStatusPanel";
import { OrderStatusTimeline } from "@/features/production-orders/components/OrderStatusTimeline";

let messages: Record<string, unknown>;
beforeAll(async () => { messages = await loadMessages("en") as Record<string, unknown>; });
beforeEach(() => { api.apiClient.mockReset().mockResolvedValue({}); perms.granted = new Set(); });
afterEach(cleanup);
const ui = (node: ReactNode) => render(<NextIntlClientProvider locale="en" messages={messages} timeZone="UTC">{node}</NextIntlClientProvider>);

const action = (name: OrderLifecycle["actions"][number]["action"], extra: Partial<OrderLifecycle["actions"][number]> = {}) =>
  ({ action: name, target: "released" as const, requires_reason: false, confirm: false, ...extra });
function order(status: ProductionOrderData["status"], lifecycle: Partial<OrderLifecycle> = {}): ProductionOrderData {
  return {
    id: "po1", organization_id: "o", production_order_number: "PO-1", work_center_id: "wc", product_type: "film", planned_quantity: "400", unit: "kg",
    priority: "normal", status, planned_start_date: "2026-10-01", planned_end_date: "2026-10-02", created_by_user_id: "u", created_at: "", updated_at: "",
    target_spec_json: null, notes: null, allocations: [],
    lifecycle: { status_version: 3, actual_start_at: null, actual_end_at: null, start_overdue: false, finish_overdue: false, terminal: false, actions: [], ...lifecycle },
  };
}

describe("order status panel", () => {
  it("shows only the actions the server allows", () => {
    ui(<OrderStatusPanel order={order("draft", { actions: [action("release"), action("cancel", { requires_reason: true, confirm: true })] })} />);
    const buttons = within(screen.getByRole("region", { name: "Order status" })).getAllByRole("button").map(b => b.textContent);
    expect(buttons).toEqual(["Release", "Cancel order"]);
    expect(screen.getByText("Draft")).toBeTruthy();
  });

  it("runs a simple action at once, sending the version the user saw", async () => {
    const onChanged = vi.fn();
    ui(<OrderStatusPanel order={order("draft", { actions: [action("release")] })} onChanged={onChanged} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Release" })); });
    expect(api.apiClient).toHaveBeenCalledWith("/production/production-orders/po1/transitions",
      { method: "POST", body: { action: "release", reason: null, expected_version: 3 } });
    expect(onChanged).toHaveBeenCalled();
  });

  it("hold needs a reason before it can be confirmed", async () => {
    ui(<OrderStatusPanel order={order("in_progress", { actions: [action("hold", { requires_reason: true }), action("complete")] })} />);
    fireEvent.click(screen.getByRole("button", { name: "Put on hold" }));
    const dialog = screen.getByRole("dialog", { name: "Put PO-1 on hold" });
    const confirm = within(dialog).getByRole("button", { name: "Put on hold" }) as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);
    fireEvent.change(within(dialog).getByLabelText("Reason"), { target: { value: "Heater fault" } });
    await act(async () => { fireEvent.click(confirm); });
    expect(api.apiClient).toHaveBeenCalledWith("/production/production-orders/po1/transitions",
      { method: "POST", body: { action: "hold", reason: "Heater fault", expected_version: 3 } });
  });

  it("close asks for confirmation with an optional note", async () => {
    ui(<OrderStatusPanel order={order("completed", { actions: [action("close", { confirm: true })] })} />);
    fireEvent.click(screen.getByRole("button", { name: "Close order" }));
    const dialog = screen.getByRole("dialog", { name: "Close PO-1" });
    expect(within(dialog).getByLabelText("Note (optional)")).toBeTruthy();
    await act(async () => { fireEvent.click(within(dialog).getByRole("button", { name: "Close order" })); });
    expect(api.apiClient.mock.calls[0][1].body.action).toBe("close");
  });

  it("offers zero output even without permission to read the result", async () => {
    ui(<OrderStatusPanel order={order("completed", { actions: [action("close", { confirm: true })] })} />);
    fireEvent.click(screen.getByRole("button", { name: "Close order" }));
    const dialog = screen.getByRole("dialog", { name: "Close PO-1" });
    fireEvent.click(within(dialog).getByLabelText(/zero output/));
    const confirm = within(dialog).getByRole("button", { name: "Close order" }) as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);  // the reason is mandatory for zero output
    fireEvent.change(within(dialog).getByLabelText("Why was nothing produced?"), { target: { value: "Line stopped" } });
    await act(async () => { fireEvent.click(confirm); });
    expect(api.apiClient.mock.calls.every(([p]) => !String(p).endsWith("/result"))).toBe(true);
    expect(api.apiClient.mock.calls[0][1].body).toMatchObject({ action: "close", reason: "Line stopped", zero_output: true });
  });

  it("close shows the final result first and can close as zero output with a reason", async () => {
    perms.granted = new Set(["production:results:read"]);
    api.apiClient.mockImplementation((path: string) => Promise.resolve(String(path).endsWith("/result") ? {
      order: { id: "po1", number: "PO-1", status: "completed", product_type: "film", unit: "kg" }, available: true, editable: true, locked: false,
      allocation_level: "none", items: [], totals: [], entries: [], close_check: { ready: false, has_entries: false, missing_item_ids: [] }, actions: [],
    } : {}));
    ui(<OrderStatusPanel order={order("completed", { actions: [action("close", { confirm: true })] })} />);
    fireEvent.click(screen.getByRole("button", { name: "Close order" }));
    const dialog = screen.getByRole("dialog", { name: "Close PO-1" });
    fireEvent.click(await within(dialog).findByLabelText(/zero output/));
    fireEvent.change(within(dialog).getByLabelText("Why was nothing produced?"), { target: { value: "Material never arrived" } });
    await act(async () => { fireEvent.click(within(dialog).getByRole("button", { name: "Close order" })); });
    const call = api.apiClient.mock.calls.find(([p]) => String(p).endsWith("/transitions"));
    expect(call?.[1].body).toMatchObject({ action: "close", reason: "Material never arrived", expected_version: 3, zero_output: true });
  });

  it("explains a concurrent change instead of applying twice", async () => {
    const { ApiClientError } = await import("@/lib/api-client");
    api.apiClient.mockRejectedValue(new ApiClientError("conflict", 409, { detail: { code: "ORDER_STATUS_CHANGED" } }));
    ui(<OrderStatusPanel order={order("released", { actions: [action("start")] })} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Start production" })); });
    expect(screen.getByRole("alert").textContent).toContain("Someone changed this order's status");
  });

  it("flags late orders and shows actual dates; final orders offer no actions", () => {
    ui(<OrderStatusPanel order={order("released", { start_overdue: true })} />);
    expect(screen.getByText("Late to start")).toBeTruthy();
    cleanup();
    ui(<OrderStatusPanel order={order("closed", { terminal: true, actual_start_at: "2026-10-01T06:00:00Z", actual_end_at: "2026-10-02T15:00:00Z" })} />);
    expect(screen.getByText("Closed")).toBeTruthy();
    expect(screen.getByText(/can no longer change/)).toBeTruthy();
    expect(within(screen.getByRole("region", { name: "Order status" })).queryAllByRole("button")).toHaveLength(0);
  });
});

describe("order status history", () => {
  it("lists changes newest first with actor, trigger and reason", async () => {
    api.apiClient.mockResolvedValue([
      { id: "h1", from_status: "draft", to_status: "released", action: "release", trigger: "manual", actor_user_id: "u", actor_name: "Mona", reason: null, created_at: "2026-10-01T06:00:00Z" },
      { id: "h2", from_status: "released", to_status: "in_progress", action: "start", trigger: "schedule", actor_user_id: null, actor_name: null, reason: "Planned start date reached", created_at: "2026-10-02T06:00:00Z" },
    ]);
    ui(<OrderStatusTimeline orderId="po1" revision={0} />);
    const items = await screen.findAllByRole("listitem");
    expect(items[0].textContent).toContain("Automatic: planned start date reached");
    expect(items[0].textContent).toContain("Planned start date reached");
    expect(items[1].textContent).toContain("Mona");
    expect(api.apiClient).toHaveBeenCalledWith("/production/production-orders/po1/status-history");
  });
});
