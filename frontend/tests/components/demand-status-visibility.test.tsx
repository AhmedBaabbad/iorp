// Demands list: choose which statuses are shown; finished demands are hidden by default.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";

const api = vi.hoisted(() => ({ apiClient: vi.fn() }));
const nav = vi.hoisted(() => ({ replace: vi.fn(), search: "" }));

vi.mock("@/lib/api-client", async importOriginal => ({ ...(await importOriginal<object>()), apiClient: api.apiClient }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: nav.replace, push: vi.fn() }),
  usePathname: () => "/production/demands",
  useSearchParams: () => new URLSearchParams(nav.search),
}));
vi.mock("@/features/auth/permission-hooks", () => ({ usePermission: () => true }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ title, children }: { title: string; children: ReactNode }) => <main><h1>{title}</h1>{children}</main> }));

import { DemandList } from "@/features/production-demands/list";
import { DEMANDS } from "@/features/production-demands/status-visibility";
const STORAGE_KEY = DEMANDS.storageKey;

let messages: Record<string, unknown>;
beforeAll(async () => { messages = await loadMessages("en") as Record<string, unknown>; });
beforeEach(() => {
  api.apiClient.mockReset(); nav.replace.mockReset(); nav.search = ""; window.localStorage.clear();
  api.apiClient.mockImplementation((path: string) => Promise.resolve(path.includes("customers") ? [] : { items: [], total: 0, page: 1, page_size: 20, hidden_by_status: 4 }));
});
afterEach(cleanup);

const ui = () => render(<NextIntlClientProvider locale="en" messages={messages} timeZone="UTC"><DemandList /></NextIntlClientProvider>);
const listCalls = () => api.apiClient.mock.calls.map(([path]) => String(path)).filter(path => path.startsWith("/production/demands?"));
const statusesOf = (path: string) => new URLSearchParams(path.split("?")[1]).getAll("statuses");

describe("demand status visibility", () => {
  it("asks the server for unfinished demands only and says how many are hidden", async () => {
    ui();
    await waitFor(() => expect(listCalls()).toHaveLength(1));
    expect(statusesOf(listCalls()[0])).toEqual(["draft", "ready_for_planning", "partially_planned"]);
    expect(await screen.findByText(/4 demands are hidden by the status filter/)).toBeTruthy();
  });

  it("hides one status, remembers it in this browser and in the URL", async () => {
    ui();
    await waitFor(() => expect(listCalls()).toHaveLength(1));
    fireEvent.click(screen.getByRole("checkbox", { name: "Draft" }));
    await waitFor(() => expect(listCalls()).toHaveLength(2));
    expect(statusesOf(listCalls()[1])).toEqual(["ready_for_planning", "partially_planned"]);
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe("ready_for_planning,partially_planned");
    expect(String(nav.replace.mock.calls.at(-1)?.[0])).toContain("statuses=ready_for_planning%2Cpartially_planned");
  });

  it("show all sends no status filter", async () => {
    ui();
    await waitFor(() => expect(listCalls()).toHaveLength(1));
    fireEvent.click(screen.getAllByRole("button", { name: "Show all" })[0]);
    await waitFor(() => expect(listCalls()).toHaveLength(2));
    expect(statusesOf(listCalls()[1])).toEqual([]);
  });

  it("starts from this browser's last choice", async () => {
    window.localStorage.setItem(STORAGE_KEY, "planned");
    ui();
    await waitFor(() => expect(listCalls()).toHaveLength(1));
    expect(statusesOf(listCalls()[0])).toEqual(["planned"]);
  });
});
