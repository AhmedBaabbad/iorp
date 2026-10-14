// SEC-001: my sessions — this device marked, the others ended from here.
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";

const api = vi.hoisted(() => ({ call: vi.fn() }));
const nav = vi.hoisted(() => ({ replace: vi.fn(), push: vi.fn(), path: "/dashboard" }));
const auth = vi.hoisted(() => ({ user: null as null | Record<string, unknown> }));
vi.mock("@/lib/api-client", async importOriginal => ({ ...(await importOriginal<object>()), apiClient: api.call }));
vi.mock("next/navigation", () => ({ useRouter: () => nav, usePathname: () => nav.path, useSearchParams: () => new URLSearchParams() }));
vi.mock("@/hooks/useFormatter", () => ({ useFormatter: () => ({ date: (v: string) => v.slice(0, 10), dateTime: (v: string) => v.slice(0, 16) }) }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) =>
  <main><h1>{title}</h1>{action}{children}</main> }));
vi.mock("@/features/auth/auth-context", () => ({ useAuth: () => ({ isAuthenticated: true, isLoading: false, user: auth.user }) }));
import { MySessionsPage } from "@/features/auth/my-sessions-page";

const SESSIONS = [
  { id: "s1", device: "Chrome · Windows", ip_address: "10.0.0.5", started_at: "2026-10-14T08:00:00Z", last_active_at: "2026-10-14T09:00:00Z", current: true },
  { id: "s2", device: "Chrome · Android", ip_address: "10.0.0.9", started_at: "2026-10-13T08:00:00Z", last_active_at: "2026-10-13T12:00:00Z", current: false },
];
const messages: Record<string, Record<string, unknown>> = {};
beforeAll(async () => { for (const l of ["ar", "en"] as const) messages[l] = await loadMessages(l) as Record<string, unknown>; });
beforeEach(() => {
  api.call.mockReset(); nav.replace.mockReset(); nav.path = "/dashboard"; auth.user = { full_name: "Ahmed" };
  api.call.mockImplementation((path: string) => Promise.resolve(path === "/auth/sessions" ? SESSIONS : { ended: 1 }));
});
afterEach(cleanup);
const ui = (node: ReactNode) => render(<NextIntlClientProvider locale="ar" messages={messages.ar} timeZone="UTC">{node}</NextIntlClientProvider>);

it("lists my sessions with this device marked, and ends another one", async () => {
  ui(<MySessionsPage />);
  expect(await screen.findByText("Chrome · Android")).toBeTruthy();
  expect(screen.getByText("هذا الجهاز")).toBeTruthy();
  expect(screen.getAllByRole("button", { name: "إنهاء" })).toHaveLength(1);  // never this device
  await act(async () => { fireEvent.click(screen.getByRole("button", { name: "إنهاء" })); });
  await waitFor(() => expect(api.call).toHaveBeenCalledWith("/auth/sessions/end", { method: "POST", body: { session_ids: ["s2"] }, notify: false }));
});
