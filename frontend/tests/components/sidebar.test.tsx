// DASH-002: the sidebar — the section of the page shown opens by itself, the others fold, the user's menu opens from
// the card at the bottom and closes with Escape.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";

const nav = vi.hoisted(() => ({ pathname: "/production-orders" }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => nav.pathname }));
vi.mock("@/features/auth", () => ({
  ProtectedRoute: ({ children }: { children: ReactNode }) => <>{children}</>,
  useAuth: () => ({ user: { full_name: "Ahmed Saleh", organization_name: "Rehab Factory", roles: ["production_manager"] }, token: "t",
    hasPermission: () => true, logout: vi.fn() }),
  useHasAnyPermission: () => true,
}));
vi.mock("@/features/ncr-reports/use-capa-alerts", () => ({ useCapaAlerts: () => ({ total: 0 }) }));
vi.mock("@/components/LanguageSwitcher", () => ({ LanguageSwitcher: () => <div>language switcher</div> }));
vi.mock("@/components/theme/theme-toggle", () => ({ ThemeToggle: () => <div>theme toggle</div> }));

import { PageFrame } from "@/components/layout/page-frame";

let en: Record<string, unknown>;
beforeAll(async () => { en = await loadMessages("en") as Record<string, unknown>; });
beforeEach(() => { window.localStorage.clear(); nav.pathname = "/production-orders"; });
afterEach(cleanup);
const ui = () => render(<NextIntlClientProvider locale="en" messages={en} timeZone="UTC"><PageFrame title="Orders">content</PageFrame></NextIntlClientProvider>);

describe("sidebar", () => {
  it("opens the section of the page shown and folds the others", () => {
    ui();
    const production = screen.getByRole("button", { name: /Production/ });
    expect(production.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByRole("link", { name: "Production Orders" }).getAttribute("aria-current")).toBe("page");
    const quality = screen.getByRole("button", { name: /^Quality/ });
    expect(quality.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(quality);
    expect(quality.getAttribute("aria-expanded")).toBe("true");
    expect(JSON.parse(window.localStorage.getItem("iorp.sidebar.groups")!)).toMatchObject({ "sections.quality": true });
  });

  it("keeps the user's settings in a menu at the bottom", () => {
    ui();
    expect(screen.queryByText("theme toggle")).toBeNull();
    const card = screen.getByRole("button", { name: /Ahmed Saleh/ });
    fireEvent.click(card);
    expect(screen.getByRole("menu")).toBeTruthy();
    expect(screen.getByText("theme toggle")).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: "Sign out" })).toBeTruthy();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("menu")).toBeNull();
  });
});
