// MD-003: every classification the departments choose is a reference list, grouped by department; an item nothing uses
// is deleted (after confirmation), one in use shows how many records and can only be deactivated; an item the system
// writes itself is never deleted.
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";

const api = vi.hoisted(() => ({ call: vi.fn() }));
vi.mock("@/lib/api-client", async importOriginal => ({ ...(await importOriginal<object>()), apiClient: api.call }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/", useSearchParams: () => new URLSearchParams() }));
vi.mock("@/features/auth/permission-hooks", () => ({ usePermission: () => true, useHasAnyPermission: () => true }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ title, children }: { title: string; children: ReactNode }) => <main><h1>{title}</h1>{children}</main> }));
import { ReferenceLists } from "@/features/masterdata/components/ReferenceLists";

const item = (key: string, name_ar: string, uses: number, extra = {}) =>
  ({ id: `id-${key}`, list: "rejection_reason", key, name_ar, name_en: key, parent_key: null, active: true, sort_order: 1, uses, protected: false, ...extra });
const REASONS = [item("critical_defect", "عيب حرج", 0), item("surface_failure", "فشل السطح", 12), item("out_of_spec", "خارج المواصفات", 0, { protected: true })];

const messages: Record<string, Record<string, unknown>> = {};
beforeAll(async () => { for (const l of ["ar", "en"] as const) messages[l] = await loadMessages(l) as Record<string, unknown>; });
beforeEach(() => {
  api.call.mockReset();
  api.call.mockImplementation((path: string, options?: { method?: string }) => Promise.resolve(
    options?.method === "DELETE" ? { deleted: 1 } : path.includes("list=rejection_reason") ? REASONS : path.includes("/legacy") ? [] : []));
});
afterEach(cleanup);
const ui = () => render(<NextIntlClientProvider locale="ar" messages={messages.ar} timeZone="UTC"><ReferenceLists initialList="rejection_reason" /></NextIntlClientProvider>);

it("groups the lists by department and names the new classifications", async () => {
  ui();
  for (const group of ["المبيعات والعملاء", "المشتريات", "الإنتاج", "الجودة", "الشحن"]) expect(screen.getByText(group)).toBeTruthy();
  for (const name of ["فئات الموردين", "فئات المواد", "فئات العيوب", "أسباب الرفض", "فئات الشكاوى", "أنواع التواصل مع العملاء", "أنواع المركبات"]) {
    expect(screen.getByRole("button", { name })).toBeTruthy();
  }
  expect(await screen.findByText("عيب حرج")).toBeTruthy();
});

it("deletes only what nothing uses, says why otherwise", async () => {
  ui();
  await screen.findByText("عيب حرج");
  const rows = screen.getAllByRole("row");
  const buttonIn = (text: string) => rows.find(r => r.textContent?.includes(text))!.querySelector("button[title], button:not([title])") as HTMLButtonElement;
  const deleteIn = (text: string) => [...rows.find(r => r.textContent?.includes(text))!.querySelectorAll("button")].find(b => b.textContent === "حذف") as HTMLButtonElement;
  expect(buttonIn("عيب حرج")).toBeTruthy();
  expect(deleteIn("فشل السطح").disabled).toBe(true);
  expect(screen.getByText("مستخدم في 12 سجلًا — يمكن إيقافه فقط")).toBeTruthy();
  expect(deleteIn("خارج المواصفات").disabled).toBe(true);
  expect(screen.getAllByText("يستخدمه النظام تلقائيًا — يمكن تعديل اسمه فقط").length).toBeGreaterThan(0);

  vi.spyOn(window, "confirm").mockReturnValue(true);
  await act(async () => { fireEvent.click(deleteIn("عيب حرج")); });
  await waitFor(() => expect(api.call).toHaveBeenCalledWith("/masterdata/lists/items/id-critical_defect", { method: "DELETE" }));
  expect(await screen.findByText("تم حذف البند.")).toBeTruthy();
});
