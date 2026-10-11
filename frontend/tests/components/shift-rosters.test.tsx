// Shift rosters page: only the create action above the table, and team members listed per roster.
import { cleanup, render, screen, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";

const api = vi.hoisted(() => ({ apiClient: vi.fn() }));
const auth = vi.hoisted(() => ({ permissions: [] as string[] }));
vi.mock("@/lib/api-client", async importOriginal => ({ ...(await importOriginal<object>()), apiClient: api.apiClient }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/", useSearchParams: () => new URLSearchParams() }));
vi.mock("@/features/auth/auth-context", () => ({
  useAuth: () => ({ permissions: auth.permissions }),
  hasPermission: (granted: string[], code: string) => granted.includes(code),
}));

import { ExecutionPanel } from "@/features/production-execution/ExecutionPanel";

const roster = {
  id: "r1", name: "Morning team", shift_definition_id: "s1", shift_name: "Morning", effective_from: "2026-09-27", effective_to: "2026-10-09",
  status: "active", period_state: "current", members_editable: true, team_count: 2,
  members: [
    { id: "m1", workforce_member_id: "w1", workforce_name: "Ali Hassan", employee_code: "E1", is_shift_lead: true },
    { id: "m2", workforce_member_id: "w2", workforce_name: "Omar Saleh", employee_code: "E2", is_shift_lead: false },
  ],
};
const workers = [{ id: "w1", full_name: "Ali Hassan", employee_code: "E1", status: "active" }];

let messages: Record<string, unknown>;
beforeAll(async () => { messages = await loadMessages("en") as Record<string, unknown>; });
beforeEach(() => {
  auth.permissions = ["production:shift_rosters:read", "production:shift_rosters:create", "production:shift_rosters:manage_members", "production:shifts:read", "workforce:members:read"];
  api.apiClient.mockReset();
  api.apiClient.mockImplementation((path: string) => Promise.resolve(
    path.startsWith("/production/shift-rosters") ? { items: [roster], total: 1, page: 1, page_size: 50, pages: 1 } : path.startsWith("/workforce-members") ? workers : []));
});
afterEach(cleanup);

const ui = (node: ReactNode) => render(<NextIntlClientProvider locale="en" messages={messages} timeZone="UTC">{node}</NextIntlClientProvider>);

describe("shift rosters page", () => {
  it("shows only the create action above the table, without worker or date filters", async () => {
    ui(<ExecutionPanel />);
    expect(await screen.findByText("Ali Hassan (Lead)")).toBeTruthy();
    expect(screen.queryByRole("combobox", { name: "Worker" })).toBeNull();
    expect(screen.queryByLabelText("From")).toBeNull();
    expect(screen.queryByLabelText("To")).toBeNull();
    expect(screen.getByRole("button", { name: "Create" })).toBeTruthy();
    const listCalls = api.apiClient.mock.calls.map(([path]) => String(path)).filter(path => path.startsWith("/production/shift-rosters"));
    expect(listCalls.every(path => !/workforce_member_id|date_from|date_to/.test(path))).toBe(true);
  });

  it("lists each roster's team members in the table", async () => {
    ui(<ExecutionPanel />);
    const lead = await screen.findByText("Ali Hassan (Lead)");
    const cell = lead.closest("td")!;
    expect(within(cell).getByText("Omar Saleh")).toBeTruthy();
  });

  it("says when a roster has no members yet", async () => {
    api.apiClient.mockImplementation((path: string) => Promise.resolve(path.startsWith("/production/shift-rosters")
      ? { items: [{ ...roster, members: [], team_count: 0 }], total: 1, page: 1, page_size: 50, pages: 1 } : []));
    ui(<ExecutionPanel />);
    expect(await screen.findByText("No members yet")).toBeTruthy();
  });

  it("keeps the worker filter for production runs on an order", async () => {
    auth.permissions = ["production:runs:read", "workforce:members:read"];
    api.apiClient.mockImplementation((path: string) => Promise.resolve(path.startsWith("/workforce-members") ? workers : []));
    ui(<ExecutionPanel orderId="po1" />);
    expect(await screen.findByRole("combobox", { name: "Worker" })).toBeTruthy();
  });
});
