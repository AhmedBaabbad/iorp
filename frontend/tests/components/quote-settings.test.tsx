// QUOTE-DOC-002: the quotation language — the settings are written in it, and every quotation is printed in it.
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";
import type { QuoteSettings } from "@/features/quotes/types";

const api = vi.hoisted(() => ({ apiClient: vi.fn() }));
vi.mock("@/lib/api-client", async importOriginal => ({ ...(await importOriginal<object>()), apiClient: api.apiClient }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/", useSearchParams: () => new URLSearchParams() }));
vi.mock("@/features/auth/permission-hooks", () => ({ usePermission: () => true, useHasAnyPermission: () => true }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ title, children }: { title: string; children: ReactNode }) => <main><h1>{title}</h1>{children}</main> }));

import { QuoteDocumentButtons } from "@/features/quotes/components/QuoteDocumentButtons";
import { QuoteSettingsPage } from "@/features/quotes/components/QuoteSettingsPage";

let ar: Record<string, unknown>;
beforeAll(async () => { ar = await loadMessages("ar") as Record<string, unknown>; });
beforeEach(() => { api.apiClient.mockReset(); });
afterEach(cleanup);
const ui = (node: ReactNode) => render(<NextIntlClientProvider locale="ar" messages={ar} timeZone="UTC">{node}</NextIntlClientProvider>);

const settings: QuoteSettings = { document_language: "ar", signature_title_ar: "مدير المبيعات", signature_title_en: "Sales Manager", show_preparer_name: false,
  terms: [{ title_ar: "الدفع", title_en: null, body_ar: "بعد شهر من الفاتورة", body_en: null, is_active: true },
    { title_ar: "التسليم", title_en: "Delivery", body_ar: "خلال 10 أيام", body_en: "Within 10 days", is_active: true }] };

describe("quotation settings", () => {
  it("shows only the chosen language and keeps the other one", async () => {
    api.apiClient.mockImplementation((_path: string, o?: { method?: string; body?: unknown }) => Promise.resolve(o?.method ? o.body : settings));
    ui(<QuoteSettingsPage />);
    expect((await screen.findByLabelText("المسمى") as HTMLInputElement).value).toBe("مدير المبيعات");
    expect(screen.getAllByLabelText("العنوان").map(i => (i as HTMLInputElement).value)).toEqual(["الدفع", "التسليم"]);
    expect(screen.queryByDisplayValue("Sales Manager")).toBeNull();
    fireEvent.click(screen.getByLabelText("الإنجليزية"));
    expect((screen.getByLabelText("المسمى") as HTMLInputElement).value).toBe("Sales Manager");
    expect(screen.getAllByLabelText("العنوان").map(i => (i as HTMLInputElement).value)).toEqual(["", "Delivery"]);
    expect(screen.getByText("غير مكتوب بهذه اللغة: لن يُطبع.")).toBeTruthy();  // the payment term has no English
    fireEvent.change(screen.getByLabelText("المسمى"), { target: { value: "Sales Director" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "حفظ الإعدادات" })); });
    const body = api.apiClient.mock.calls.find(([, o]) => o?.method === "PUT")![1].body as QuoteSettings;
    expect(body.document_language).toBe("en");
    expect(body.signature_title_en).toBe("Sales Director");
    expect(body.signature_title_ar).toBe("مدير المبيعات");
    expect(body.terms[0]).toMatchObject({ title_ar: "الدفع", title_en: null, body_en: null });  // the Arabic term is kept
  });
});

describe("quotation document", () => {
  it("downloads in the settings' language with one button", async () => {
    api.apiClient.mockResolvedValue(new Response("pdf", { headers: { "content-disposition": "attachment; filename*=UTF-8''QT-2026-0004.pdf" } }));
    URL.createObjectURL = vi.fn(() => "blob:x");
    URL.revokeObjectURL = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);  // jsdom does not navigate
    ui(<QuoteDocumentButtons quoteId="q1" />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "تنزيل عرض السعر PDF" })); });
    expect(api.apiClient).toHaveBeenCalledWith("/commercial/quotes/q1/document.pdf", { raw: true });
  });
});
