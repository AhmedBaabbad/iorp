// PROD-DOWNTIME-001: machine stops — planned vs. availability loss, open/close, report figures, Arabic labels.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";
import { ApiClientError } from "@/lib/api-client";
import type { DowntimeEvent, DowntimeSummary } from "@/features/downtime-events/types";

const api = vi.hoisted(() => ({ apiClient: vi.fn() }));
const nav = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn(), params: new URLSearchParams() }));
const perms = vi.hoisted(() => ({ granted: new Set<string>() }));
vi.mock("@/lib/api-client", async importOriginal => ({ ...(await importOriginal<object>()), apiClient: api.apiClient }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: nav.push, replace: nav.replace }), usePathname: () => "/", useSearchParams: () => nav.params }));
vi.mock("@/features/auth/permission-hooks", () => ({ usePermission: (code: string) => perms.granted.has(code) }));
vi.mock("@/hooks/useFormatter", () => ({ useFormatter: () => ({ date: (v: string) => v, dateTime: (v: string) => v, number: (v: string) => v,
  quantity: (v: string, u?: string) => `${v} ${u ?? ""}`.trim(), duration: (m: number) => `${m} min` }) }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) => <main><h1>{title}</h1>{action}{children}</main> }));
vi.mock("@/features/work-centers", () => ({ getWorkCenters: () => Promise.resolve([{ id: "wc1", code: "EX1", name: "Extruder 1" }, { id: "wc2", code: "EX2", name: "Extruder 2" }]) }));

import { DowntimeEventDetail } from "@/features/downtime-events/components/DowntimeEventDetail";
import { DowntimeEventForm } from "@/features/downtime-events/components/DowntimeEventForm";
import { DowntimeEventsList } from "@/features/downtime-events/components/DowntimeEventsList";
import { OrderDowntimeSection } from "@/features/downtime-events/components/OrderDowntimeSection";

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
  perms.granted = new Set(["production:downtime_events:read", "production:downtime_events:create", "production:downtime_events:update", "production:downtime_events:delete", "production:downtime_events:close", "production:runs:read"]);
});
afterEach(cleanup);
const ui = (node: ReactNode, locale: "en" | "ar" = "en") =>
  render(<NextIntlClientProvider locale={locale} messages={locale === "en" ? en : ar} timeZone="UTC">{node}</NextIntlClientProvider>);
const respond = (handler: (path: string, options?: { method?: string; body?: unknown }) => unknown) => {
  api.apiClient.mockImplementation((path: string, options?: { method?: string; body?: unknown }) => {
    try { return Promise.resolve(handler(path, options)); } catch (e) { return Promise.reject(e); }
  });
};
const sent = (path: string, method = "POST") => api.apiClient.mock.calls.find(([p, o]) => p === path && o?.method === method)?.[1]?.body;
const page = <T,>(items: T[]) => ({ items, total: items.length, page: 1, page_size: 50, pages: items.length ? 1 : 0 });

function event(over: Partial<DowntimeEvent> = {}): DowntimeEvent {
  return { id: "d1", organization_id: "o", work_center_id: "wc1", production_order_id: null, production_run_id: null, start_time: "2026-09-29T08:00:00Z",
    end_time: null, duration_minutes: null, category: "breakdown", planned: false, reason_code: "HYD-PUMP", status: "open", created_by_user_id: "u",
    closed_by_user_id: null, updated_by_user_id: null, created_at: "2026-09-29T08:00:00Z", updated_at: "2026-09-29T08:00:00Z", notes: null,
    labels: { work_center_name: "Extruder 1", order_number: null, order_status: null, run_date: null, created_by_name: "Sara", closed_by_name: null,
      elapsed_minutes: "12.5", actions: ["close", "edit", "delete"] }, ...over };
}
const summary: DowntimeSummary = { count: 3, total_minutes: "145", planned_minutes: "30", unplanned_minutes: "115", open_count: 1, open_minutes_so_far: "12.5",
  mttr_minutes: "45", by_category: [{ category: "breakdown", planned: false, count: 2, minutes: "90" }, { category: "break_meeting", planned: true, count: 1, minutes: "30" }],
  by_work_center: [{ work_center_id: "wc1", work_center_name: "Extruder 1", count: 2, minutes: "135", unplanned_minutes: "105" },
    { work_center_id: "wc2", work_center_name: "Extruder 2", count: 1, minutes: "10", unplanned_minutes: "10" }] };

describe("downtime list and report figures", () => {
  it("shows stops with Arabic causes and the report figures for the same filters", async () => {
    respond(path => (path.includes("/summary") ? summary : path.startsWith("/production/downtime-events") ? page([event()]) : []));
    ui(<DowntimeEventsList />, "ar");
    const table = await screen.findByRole("table", { name: "قائمة أحداث التوقف" });
    expect(within(table).getByText("عطل")).toBeTruthy();
    expect(within(table).getByText("فقد في التوافر")).toBeTruthy();
    expect(within(table).getByText("13 min حتى الآن")).toBeTruthy();
    const cards = screen.getByLabelText("ملخص التوقفات");
    expect(within(cards).getByText("متوسط زمن الإصلاح").nextElementSibling?.textContent).toBe("45 min");
    expect(within(cards).getByText("فقد التوافر").nextElementSibling?.textContent).toBe("115 min");
    expect(screen.getByRole("table", { name: "التوقف حسب الماكينة" })).toBeTruthy();
    // The filter goes into the address (page 1); the list and its figures follow the address.
    fireEvent.change(screen.getByLabelText("النوع"), { target: { value: "true" } });
    expect(nav.replace).toHaveBeenCalledWith("/?planned=true", { scroll: false });
  });

  it("reads its filters and page from the address and asks one page with figures for every match", async () => {
    nav.params = new URLSearchParams("planned=true&page=2");
    respond(path => (path.includes("/summary") ? summary : path.startsWith("/production/downtime-events") ? { ...page([event()]), total: 60, page: 2, pages: 2 } : []));
    ui(<DowntimeEventsList />);
    await waitFor(() => expect(api.apiClient).toHaveBeenCalledWith("/production/downtime-events/summary?planned=true"));
    expect(api.apiClient).toHaveBeenCalledWith("/production/downtime-events?planned=true&page=2&page_size=50");
    expect(await screen.findByText(/51/)).toBeTruthy();
  });
});

describe("recording a stop", () => {
  const orders = [{ id: "po1", production_order_number: "PO-1", product_type: "film", status: "in_progress" }, { id: "po2", production_order_number: "PO-2", product_type: "film", status: "draft" }];
  beforeEach(() => {
    respond((path, o) => {
      if (o?.method === "POST") return event({ id: "new1" });
      // The picker asks the server for the orders a stop can be linked to; the server filters by status.
      if (path.startsWith("/production/production-orders/lookup")) return orders.filter(o => new URLSearchParams(path.split("?")[1]).getAll("statuses").includes(o.status));
      if (path.startsWith("/production/runs")) return [{ id: "r1", run_date: "2026-09-29", status: "in_progress", work_center_id: "wc2", production_order_id: "po1" }];
      return [];
    });
  });

  it("groups causes into availability losses and planned stops, and requires a machine", async () => {
    ui(<DowntimeEventForm />, "ar");
    const cause = await screen.findByLabelText("السبب");
    const groups = Array.from(cause.querySelectorAll("optgroup")).map(g => [g.label, Array.from(g.querySelectorAll("option")).map(o => o.textContent)]);
    expect(groups).toEqual([["فقد في التوافر", ["عطل", "تغيير المنتج والضبط", "نقص المواد", "انتظار المشغّل", "مشكلة جودة", "المرافق (كهرباء، هواء، ماء)", "أخرى"]],
      ["توقف مخطط", ["صيانة مخططة", "استراحة أو اجتماع", "لا يوجد عمل مجدول"]]]);
    expect((screen.getByRole("button", { name: "تسجيل توقف" }) as HTMLButtonElement).disabled).toBe(true);
    await waitFor(() => expect(screen.getByRole("combobox", { name: "أمر الإنتاج (اختياري)" }).querySelectorAll("option").length).toBe(2));  // the draft order is not offered
  });

  it("records an open stop on a machine, with times in UTC", async () => {
    ui(<DowntimeEventForm />);
    await waitFor(() => expect(screen.getByRole("option", { name: "EX1 — Extruder 1" })).toBeTruthy());
    fireEvent.change(screen.getByLabelText("Work center (machine)"), { target: { value: "wc1" } });
    fireEvent.change(screen.getByLabelText("Start"), { target: { value: "2026-09-29T08:00" } });
    expect(screen.getByText(/stays open \(ongoing\)/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Record downtime" }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/downtime-events/new1"));
    const body = sent("/production/downtime-events");
    expect(body).toMatchObject({ work_center_id: "wc1", production_order_id: null, category: "breakdown", end_time: null });
    expect(body.start_time).toMatch(/Z$/);
  });

  it("takes the machine and order from a run", async () => {
    nav.params = new URLSearchParams("order=po1");
    ui(<DowntimeEventForm />);
    const run = await screen.findByLabelText("Production run (optional)");
    await waitFor(() => expect((run as HTMLSelectElement).options.length).toBe(2));
    fireEvent.change(run, { target: { value: "r1" } });
    const machine = screen.getByLabelText("Work center (machine)") as HTMLSelectElement;
    expect(machine.disabled && machine.value === "wc2").toBe(true);
    fireEvent.change(screen.getByLabelText("Cause"), { target: { value: "planned_maintenance" } });
    expect(screen.getByText(/does not reduce availability/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Record downtime" }));
    await waitFor(() => expect(sent("/production/downtime-events")).toMatchObject({ production_run_id: "r1", work_center_id: null, production_order_id: null, category: "planned_maintenance" }));
  });

  it("explains an overlapping stop in Arabic", async () => {
    respond((path, o) => {
      if (o?.method === "POST") throw new ApiClientError("overlap", 409, { detail: { code: "DOWNTIME_OVERLAP" } });
      return path === "/production/production-orders" ? orders : [];
    });
    nav.params = new URLSearchParams("work_center=wc1");
    ui(<DowntimeEventForm />, "ar");
    await waitFor(() => expect((screen.getByLabelText("مركز العمل (الماكينة)") as HTMLSelectElement).value).toBe("wc1"));
    fireEvent.click(screen.getByRole("button", { name: "تسجيل توقف" }));
    expect((await screen.findByRole("alert")).textContent).toBe("لهذه الماكينة توقف في نفس الفترة. لا يكون للماكينة إلا توقف واحد في الوقت نفسه.");
  });
});

describe("stop detail", () => {
  it("ends an open stop with the chosen time", async () => {
    respond((path, o) => (o?.method === "POST" ? event({ status: "closed", end_time: "2026-09-29T08:42:00Z", duration_minutes: "42" }) : event()));
    ui(<DowntimeEventDetail eventId="d1" />);
    fireEvent.click(await screen.findByRole("button", { name: "End the stop" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("End"), { target: { value: "2026-09-29T08:42" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "End the stop" }));
    await waitFor(() => expect(sent("/production/downtime-events/d1/close")?.end_time).toMatch(/Z$/));
  });

  it("is read-only when the linked order is closed", async () => {
    respond(() => event({ production_order_id: "po1", labels: { ...event().labels!, order_number: "PO-1", order_status: "closed", actions: [] } }));
    ui(<DowntimeEventDetail eventId="d1" />);
    expect(await screen.findByText(/linked order is closed/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "End the stop" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Edit" })).toBeNull();
  });
});

describe("stops on the order page", () => {
  it("shows the order's figures and a record link while it runs", async () => {
    respond(() => summary);
    ui(<OrderDowntimeSection order={{ id: "po1", status: "in_progress" }} />, "ar");
    expect(await screen.findByText("توقفات الماكينات")).toBeTruthy();
    expect(api.apiClient).toHaveBeenCalledWith("/production/downtime-events/summary?production_order_id=po1");
    expect(screen.getByRole("link", { name: "تسجيل توقف" }).getAttribute("href")).toBe("/downtime-events/new?order=po1");
  });

  it("offers no record link once the order is closed, and nothing before it starts", async () => {
    respond(() => ({ ...summary, count: 0, open_count: 0, by_category: [], by_work_center: [] }));
    ui(<OrderDowntimeSection order={{ id: "po1", status: "closed" }} />);
    expect(await screen.findByText("No stops recorded for this order.")).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Record downtime" })).toBeNull();
    cleanup();
    ui(<OrderDowntimeSection order={{ id: "po1", status: "released" }} />);
    expect(screen.queryByText("Machine stops")).toBeNull();
  });
});
