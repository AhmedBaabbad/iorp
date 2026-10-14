// ORG-AUDIT-002: the audit trail, the security log and the activity log read as sentences in the screen's language —
// never a raw code, an untranslated key or an id — and their details show as labelled values, before → after.
import { cleanup, fireEvent, render, renderHook, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";

const api = vi.hoisted(() => ({ call: vi.fn() }));
vi.mock("@/lib/api-client", () => ({ apiClient: api.call }));
const files = vi.hoisted(() => ({ download: vi.fn() }));
vi.mock("@/lib/download", () => ({ downloadFile: files.download }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/", useSearchParams: () => new URLSearchParams() }));
vi.mock("@/hooks/useFormatter", () => ({ useFormatter: () => ({ date: (v: string) => v.slice(0, 10), dateTime: (v: string) => v.slice(0, 16) }) }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ title, children }: { title: string; children: ReactNode }) => <main><h1>{title}</h1>{children}</main> }));
vi.mock("@/features/auth/permission-hooks", () => ({ usePermission: () => true, useHasAnyPermission: () => true }));
vi.mock("@/features/auth", () => ({ useAuth: () => ({ hasPermission: () => true }) }));
vi.mock("@/features/platform/platform-auth-context", () => ({ useOptionalPlatformAuth: () => null }));
import { AuditLogDetailPage, AuditLogPage } from "@/features/admin-audit/AuditLogPage";
import { useOperationText } from "@/features/logs/log-words";
import { SeparatedLogPage } from "@/features/logs/SeparatedLogPages";

const page = <T,>(items: T[]) => ({ items, total: items.length, page: 1, page_size: 50, pages: 1 });
const ROLE_GIVEN = { id: "a1", created_at: "2026-10-13T09:00:00Z", action: "role_assignment.added", entity_type: "role_assignment", entity_id: "u1",
  entity_name: "Omar", actor_id: "x", actor_name: "Ahmed Baabbad", details: { role_name: "مندوب مبيعات", user_name: "omar" }, permission_names: {} };
const LANGUAGE = { ...ROLE_GIVEN, id: "a2", action: "user.updated", entity_type: "user", details: { preferred_locale: { before: null, after: "en" } } };
const PERMISSION = { ...ROLE_GIVEN, id: "a3", action: "role.permissions_updated", entity_type: "role", entity_name: "Approvers",
  details: { permission: "procurement:purchase_orders:approve", operation: "added", scope: "organization" },
  permission_names: { "procurement:purchase_orders:approve": { ar: "اعتماد أوامر الشراء", en: "Approve purchase orders" } } };

let archived = false;
const messages: Record<string, Record<string, unknown>> = {};
beforeAll(async () => { for (const l of ["ar", "en"] as const) messages[l] = await loadMessages(l) as Record<string, unknown>; });
beforeEach(() => {
  api.call.mockReset(); files.download.mockReset(); archived = false;
  api.call.mockImplementation((path: string) => Promise.resolve(
    path.startsWith("/admin/audit-log/a2") ? LANGUAGE : path.startsWith("/admin/audit-log/a3") ? PERMISSION
      : path.startsWith("/admin/audit-log?") ? page([ROLE_GIVEN])
      : path === "/admin/activity-log/actors" ? [{ id: "u1", name: "Sara" }]
      : path === "/admin/activity-log/archive" ? [{ month: "2025-09", rows: 1200, due_on: "2026-10-01", delete_on: "2026-10-31", downloaded_at: archived ? "2026-10-13T10:00:00Z" : null, downloaded_by_name: archived ? "Ahmed Baabbad" : null }]
      : path === "/admin/activity-log/archive/2025-09/delete" ? { month: "2025-09", rows: 1200 }
      : path === "/admin/activity-log/kinds" ? ["production_order.status_changed", "list_item.created.city"]
      : path.startsWith("/admin/activity-log?") ? page([{ id: "e1", created_at: "2026-10-13T10:00:00Z", action: "production_order.status_changed",
          entity_type: "production_order", entity_id: "p3", entity_name: "PO-2026-0003", actor_name: "Sara", details: { from_status: "draft", to_status: "released", trigger: "manual", order_id: "3f2a1c4e-0000-4000-8000-000000000001" } }])
      : path === "/admin/security-log/kinds" ? ["tenant.login_success"]
      : path.startsWith("/admin/security-log?") ? page([{ id: "s1", created_at: "2026-10-13T08:00:00Z", event_type: "tenant.login_success",
          actor_name: "Ahmed Baabbad", actor_email: "a@x.com", ip_address: "10.0.0.5", details: null, occurrences: 5, last_seen_at: "2026-10-13T20:16:00Z" }])
      : null));
});
afterEach(cleanup);
const ui = (node: ReactNode, locale: "ar" | "en" = "ar") => render(<NextIntlClientProvider locale={locale} messages={messages[locale]} timeZone="UTC">{node}</NextIntlClientProvider>);
const noRawCode = () => expect(document.body.textContent).not.toMatch(/[a-z]+_[a-z_]+\.|tenantAudit\.|\b[a-z_]+\.[a-z_]+\b/);

it("the audit trail reads in Arabic: what, on whom, by whom", async () => {
  ui(<AuditLogPage />);
  expect(await screen.findByRole("link", { name: "منح دور لمستخدم" })).toBeTruthy();
  expect(screen.getByText("Ahmed Baabbad")).toBeTruthy();
  expect(screen.getByText("Omar")).toBeTruthy();
  noRawCode();
});

it("a change shows its values before and after, and a permission by its name", async () => {
  ui(<AuditLogDetailPage id="a2" />);
  expect(await screen.findByText("لغة الواجهة")).toBeTruthy();
  expect(screen.getByText("فارغ ← الإنجليزية")).toBeTruthy();
  cleanup();
  ui(<AuditLogDetailPage id="a3" />, "en");
  expect(await screen.findByText("Approve purchase orders")).toBeTruthy();
  expect(screen.getByText("whole organization")).toBeTruthy();
  noRawCode();
});

it("the activity log composes each operation and hides ids from its details", async () => {
  ui(<SeparatedLogPage scope="tenant" kind="activity" namespace="tenantActivity" permission="foundation:activity_log:read" />);
  expect(await screen.findByRole("cell", { name: "تغيير حالة أمر إنتاج" })).toBeTruthy();
  expect(screen.getByRole("option", { name: "إنشاء بند في قائمة مرجعية (المدن)" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "عرض التفاصيل" }));
  expect(screen.getByText("مسودة")).toBeTruthy();
  expect(screen.getByText("معتمد")).toBeTruthy();
  expect(screen.getByText("يدويًا")).toBeTruthy();
  expect(document.body.textContent).not.toContain("3f2a1c4e");
  noRawCode();
});

it("the security log names the person and the device", async () => {
  ui(<SeparatedLogPage scope="tenant" kind="security" namespace="tenantSecurity" permission="foundation:security_log:read" />);
  expect((await screen.findAllByText("تسجيل دخول ناجح")).length).toBeGreaterThan(0);
  expect(screen.getByText("Ahmed Baabbad")).toBeTruthy();
  expect(screen.getByText("10.0.0.5")).toBeTruthy();
  expect(screen.getByText("5 مرات، آخرها 2026-10-13T20:16")).toBeTruthy();  // repeated sign-ins counted on one entry
  expect(api.call).toHaveBeenCalledWith(expect.stringContaining("important=true"));  // opens on what matters
  expect((screen.getByRole("combobox", { name: "النوع" }) as HTMLSelectElement).value).toBe("__important");
});

it("any operation the system may write reads as words, in both languages", () => {
  const written = ["customer.created", "followup.reopened", "goods_receipt.received", "list_item.created.sector", "ncr_report.action_added",
    "ncr_report.effectiveness_review", "production_allocation.released", "production_downtime.closed", "production_order.allocation_added",
    "production_result.corrected", "production_waste.created", "purchase_order.approve", "quality_certificate.revoked", "quality_check.started",
    "quality_rejection.executed", "quality_specification.activated", "return.requested", "shift_roster.member_removed", "shipment.partially_delivered",
    "supplier.conditional", "workforce_member.user_linked", "product.legacy_mapped", "work_center.deleted", "interaction.updated", "material.created"];
  for (const locale of ["ar", "en"] as const) {
    const { result } = renderHook(() => useOperationText(), {
      wrapper: ({ children }) => <NextIntlClientProvider locale={locale} messages={messages[locale]} timeZone="UTC">{children}</NextIntlClientProvider> });
    for (const code of written) {
      const text = result.current(code);
      expect(text, code).not.toMatch(/[._]/);
      expect(text, code).not.toBe(locale === "ar" ? "عملية في النظام" : "An operation in the system");
    }
    expect(result.current("something.unheard_of")).toBe(locale === "ar" ? "عملية في النظام" : "An operation in the system");
  }
});

it("the activity log reads by department and person, opens a record, and archives a month past its retention", async () => {
  ui(<SeparatedLogPage scope="tenant" kind="activity" namespace="tenantActivity" permission="foundation:activity_log:read" />);
  expect(await screen.findByRole("link", { name: "PO-2026-0003" })).toBeTruthy();
  expect((await screen.findByRole("option", { name: "Sara" }))).toBeTruthy();
  fireEvent.change(screen.getByRole("combobox", { name: "القسم" }), { target: { value: "quality" } });
  await vi.waitFor(() => expect(api.call).toHaveBeenCalledWith(expect.stringContaining("area=quality")));
  expect(await screen.findByText("سبتمبر 2025")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "تأكدت من حفظ الملف — احذف" })).toBeNull();  // not before downloading
  archived = true;
  fireEvent.click(screen.getByRole("button", { name: "تنزيل الأرشيف" }));
  await vi.waitFor(() => expect(files.download).toHaveBeenCalledWith("/admin/activity-log/archive/2025-09/download?locale=ar", "activity-2025-09.zip"));
  const remove = await screen.findByRole("button", { name: "تأكدت من حفظ الملف — احذف" });
  vi.spyOn(window, "confirm").mockReturnValue(true);
  fireEvent.click(remove);
  await vi.waitFor(() => expect(api.call).toHaveBeenCalledWith("/admin/activity-log/archive/2025-09/delete", { method: "POST", notify: false }));
});
