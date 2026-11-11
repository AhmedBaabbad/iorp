import { cleanup, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, expect, it } from "vitest";
import messages from "@/i18n/locales/en/password-reset.json";
import { PasswordRequirements, passwordIsValid } from "@/components/forms/PasswordRequirements";
afterEach(cleanup);
it("updates the live checklist as the password and confirmation meet every condition", () => {
  const ui = (password: string, confirmation: string) => <NextIntlClientProvider locale="en" messages={{ passwordReset: messages }}>
    <PasswordRequirements password={password} confirmation={confirmation} />
  </NextIntlClientProvider>;
  const { rerender } = render(ui("", ""));
  expect(screen.getByRole("list").getAttribute("aria-live")).toBe("polite");
  expect(screen.getAllByRole("listitem").every(item => item.getAttribute("data-met") === "false")).toBe(true);
  rerender(ui("Abcd123!", "Abcd123!"));
  expect(screen.getAllByRole("listitem").every(item => item.getAttribute("data-met") === "true")).toBe(true);
  expect(passwordIsValid("Abcd123!", "Abcd123!")).toBe(true);
  expect(passwordIsValid("Abcd123!", "different")).toBe(false);
  expect(passwordIsValid("abcdefgh", "abcdefgh")).toBe(false);
});
