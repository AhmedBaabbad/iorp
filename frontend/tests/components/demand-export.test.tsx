// PROD-EXPORT-001: the demands screen exports what it shows (same filters, every page) as an Excel file.
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";

const api = vi.hoisted(() => ({ apiClient: vi.fn() }));
vi.mock("@/lib/api-client", async importOriginal => ({ ...(await importOriginal<object>()), apiClient: api.apiClient, API_BASE_URL: "http://api" }));
vi.mock("@/lib/auth", async importOriginal => ({ ...(await importOriginal<object>()), getStoredAccessToken: () => "token-1" }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn(), push: vi.fn() }), usePathname: () => "/production/demands", useSearchParams: () => new URLSearchParams() }));
vi.mock("@/features/auth/permission-hooks", () => ({ usePermission: () => true }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ title, children }: { title: string; children: ReactNode }) => <main><h1>{title}</h1>{children}</main> }));

import { DemandList } from "@/features/production-demands/list";

let ar: Record<string, unknown>;
const fetchMock = vi.fn();
beforeAll(async () => {
  ar = await loadMessages("ar") as Record<string, unknown>;
  URL.createObjectURL = vi.fn(() => "blob:demands");
  URL.revokeObjectURL = vi.fn();
  // jsdom has no modal dialogs (the planning screen keeps one ready).
  HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  HTMLDialogElement.prototype.close = function () { this.open = false; };
});
beforeEach(() => {
  api.apiClient.mockReset(); fetchMock.mockReset(); window.localStorage.clear();
  vi.stubGlobal("fetch", fetchMock);
  api.apiClient.mockImplementation((path: string) => Promise.resolve(path.includes("customers") || path.includes("work-centers") ? [] : { items: [], total: 0, page: 1, page_size: 20, pages: 0 }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const ui = (node: ReactNode) => render(<NextIntlClientProvider locale="ar" messages={ar} timeZone="UTC">{node}</NextIntlClientProvider>);

describe("demands export", () => {
  it("downloads the screen's demands with its filters and without the page", async () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    fetchMock.mockResolvedValue(new Response(new Blob(["xlsx"]), { status: 200, headers: { "content-disposition": "attachment; filename*=UTF-8''%D8%B7%D9%84%D8%A8%D8%A7%D8%AA.xlsx" } }));
    ui(<DemandList />);
    await waitFor(() => expect(api.apiClient).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText("بحث"), { target: { value: "PD-7" } });
    const button = screen.getByRole("button", { name: "تصدير Excel" }) as HTMLButtonElement;
    await waitFor(() => expect(button.disabled).toBe(false));  // the list reloads first
    await act(async () => { fireEvent.click(button); });
    const [url, init] = fetchMock.mock.calls[0];
    const query = new URL(String(url)).searchParams;
    expect(String(url).startsWith("http://api/api/v1/production/demands/export.xlsx?")).toBe(true);
    expect(query.get("search")).toBe("PD-7");
    expect(query.getAll("statuses")).toEqual(["draft", "ready_for_planning", "partially_planned"]);
    expect(query.has("page") || query.has("page_size")).toBe(false);
    expect((init as RequestInit).headers).toEqual({ Authorization: "Bearer token-1" });
    expect(click).toHaveBeenCalled();
    click.mockRestore();
  });

  it("explains when the result is too large for one file", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ detail: { code: "export_too_large" } }), { status: 422 }));
    ui(<DemandList />);
    await waitFor(() => expect(api.apiClient).toHaveBeenCalled());
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "تصدير Excel" })); });
    expect((await screen.findByRole("alert")).textContent).toContain("ضيّق الفلاتر");
  });

  it("exports the planning queue from its own address", async () => {
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    fetchMock.mockResolvedValue(new Response(new Blob(["xlsx"]), { status: 200 }));
    ui(<DemandList planning />);
    await waitFor(() => expect(api.apiClient).toHaveBeenCalled());
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "تصدير Excel" })); });
    expect(String(fetchMock.mock.calls[0][0])).toContain("/api/v1/production/planning/demands/export.xlsx?");
  });
});
