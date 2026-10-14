// PROJECT-NOTIFY-001: the bell shows the unread count; its panel reads each notification in the screen's language, with
// who did it; opening one marks it read and goes to its document; an announcement requiring acknowledgement stays in
// front of the reader until confirmed; an announcement is written to a role and its author is told how many received it.
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";

const api = vi.hoisted(() => ({ call: vi.fn() }));
const nav = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
vi.mock("@/lib/api-client", () => ({ apiClient: api.call }));
vi.mock("next/navigation", () => ({ useRouter: () => nav, usePathname: () => "/", useSearchParams: () => new URLSearchParams() }));
vi.mock("@/hooks/useFormatter", () => ({ useFormatter: () => ({ date: (v: string) => v, dateTime: (v: string) => v }) }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ title, children }: { title: string; children: ReactNode }) => <main><h1>{title}</h1>{children}</main> }));
import { AcknowledgeGate, NotificationBell } from "@/components/notify/NotificationCenter";
import { Notifications, dismiss } from "@/components/notify/Notifications";
import { AnnouncementForm } from "@/features/announcements/Announcements";

const now = new Date().toISOString();
const PO = { id: "n1", event: "procurement.purchase_order.awaiting_approval", category: "work", severity: "important",
  params: { number: "PO-2026-0007", supplier: "Gulf Resins" }, link: "/purchase-orders/p7", actor_name: "Sara Ali", created_at: now,
  read: false, settled: false, announcement: null };
const ROLE = { ...PO, id: "n2", event: "foundation.role.assigned", category: "access", severity: "important", params: { role: "Quality Manager" },
  link: "/admin/profile", read: true };
const POLICY = { ...PO, id: "n3", event: "notifications.announcement.published", category: "announcement", severity: "urgent", params: { title: "Safety first" },
  link: "/notifications", actor_name: "Org Admin", announcement: { id: "a1", title: "Safety first", body: "Wear the helmet in hall B.", requires_ack: true, acknowledged: false } };
let summary = { unread: 1, latest: [PO, ROLE], pending_ack: [] as typeof POLICY[] };

const messages: Record<string, Record<string, unknown>> = {};
beforeAll(async () => { for (const l of ["ar", "en"] as const) messages[l] = await loadMessages(l) as Record<string, unknown>; });
beforeEach(() => {
  api.call.mockReset(); nav.push.mockReset();
  summary = { unread: 1, latest: [PO, ROLE], pending_ack: [] };
  api.call.mockImplementation((path: string, options?: { method?: string; body?: Record<string, unknown> }) => {
    if (path === "/notifications/summary") return Promise.resolve(summary);
    if (path.endsWith("/read")) { summary = { ...summary, unread: 0, latest: summary.latest.map((n) => ({ ...n, read: true })) }; return Promise.resolve({}); }
    if (path.endsWith("/acknowledge")) { summary = { ...summary, pending_ack: [] }; return Promise.resolve({}); }
    if (path === "/announcements/options") return Promise.resolve({ users: [{ id: "u1", name: "Sara Ali" }], roles: [{ id: "r1", code: "qm", name: "Quality" }] });
    if (path === "/announcements" && options?.method === "POST") return Promise.resolve({ id: "a9", recipient_count: 3 });
    return Promise.resolve(null);
  });
});
afterEach(() => { cleanup(); for (let id = 0; id < 200; id++) dismiss(id); });
const ui = (node: ReactNode, locale: "ar" | "en" = "ar") =>
  render(<NextIntlClientProvider locale={locale} messages={messages[locale]} timeZone="UTC">{node}<Notifications /></NextIntlClientProvider>);

it("rings with the unread count and reads each notification in Arabic, with who did it", async () => {
  ui(<NotificationBell />);
  const bell = await screen.findByRole("button", { name: /الإشعارات — إشعار واحد غير مقروء/ });
  expect(bell.textContent).toContain("1");
  fireEvent.click(bell);
  expect(screen.getByText("أمر الشراء PO-2026-0007 (Gulf Resins) بانتظار اعتمادك. أعدّه Sara Ali.")).toBeTruthy();
  expect(screen.getByText("منحك Sara Ali دور «Quality Manager».")).toBeTruthy();
  fireEvent.click(screen.getByRole("tab", { name: "غير المقروءة" }));
  expect(screen.queryByText(/Quality Manager/)).toBeNull();
});

it("opening a notification marks it read and goes to its document", async () => {
  ui(<NotificationBell />, "en");
  fireEvent.click(await screen.findByRole("button", { name: /Notifications — 1 unread notification/ }));
  fireEvent.click(screen.getByText(/Purchase order PO-2026-0007/));
  await waitFor(() => expect(api.call).toHaveBeenCalledWith("/notifications/n1/read", { method: "POST", notify: false }));
  await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/purchase-orders/p7"));
});

it("keeps an announcement requiring acknowledgement in front until the reader confirms", async () => {
  summary = { ...summary, pending_ack: [POLICY] };
  ui(<AcknowledgeGate />);
  const dialog = await screen.findByRole("alertdialog");
  expect(dialog.textContent).toContain("Wear the helmet in hall B.");
  expect(dialog.textContent).toContain("من Org Admin");
  await act(async () => { fireEvent.click(screen.getByRole("button", { name: "اطّلعت عليه" })); });
  await waitFor(() => expect(api.call).toHaveBeenCalledWith("/notifications/n3/acknowledge", { method: "POST", notify: false }));
  await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
  expect(await screen.findByText("تم تسجيل تأكيد اطلاعك.")).toBeTruthy();
});

it("sends an announcement to a role's members and says how many received it", async () => {
  ui(<AnnouncementForm />);
  fireEvent.change(await screen.findByLabelText("العنوان"), { target: { value: "تحديث سياسة الجودة" } });
  fireEvent.change(screen.getByLabelText("الرسالة"), { target: { value: "يرجى قراءة السياسة الجديدة." } });
  fireEvent.change(screen.getByLabelText("إرسال إلى"), { target: { value: "role" } });
  fireEvent.change(await screen.findByLabelText("الدور"), { target: { value: "r1" } });
  fireEvent.click(screen.getByLabelText("يجب أن يؤكد القارئ اطلاعه"));
  await act(async () => { fireEvent.click(screen.getByRole("button", { name: "إرسال الإعلان" })); });
  await waitFor(() => expect(api.call).toHaveBeenCalledWith("/announcements", expect.objectContaining({ method: "POST",
    body: expect.objectContaining({ audience: "role", role_id: "r1", requires_ack: true, user_ids: [] }) })));
  expect(await screen.findByText("تم إرسال الإعلان إلى 3 أشخاص.")).toBeTruthy();
  expect(nav.push).toHaveBeenCalledWith("/admin/announcements/a9");
});
