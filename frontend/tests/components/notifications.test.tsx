// PROJECT-UX-NOTIFY: every successful change tells the user what happened, in the screen's language; a screen's own
// message replaces the automatic one, so one click never shows two messages.
import { act, cleanup, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeAll, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";
import { Notifications, dismiss, pushNote } from "@/components/notify/Notifications";
import { actionOf, pushAction } from "@/lib/notify-store";

const messages: Record<string, Record<string, unknown>> = {};
beforeAll(async () => { for (const l of ["ar", "en"] as const) messages[l] = await loadMessages(l) as Record<string, unknown>; });
afterEach(() => { act(() => { for (let id = 0; id < 200; id++) dismiss(id); }); cleanup(); vi.useRealTimers(); });
const ui = (locale: "ar" | "en") => render(<NextIntlClientProvider locale={locale} messages={messages[locale]} timeZone="UTC"><Notifications /></NextIntlClientProvider>);

it("names the action from the method and the address", () => {
  expect(actionOf("POST", "/procurement/purchase-orders/3f2a1c4e-0000-4000-8000-000000000001/approve")).toBe("approve");
  expect(actionOf("POST", "/procurement/suppliers")).toBe("create");
  expect(actionOf("PATCH", "/procurement/suppliers/3f2a1c4e-0000-4000-8000-000000000001")).toBe("update");
  expect(actionOf("DELETE", "/quality/ncr-reports/1/attachments/2")).toBe("delete");
  expect(actionOf("POST", "/quality/ncr-reports/1/attachments")).toBe("upload");
  expect(actionOf("POST", "/auth/login")).toBeNull();
  expect(actionOf("POST", "/production/planning/preview-production-order")).toBeNull();
});

it("shows the automatic message in Arabic, and a screen's own message replaces it", () => {
  ui("ar");
  act(() => { pushAction("approve", true); });
  expect(screen.getByText("تم الاعتماد.")).toBeTruthy();
  act(() => { pushNote("success", "تم إرسال طلب التفويض"); });
  expect(screen.queryByText("تم الاعتماد.")).toBeNull();
  expect(screen.getByText("تم إرسال طلب التفويض")).toBeTruthy();
});

it("one click saving several parts shows one message, in English", () => {
  ui("en");
  act(() => { pushAction("update", true); pushAction("create", true); });
  expect(screen.getAllByRole("status")).toHaveLength(1);
  expect(screen.getByText("Changes saved.")).toBeTruthy();
});
