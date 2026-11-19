import { cleanup, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, expect, it, vi } from "vitest";
import { useCustomerNames } from "@/features/customers/use-customer-names";

const api = vi.hoisted(() => ({ lookup: vi.fn() }));
vi.mock("@/features/customers/customer-api", () => ({ customersByIds: api.lookup }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

function Names() {
  const name = useCustomerNames(["one", "two", "one", null]);
  return <><p>{name("one", "اسم محفوظ")}</p><p>{name("two", "Second snapshot")}</p><p>{name(null, "Free text")}</p></>;
}

it("resolves registered customer names in one batched lookup and preserves free text", async () => {
  api.lookup.mockResolvedValue([{ id: "one", name_ar: "عميل", name_en: "Current customer" }]);
  render(<NextIntlClientProvider locale="en" messages={{}}><Names /></NextIntlClientProvider>);
  expect(await screen.findByText("Current customer")).toBeTruthy();
  expect(api.lookup).toHaveBeenCalledExactlyOnceWith(["one", "two"]);
  expect(screen.getByText("Second snapshot")).toBeTruthy();
  expect(screen.getByText("Free text")).toBeTruthy();
});

it("preserves saved text when lookup permission is denied", async () => {
  api.lookup.mockRejectedValue(new Error("forbidden"));
  render(<NextIntlClientProvider locale="ar" messages={{}}><Names /></NextIntlClientProvider>);
  expect(await screen.findByText("اسم محفوظ")).toBeTruthy();
});
