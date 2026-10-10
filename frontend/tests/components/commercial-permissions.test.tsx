// RBAC-002: a button of the customers module shows only to who may use it (the server checks again).
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";

const api = vi.hoisted(() => ({ apiClient: vi.fn() }));
const perms = vi.hoisted(() => ({ granted: new Set<string>() }));
vi.mock("@/lib/api-client", async importOriginal => ({ ...(await importOriginal<object>()), apiClient: api.apiClient }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/quotes",
  useSearchParams: () => new URLSearchParams() }));
vi.mock("@/features/auth/permission-hooks", () => ({ usePermission: (code: string) => perms.granted.has(code),
  useHasAnyPermission: (codes: string[]) => codes.some(code => perms.granted.has(code)) }));
vi.mock("@/hooks/useFormatter", () => ({ useFormatter: () => ({ date: (v: string) => v, dateTime: (v: string) => v, number: (v: string) => v,
  decimal: (v: string) => v, quantity: (v: string) => v, currency: (v: string) => v }) }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ action, children }: { action?: ReactNode; children: ReactNode }) => <main>{action}{children}</main> }));

import { CustomerInteractionsSection } from "@/features/interactions/interactions-section";
import { QuotesList } from "@/features/quotes/components/QuotesList";

let en: Record<string, unknown>;
beforeAll(async () => { en = await loadMessages("en") as Record<string, unknown>; });
beforeEach(() => { api.apiClient.mockReset(); perms.granted = new Set(); });
afterEach(cleanup);
const ui = (node: ReactNode) => render(<NextIntlClientProvider locale="en" messages={en} timeZone="UTC">{node}</NextIntlClientProvider>);

const interaction = { id: "i1", customer_id: "c1", interaction_type: "call", interaction_date: "2026-06-01T10:00:00Z", subject: "First call",
  summary: null, outcome: null, next_step_hint: null, created_by_user_id: "u", created_at: "2026-06-01T10:00:00Z" };

describe("customer interactions", () => {
  it("shows no edit or delete without their permissions", async () => {
    perms.granted = new Set(["commercial:interactions:read"]);
    api.apiClient.mockResolvedValue({ items: [interaction], total: 1, page: 1, page_size: 25, pages: 1 });
    ui(<CustomerInteractionsSection customerId="c1" />);
    expect(await screen.findByText("First call")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Edit" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Delete" })).toBeNull();
  });

  it("corrects an interaction with the update permission and deletes it after confirming", { timeout: 15000 }, async () => {
    perms.granted = new Set(["commercial:interactions:read", "commercial:interactions:update", "commercial:interactions:delete"]);
    api.apiClient.mockImplementation((path: string, options?: { method?: string }) =>
      Promise.resolve(options?.method ? interaction : { items: [interaction], total: 1, page: 1, page_size: 25, pages: 1 }));
    ui(<CustomerInteractionsSection customerId="c1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Edit" }));
    const subject = screen.getByDisplayValue("First call");
    fireEvent.change(subject, { target: { value: "First call (corrected)" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(api.apiClient.mock.calls.some(([p, o]) => p === "/commercial/customers/c1/interactions/i1" && o?.method === "PATCH"
      && o.body.subject === "First call (corrected)")).toBe(true));
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, delete" }));
    await waitFor(() => expect(api.apiClient.mock.calls.some(([p, o]) => p === "/commercial/customers/c1/interactions/i1" && o?.method === "DELETE")).toBe(true));
  });
});

describe("quotations list", () => {
  it("offers new, edit and delete only with their permissions", { timeout: 15000 }, async () => {
    const page = { items: [{ id: "q1", organization_id: "o", customer_id: "c1", customer_name: "Gulf", sample_id: null, quote_number: "QT-1",
      issue_date: "", valid_until: "", status: "draft", currency: "SAR", subtotal_amount: "0", discount_amount: "0", tax_amount: "0",
      total_amount: "0", created_by_user_id: "u", created_at: "", updated_at: "" }], total: 1, page: 1, page_size: 50, pages: 1 };
    api.apiClient.mockResolvedValue(page);
    perms.granted = new Set(["commercial:quotes:read"]);
    ui(<QuotesList />);
    expect(await screen.findByText("QT-1")).toBeTruthy();
    expect(screen.queryByRole("link", { name: /new/i })).toBeNull();
    expect(screen.queryByRole("link", { name: "Edit" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Delete" })).toBeNull();
    cleanup();
    perms.granted = new Set(["commercial:quotes:read", "commercial:quotes:create", "commercial:quotes:update", "commercial:quotes:delete"]);
    ui(<QuotesList />);
    expect(await screen.findByRole("link", { name: "Edit" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Delete" })).toBeTruthy();
  });
});
