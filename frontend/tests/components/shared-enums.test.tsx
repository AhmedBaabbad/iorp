import { cleanup, render, screen } from "@testing-library/react";
import { NextIntlClientProvider, useTranslations } from "next-intl";
import { afterEach, beforeAll, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";
import { getEnumLabel, missingEnum, useEnumLabel } from "@/i18n/enum-helpers";
import { localName } from "@/lib/local-name";
import { customerDisplayName } from "@/lib/customer-name";
import { DASHBOARD_ENUM_FIELDS } from "@/i18n/dashboard-enums";
import { TranslationProvider } from "@/i18n/TranslationProvider";

let messages: Awaited<ReturnType<typeof loadMessages>>;
beforeAll(async () => { messages = await loadMessages("ar"); });
afterEach(() => { cleanup(); vi.unstubAllEnvs(); vi.restoreAllMocks(); });

function Words() {
  const reason = useEnumLabel("shipping", "returnReason");
  const status = useEnumLabel("procurement", "orderStatus");
  return <p>{reason("site_closed")} / {status("partially_received")}</p>;
}

it("reads return reasons and procurement statuses from the shared Arabic source", () => {
  render(<NextIntlClientProvider locale="ar" messages={messages}><Words /></NextIntlClientProvider>);
  expect(screen.getByText(/الموقع مغلق/)).toBeTruthy();
  expect(document.body.textContent).not.toMatch(/site_closed|partially_received/);
});

it("fails explicitly in test and never turns unknown keys into English titles", () => {
  expect(() => getEnumLabel("entity", "status", "unknown_value", key => key)).toThrow("Missing enum translation");
  expect(() => missingEnum("shipping.status")).toThrow("Missing enum translation");
});

it("shows a dash and warns in production", () => {
  vi.stubEnv("NODE_ENV", "production");
  const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
  expect(getEnumLabel("entity", "status", "unknown_value", key => key)).toBe("—");
  expect(warn).toHaveBeenCalledWith("Missing enum translation: entity.status");
});

it("shares the data-name fallback without translating single-language user text", () => {
  const item = { name_ar: "عميل", name_en: "Customer" };
  expect(localName(item, "ar")).toBe("عميل");
  expect(localName(item, "en")).toBe("Customer");
  expect(localName({ name_ar: "عميل" }, "en")).toBe("عميل");
  expect(localName({ name: "Original text" }, "ar")).toBe("Original text");
  expect(customerDisplayName(item, "en")).toBe(localName(item, "en"));
});

it("every dashboard enum type points to a shared dictionary", () => {
  const catalog = messages.sharedEnums as Record<string, Record<string, unknown>>;
  for (const [module, fields] of Object.entries(DASHBOARD_ENUM_FIELDS)) {
    for (const field of Object.values(fields)) expect(catalog[module][field]).toBeTruthy();
  }
});

it("the application provider protects legacy calls from leaking missing keys in production", () => {
  vi.stubEnv("NODE_ENV", "production");
  const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
  function Legacy() {
    const t = useTranslations("shipping.statuses");
    return <p>{t("unknown_value")}</p>;
  }
  render(<TranslationProvider locale="ar" messages={messages}><Legacy /></TranslationProvider>);
  expect(screen.getByText("—")).toBeTruthy();
  expect(document.body.textContent).not.toContain("unknown_value");
  expect(warn).toHaveBeenCalledWith("Missing enum translation: shipping.statuses");
});
