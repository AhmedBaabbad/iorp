import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeAll, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";
import { customerDisplayName } from "@/lib/customer-name";
import { hasCustomerName, defaultCustomerFormValues, toCustomerCreateRequest } from "@/features/customers/customer-form";
import { CustomerNameLanguageHint } from "@/features/quotes/components/CustomerNameLanguageHint";
import { customersByIds } from "@/features/customers/customer-api";

vi.mock("@/features/customers/customer-api", () => ({ customersByIds: vi.fn() }));
let messages: Awaited<ReturnType<typeof loadMessages>>;
beforeAll(async () => { messages = await loadMessages("en"); });
afterEach(() => { cleanup(); vi.clearAllMocks(); });

it("uses the UI locale and falls back to the other name or legacy display", () => {
  const customer = { name: "Legacy", name_ar: "عميل", name_en: "Customer" };
  expect(customerDisplayName(customer, "ar")).toBe("عميل");
  expect(customerDisplayName(customer, "en")).toBe("Customer");
  expect(customerDisplayName({ ...customer, name_en: " " }, "en")).toBe("عميل");
  expect(customerDisplayName({ ...customer, name_ar: null }, "ar-SA")).toBe("Customer");
  expect(customerDisplayName({ name: "Legacy" }, "en")).toBe("Legacy");
});

it("requires at least one trimmed name and sends both language fields", () => {
  expect(hasCustomerName(defaultCustomerFormValues)).toBe(false);
  expect(hasCustomerName({ name_ar: " ", name_en: "\t" })).toBe(false);
  expect(hasCustomerName({ name_ar: " عميل ", name_en: "" })).toBe(true);
  expect(hasCustomerName({ name_ar: "", name_en: "Customer" })).toBe(true);
  const body = toCustomerCreateRequest({ ...defaultCustomerFormValues, name_ar: " عميل ", name_en: " Customer " }, false);
  expect(body).toMatchObject({ name_ar: "عميل", name_en: "Customer" });
  expect(body).not.toHaveProperty("name");
});

it.each([
  ["en", "عميل", null, "This customer has no English name; the Arabic name will be printed."],
  ["ar", null, "Customer", "This customer has no Arabic name; the English name will be printed."],
] as const)("shows a nonblocking document-language fallback note for %s", async (language, ar, en, note) => {
  vi.mocked(customersByIds).mockResolvedValue([{ id: "synthetic", customer_code: "C1", name: ar ?? en!, name_ar: ar, name_en: en, status: "active" }]);
  render(<NextIntlClientProvider locale="en" messages={messages} timeZone="UTC">
    <CustomerNameLanguageHint customerId="synthetic" language={language} />
  </NextIntlClientProvider>);
  expect(await screen.findByText(note)).toBeTruthy();
  expect(screen.getByRole("link", { name: "Customer details" }).getAttribute("href")).toBe("/customers/synthetic");
  expect(screen.queryByRole("alert")).toBeNull();
});

it("does not warn when the name in the document language exists", async () => {
  vi.mocked(customersByIds).mockResolvedValue([{ id: "both", customer_code: "C2", name: "عميل", name_ar: "عميل", name_en: "Customer", status: "active" }]);
  render(<NextIntlClientProvider locale="en" messages={messages} timeZone="UTC">
    <CustomerNameLanguageHint customerId="both" language="en" />
  </NextIntlClientProvider>);
  await waitFor(() => expect(customersByIds).toHaveBeenCalledWith(["both"]));
  expect(screen.queryByRole("link")).toBeNull();
});
