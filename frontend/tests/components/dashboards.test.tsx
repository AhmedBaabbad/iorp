// DASH-001: a section's dashboard — figure cards with the change from the previous period and today, the trend chart,
// what waits for someone, and the period kept in the address.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";

const api = vi.hoisted(() => ({ apiClient: vi.fn() }));
const nav = vi.hoisted(() => ({ replace: vi.fn(), params: new URLSearchParams() }));
vi.mock("@/lib/api-client", async importOriginal => ({ ...(await importOriginal<object>()), apiClient: api.apiClient }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: nav.replace }), usePathname: () => "/production",
  useSearchParams: () => nav.params }));
vi.mock("@/hooks/useFormatter", () => ({ useFormatter: () => ({ date: (v: string) => v.slice(0, 10), dateTime: (v: string) => v,
  number: (v: number) => String(v), decimal: (v: number, p = 2) => Number(v).toFixed(p) }) }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) =>
  <main><h1>{title}</h1>{action}{children}</main> }));

import { ProductionDashboard } from "@/features/production-dashboard/ProductionDashboard";

let en: Record<string, unknown>;
beforeAll(async () => { en = await loadMessages("en") as Record<string, unknown>; });
beforeEach(() => { api.apiClient.mockReset(); nav.replace.mockReset(); nav.params = new URLSearchParams(); });
afterEach(cleanup);
const ui = (node: ReactNode) => render(<NextIntlClientProvider locale="en" messages={en} timeZone="UTC">{node}</NextIntlClientProvider>);

const board = {
  module: "production", period: "3m", start: "2026-07-10", end: "2026-10-07", attention_total: 2,
  cards: [
    { key: "produced", value: "3400", previous: "2000", today: "900", unit: "kg", good_when: "up", href: "/production-results" },
    { key: "scrap_rate", value: "2.9", previous: "3.5", today: null, unit: "%", good_when: "down" },
    { key: "downtime", value: "4.0", previous: "2.0", today: "1.0", unit: "h", good_when: "down" },
    { key: "completed_orders", value: "1", previous: "0", today: "0", unit: null, good_when: "up" },
  ],
  series: [{ key: "produced", unit: "kg", points: [{ date: "2026-10-05", value: "100" }, { date: "2026-10-06", value: "300" }] },
           { key: "scrap", unit: "kg", points: [{ date: "2026-10-05", value: "5" }, { date: "2026-10-06", value: "9" }] }],
  attention: [{ kind: "open_downtime", id: "d1", label: "Extruder 1", detail: "breakdown", date: "2026-10-07", href: "/downtime-events/d1", severity: "danger" },
              { kind: "overdue_order", id: "o1", label: "PO-0042", detail: "Line 2", date: "2026-10-04", href: "/production-orders/o1", severity: "danger" }],
};

describe("production dashboard", () => {
  it("shows each figure against the previous period, today, the chart and what waits", async () => {
    api.apiClient.mockResolvedValue(board);
    ui(<ProductionDashboard />);
    const produced = (await screen.findByText("Good output", { selector: "h2" })).closest("a")!;
    expect(produced.getAttribute("href")).toBe("/production-results");
    expect(within(produced).getByText("Past 3 months")).toBeTruthy();
    expect(within(produced).getByText("▲ 70.0%")).toBeTruthy();  // 3400 against 2000: up, and up is good
    const scrap = screen.getByText("Loss rate", { selector: "h2" }).parentElement!;
    expect(within(scrap).getByText("▼ 0.6 pts")).toBeTruthy();   // a rate changes in points
    expect(within(scrap).getByText("▼ 0.6 pts").className).toMatch(/good/);  // scrap going down is good news
    const downtime = screen.getByText("Downtime hours", { selector: "h2" }).parentElement!;
    expect(within(downtime).getByText("▲ 100.0%").className).toMatch(/bad/);
    expect(screen.getByRole("button", { name: "Scrap" })).toBeTruthy();  // the legend
    const table = screen.getByRole("region", { name: "Needs your attention" });
    expect(within(table).getByRole("link", { name: "PO-0042" }).getAttribute("href")).toBe("/production-orders/o1");
    expect(api.apiClient).toHaveBeenCalledWith("/production/dashboard?period=3m");
  });

  it("keeps the chosen period in the address", async () => {
    api.apiClient.mockResolvedValue(board);
    ui(<ProductionDashboard />);
    fireEvent.click(await screen.findByRole("button", { name: "6M" }));
    expect(nav.replace).toHaveBeenCalledWith("/production?period=6m", { scroll: false });
  });
});
