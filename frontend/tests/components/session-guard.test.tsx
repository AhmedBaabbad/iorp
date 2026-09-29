// Idle sign-out: warning after 4 minutes, automatic sign-out at 5, without any click.
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";

const calls = vi.hoisted(() => ({ refresh: vi.fn(), logout: vi.fn() }));
vi.mock("@/lib/api-client", async importOriginal => ({ ...(await importOriginal<object>()), refreshSession: calls.refresh }));
vi.mock("@/features/auth/auth-client", () => ({ logoutSession: calls.logout }));

import { SessionGuard } from "@/features/auth/session-guard";
import { ACCESS_TOKEN_KEY } from "@/lib/auth";

const MIN = 60_000;
const jwt = (expiresInMs: number) => `h.${btoa(JSON.stringify({ exp: Math.floor((Date.now() + expiresInMs) / 1000) }))}.s`;
let messages: Record<string, unknown>;
beforeAll(async () => { messages = await loadMessages("en") as Record<string, unknown>; });
beforeEach(() => {
  vi.useFakeTimers();
  localStorage.clear();
  localStorage.setItem(ACCESS_TOKEN_KEY, jwt(15 * MIN));
  calls.refresh.mockReset().mockResolvedValue("new-token");
  calls.logout.mockReset().mockResolvedValue(undefined);
});
afterEach(() => { cleanup(); vi.useRealTimers(); });

function mount() {
  const redirect = vi.fn();
  const onSignedOut = vi.fn();
  render(<NextIntlClientProvider locale="en" messages={messages} timeZone="UTC"><SessionGuard redirect={redirect} onSignedOut={onSignedOut} /></NextIntlClientProvider>);
  return { redirect, onSignedOut };
}
const advance = (ms: number) => act(() => { vi.advanceTimersByTime(ms); });

describe("session guard", () => {
  it("warns one minute before, then signs out at five idle minutes with no click", () => {
    const { redirect, onSignedOut } = mount();
    advance(4 * MIN - 2000);
    expect(screen.queryByRole("alertdialog")).toBeNull();
    advance(3000);
    expect(screen.getByRole("alertdialog", { name: "Are you still there?" })).toBeTruthy();
    expect(screen.getByText(/Signing out in \d+ seconds/)).toBeTruthy();
    advance(MIN);
    expect(redirect).toHaveBeenCalledWith("/login?session=idle");
    expect(calls.logout).toHaveBeenCalledTimes(1);          // server session revoked too
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull();
    expect(onSignedOut).toHaveBeenCalled();
  });

  it("activity resets the countdown", () => {
    const { redirect } = mount();
    advance(4 * MIN + 5000);
    expect(screen.getByRole("alertdialog")).toBeTruthy();
    fireEvent.keyDown(window, { key: "a" });
    advance(1000);
    expect(screen.queryByRole("alertdialog")).toBeNull();
    advance(3 * MIN);
    expect(redirect).not.toHaveBeenCalled();
  });

  it("stay signed in keeps the session; sign out now ends it at once", () => {
    const { redirect } = mount();
    advance(4 * MIN + 1000);
    fireEvent.click(screen.getByRole("button", { name: "Stay signed in" }));
    expect(screen.queryByRole("alertdialog")).toBeNull();
    advance(2 * MIN);
    expect(redirect).not.toHaveBeenCalled();
    advance(2 * MIN + 1000);
    fireEvent.click(screen.getByRole("button", { name: "Sign out now" }));
    expect(redirect).toHaveBeenCalledWith("/login?session=idle");
  });

  it("activity in another tab keeps this tab signed in", () => {
    const { redirect } = mount();
    advance(3 * MIN);
    localStorage.setItem("iorp.last_activity", String(Date.now()));
    advance(3 * MIN);
    expect(redirect).not.toHaveBeenCalled();
  });

  it("signing out in another tab signs this tab out immediately", () => {
    const { redirect } = mount();
    act(() => { window.dispatchEvent(new StorageEvent("storage", { key: ACCESS_TOKEN_KEY, newValue: null })); });
    expect(redirect).toHaveBeenCalledWith("/login?session=expired");
  });

  it("renews the token for an active user and signs out when renewal fails", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, jwt(30_000));
    calls.refresh.mockRejectedValue(new Error("session revoked"));
    const { redirect } = mount();
    await act(async () => { vi.advanceTimersByTime(1000); await Promise.resolve(); });
    expect(calls.refresh).toHaveBeenCalledTimes(1);
    expect(redirect).toHaveBeenCalledWith("/login?session=expired");
  });
});

describe("session guard on page load", () => {
  it("signs out at once when the app is reopened after the idle limit", () => {
    localStorage.setItem("iorp.last_activity", String(Date.now() - 6 * MIN));
    const { redirect } = mount();
    expect(redirect).toHaveBeenCalledWith("/login?session=idle");
  });

  it("keeps a recently active session when the page reloads", () => {
    localStorage.setItem("iorp.last_activity", String(Date.now() - 2 * MIN));
    const { redirect } = mount();
    advance(2 * MIN);
    expect(redirect).not.toHaveBeenCalled();
  });
});
