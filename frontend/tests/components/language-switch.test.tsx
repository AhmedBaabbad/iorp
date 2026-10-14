// PROJECT-FIX-002: a screen's words follow the chosen language (here the shift form, whose type list was English only).
import { cleanup, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ title, children }: { title: string; children: ReactNode }) => <main><h1>{title}</h1>{children}</main> }));
vi.mock("@/features/shifts/api/shifts-api", () => ({ createShift: vi.fn() }));
import { ShiftForm } from "@/features/shifts/components/ShiftForm";

const messages: Record<string, Record<string, unknown>> = {};
beforeAll(async () => { for (const l of ["ar", "en"] as const) messages[l] = await loadMessages(l) as Record<string, unknown>; });
afterEach(cleanup);
const ui = (locale: "ar" | "en") => <NextIntlClientProvider locale={locale} messages={messages[locale]} timeZone="UTC"><ShiftForm /></NextIntlClientProvider>;

it("changes every word when the language changes", () => {
  const { rerender } = render(ui("en"));
  expect(screen.getByRole("option", { name: "Morning" })).toBeTruthy();
  const english = document.body.textContent;
  rerender(ui("ar"));
  expect(screen.getByRole("option", { name: "صباحي" })).toBeTruthy();
  expect(screen.queryByRole("option", { name: "Morning" })).toBeNull();
  expect(document.body.textContent).not.toEqual(english);
  expect(document.body.textContent).not.toMatch(/\b(Morning|Evening|Night|Custom)\b/);
});
