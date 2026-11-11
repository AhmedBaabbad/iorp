// DASH-002: the sidebar — the section of the page shown opens by itself, the others fold, the user's menu opens from
// the card at the bottom and closes with Escape.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";

const nav = vi.hoisted(() => ({ pathname: "/production-orders", ready: true }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => nav.pathname }));
vi.mock("@/features/auth", () => ({
  ProtectedRoute: ({ children }: { children: ReactNode }) => nav.ready ? <>{children}</> : null,
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
beforeEach(() => { window.localStorage.clear(); window.sessionStorage.clear(); nav.pathname = "/production-orders"; nav.ready = true; });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const view = () => <NextIntlClientProvider locale="en" messages={en} timeZone="UTC"><PageFrame title="Orders">content</PageFrame></NextIntlClientProvider>;
const ui = () => render(view());

describe("sidebar", () => {
  it("shows the transport directory only once under master data", () => {
    nav.pathname = "/shipping-directory";
    ui();
    const links = document.querySelectorAll('a[href="/shipping-directory"]');
    expect(links.length).toBe(1);
    expect(links[0].parentElement?.parentElement?.querySelector("button")?.textContent).toContain("Master data");
  });

  it("restores scroll across page remounts and leaves a visible active link alone", () => {
    vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(200);
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
      return { top: this.tagName === "NAV" ? 100 : 120, bottom: this.tagName === "NAV" ? 300 : 140, height: 20 } as DOMRect;
    });
    const nearest = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: nearest });
    const first = ui();
    const scroll = document.querySelector<HTMLElement>(".iorp-sidebar-nav")!;
    scroll.scrollTop = 700; fireEvent.scroll(scroll);
    first.unmount();
    nav.pathname = "/quality-checks";
    ui();
    expect(document.querySelector(".iorp-sidebar-nav")?.scrollTop).toBe(700);
    expect(nearest).not.toHaveBeenCalled();
  });

  it("brings an offscreen active link into view using nearest", () => {
    vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(200);
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
      return { top: this.tagName === "NAV" ? 100 : 400, bottom: this.tagName === "NAV" ? 300 : 420, height: 20 } as DOMRect;
    });
    const nearest = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: nearest });
    const page = ui();
    expect(nearest).toHaveBeenCalledWith({ block: "nearest" });
    page.rerender(view());
    expect(nearest).toHaveBeenCalledTimes(1);
  });

  it("restores the same saved position when the mobile drawer opens", () => {
    window.sessionStorage.setItem("iorp.sidebar.scroll", "540");
    vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockImplementation(function (this: HTMLElement) {
      return this.closest(".iorp-sidebar-open") ? 200 : 0;
    });
    ui();
    fireEvent.click(document.querySelector(".iorp-hamburger")!);
    expect(document.querySelector(".iorp-sidebar-nav")?.scrollTop).toBe(540);
  });

  it("restores when the protected sidebar mounts after session loading", () => {
    nav.ready = false;
    window.sessionStorage.setItem("iorp.sidebar.scroll", "470");
    vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(200);
    const page = ui();
    expect(document.querySelector(".iorp-sidebar-nav")).toBeNull();
    nav.ready = true; page.rerender(view());
    expect(document.querySelector(".iorp-sidebar-nav")?.scrollTop).toBe(470);
  });

  it("still navigates when session storage is blocked", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    ui();
    expect(() => fireEvent.scroll(document.querySelector(".iorp-sidebar-nav")!)).not.toThrow();
  });
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
