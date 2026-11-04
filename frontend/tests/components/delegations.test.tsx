// PROJECT-GOV-004: governed delegations — a holder asks, a manager agrees (or the holder agrees to a manager's
// proposal). The list is paged by the server and shows what waits for the user's answer; a new delegation has its own
// page; every action ends with a notification in the screen's language.
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";

const api = vi.hoisted(() => ({ call: vi.fn() }));
const nav = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
vi.mock("@/lib/api-client", () => ({ apiClient: api.call }));
vi.mock("next/navigation", () => ({ useRouter: () => nav, usePathname: () => "/admin/delegations", useSearchParams: () => new URLSearchParams() }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) =>
  <main><h1>{title}</h1>{action}{children}</main> }));
vi.mock("@/hooks/useFormatter", () => ({ useFormatter: () => ({ date: (v: string) => v, dateTime: (v: string) => v }) }));
import { DelegationForm, DelegationsPage } from "@/features/delegations/DelegationsPage";
import { Notifications, dismiss } from "@/components/notify/Notifications";

const base = { delegator_name: "Production Manager", delegate_name: "Deputy Planner", permission_code: "procurement:purchase_orders:approve",
  effective_from: "2026-10-01", effective_to: "2026-10-31", reason: "Annual leave", usable: true, created_by_name: "Production Manager",
  decided_by_name: null, decision_reason: null, revoked_at: null, revoked_by_name: null, revoke_reason: null };
const ACTIVE = { ...base, id: "d1", status: "active", decided_by_name: "Org Admin", can_answer: false, can_revoke: true };
const WAITING = { ...base, id: "d2", status: "awaiting_manager", usable: false, can_answer: true, can_revoke: true };
let OPTIONS = { delegators: [{ id: "m1", name: "Production Manager", permissions: ["procurement:purchase_orders:approve"] }],
  delegates: [{ id: "m1", name: "Production Manager" }, { id: "u2", name: "Deputy Planner" }], manages: false };
const messages: Record<string, Record<string, unknown>> = {};
beforeAll(async () => { for (const l of ["ar", "en"] as const) messages[l] = await loadMessages(l) as Record<string, unknown>; });
beforeEach(() => {
  // Fake Date only: Testing Library polling and notification timers stay real.
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-10-15T12:00:00Z"));
  api.call.mockReset(); nav.push.mockReset();
  api.call.mockImplementation((path: string, options?: { method?: string }) => Promise.resolve(
    path.endsWith("/options") ? OPTIONS : path.endsWith("/waiting") ? { count: 1, items: [WAITING] }
      : path.startsWith("/delegations?") ? { items: [WAITING, ACTIVE], total: 2, page: 1, page_size: 50, pages: 1 }
      : options?.method === "POST" ? { ...WAITING, status: "awaiting_manager" } : null));
});
afterEach(() => { cleanup(); for (let id = 0; id < 100; id++) dismiss(id); vi.useRealTimers(); });
const ui = (page: ReactNode, locale: "ar" | "en" = "en") =>
  render(<NextIntlClientProvider locale={locale} messages={messages[locale]} timeZone="UTC">{page}<Notifications /></NextIntlClientProvider>);

it("lists one server page, with what waits for the user's answer, in the screen's language", async () => {
  ui(<DelegationsPage />, "ar");
  expect(await screen.findByText(/\(1\)/)).toBeTruthy();
  expect(api.call).toHaveBeenCalledWith("/delegations?page=1&page_size=50");
  expect(screen.getByRole("cell", { name: /ساري/ })).toBeTruthy();
  expect(screen.getByRole("link", { name: "تفويض اعتماد" }).getAttribute("href")).toBe("/admin/delegations/new");
});

it("a holder asks on the new-delegation page, is told it awaits a manager, and returns to the list", async () => {
  OPTIONS = { ...OPTIONS, manages: false };
  ui(<DelegationForm />, "ar");
  const from = await screen.findByLabelText("بالتفويض عن") as HTMLSelectElement;
  await waitFor(() => expect(from.value).toBe("m1"));
  expect(from.disabled).toBe(true);
  const to = screen.getByLabelText("المفوَّض إليه") as HTMLSelectElement;
  expect([...to.options].map((o) => o.value)).toEqual(["", "u2"]);
  fireEvent.change(screen.getByLabelText("الاعتماد"), { target: { value: "procurement:purchase_orders:approve" } });
  fireEvent.change(to, { target: { value: "u2" } });
  fireEvent.change(screen.getByLabelText(/^إلى/), { target: { value: "2026-10-31" } });
  fireEvent.change(screen.getByLabelText("السبب"), { target: { value: "إجازة سنوية" } });
  await act(async () => { fireEvent.click(screen.getByRole("button", { name: "إرسال للموافقة" })); });
  await waitFor(() => expect(api.call).toHaveBeenCalledWith("/delegations", expect.objectContaining({ method: "POST",
    body: expect.objectContaining({ delegator_user_id: "m1", delegate_user_id: "u2", permission_code: "procurement:purchase_orders:approve" }) })));
  expect(await screen.findByText("تم إرسال طلب التفويض، وهو بانتظار موافقة مدير التفويضات.")).toBeTruthy();
  expect(nav.push).toHaveBeenCalledWith("/admin/delegations");
});

it("approves at once and rejects with a reason, each with its message", async () => {
  ui(<DelegationsPage />);
  fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
  await waitFor(() => expect(api.call).toHaveBeenCalledWith("/delegations/d2/approve", { method: "POST", body: { reason: "" } }));
  expect(await screen.findByText("The delegation is approved and in force.")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Reject" }));
  fireEvent.change(screen.getByLabelText("Why it is rejected"), { target: { value: "No cover needed" } });
  fireEvent.click(screen.getAllByRole("button", { name: "Reject" }).at(-1)!);
  await waitFor(() => expect(api.call).toHaveBeenCalledWith("/delegations/d2/reject", { method: "POST", body: { reason: "No cover needed" } }));
  expect(await screen.findByText("The delegation was rejected.")).toBeTruthy();
});
