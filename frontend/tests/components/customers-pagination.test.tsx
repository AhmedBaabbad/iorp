// ARCH-PAGE-001: the customers list comes from the server one page at a time; search, filters and the page live in the
// address, and pickers search instead of loading every customer.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";
import { pageNumbers } from "@/lib/pagination";

const api = vi.hoisted(() => ({ apiClient: vi.fn() }));
const nav = vi.hoisted(() => ({ replace: vi.fn(), params: new URLSearchParams() }));
vi.mock("@/lib/api-client", async importOriginal => ({ ...(await importOriginal<object>()), apiClient: api.apiClient }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: nav.replace }), usePathname: () => "/customers",
  useSearchParams: () => nav.params }));
vi.mock("@/components/PermissionGuard", () => ({ PermissionGuard: ({ children }: { children: ReactNode }) => <>{children}</> }));
vi.mock("@/hooks/useFormatter", () => ({ useFormatter: () => ({ date: (v: string) => v, dateTime: (v: string) => v, number: (v: string) => v,
  decimal: (v: string) => v, quantity: (v: string) => v, currency: (v: string) => v }) }));
vi.mock("@/features/auth/permission-hooks", () => ({ usePermission: () => true, useHasAnyPermission: () => true }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ title, children }: { title: string; children: ReactNode }) => <main><h1>{title}</h1>{children}</main> }));

import { CustomersListPage } from "@/features/customers/customers-list-page";
import { CustomerPicker } from "@/features/customers/customer-picker";
import { QuotesList } from "@/features/quotes/components/QuotesList";

let en: Record<string, unknown>;
beforeAll(async () => { en = await loadMessages("en") as Record<string, unknown>; });
beforeEach(() => { api.apiClient.mockReset(); nav.replace.mockReset(); nav.params = new URLSearchParams(); });
afterEach(cleanup);
const ui = (node: ReactNode) => render(<NextIntlClientProvider locale="en" messages={en} timeZone="UTC">{node}</NextIntlClientProvider>);

const customer = (n: number) => ({ id: `c${n}`, customer_code: `CUST-${n}`, name: `Client ${n}`, sector: null, phone: null, email: null,
  status: "active", relationship_stage: "lead", priority_level: "medium", sales_owner: null });
const page = (p: number, size = 50, total = 120) => ({ items: Array.from({ length: Math.min(size, total - (p - 1) * size) }, (_, i) => customer((p - 1) * size + i + 1)),
  total, page: p, page_size: size, pages: Math.ceil(total / size) });

describe("customers list", () => {
  it("asks the server for one page and shows where it is", { timeout: 15000 }, async () => {
    nav.params = new URLSearchParams("page=2");
    api.apiClient.mockImplementation((path: string) => Promise.resolve(path.startsWith("/masterdata") ? [] : page(2)));
    ui(<CustomersListPage />);
    expect(await screen.findByText("Client 51")).toBeTruthy();
    expect(api.apiClient.mock.calls.some(([p]) => p === "/commercial/customers?page=2&page_size=50")).toBe(true);
    expect(screen.getAllByRole("row")).toHaveLength(51);  // the header and 50 rows, not all 120
    expect(screen.getByText("Showing 51 to 100 of 120")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Page 3" }));
    expect(nav.replace).toHaveBeenCalledWith("/customers?page=3", { scroll: false });
  });

  it("searches on the server and goes back to page 1", async () => {
    nav.params = new URLSearchParams("page=2");
    api.apiClient.mockImplementation((path: string) => Promise.resolve(path.startsWith("/masterdata") ? [] : page(2)));
    ui(<CustomersListPage />);
    fireEvent.change(await screen.findByPlaceholderText("Code, name, phone or e-mail"), { target: { value: "gulf" } });
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/customers?search=gulf", { scroll: false }));
    fireEvent.change(screen.getByRole("combobox", { name: "Status" }), { target: { value: "inactive" } });
    expect(nav.replace).toHaveBeenLastCalledWith("/customers?status=inactive", { scroll: false });
  });
});

describe("customer picker", () => {
  it("searches the server instead of loading every customer", async () => {
    api.apiClient.mockResolvedValue([{ id: "c7", customer_code: "CUST-7", name: "Gulf Packaging", status: "active" }]);
    const chosen = vi.fn();
    ui(<CustomerPicker value="" onChange={chosen} ariaLabel="Customer" />);
    fireEvent.change(screen.getByPlaceholderText("Search by name or code"), { target: { value: "gulf" } });
    await waitFor(() => expect(api.apiClient).toHaveBeenCalledWith("/commercial/customers/lookup?limit=20&search=gulf"));
    fireEvent.change(await screen.findByRole("combobox", { name: "Customer" }), { target: { value: "c7" } });
    expect(chosen).toHaveBeenCalledWith("c7", expect.objectContaining({ name: "Gulf Packaging" }));
  });
});

it("shows the first, the last and the pages around the current one", () => {
  expect(pageNumbers(1, 1)).toEqual([1]);
  expect(pageNumbers(5, 12)).toEqual([1, "gap", 3, 4, 5, 6, 7, "gap", 12]);
  expect(pageNumbers(2, 4)).toEqual([1, 2, 3, 4]);
});

describe("quotations list", () => {
  it("shows one server page with each row's customer, and searches on the server", { timeout: 15000 }, async () => {
    nav.params = new URLSearchParams("status=issued");
    api.apiClient.mockResolvedValue({ items: [{ id: "q1", organization_id: "o", customer_id: "c1", customer_name: "Gulf Packaging", customer_code: "C-1",
      sample_id: null, quote_number: "QT-2026-0040", issue_date: "2026-10-01T00:00:00Z", valid_until: "2026-11-01T00:00:00Z", status: "issued",
      currency: "SAR", subtotal_amount: "100", discount_amount: "0", tax_amount: "15", total_amount: "115", created_by_user_id: "u", created_at: "", updated_at: "" }],
      total: 61, page: 1, page_size: 50, pages: 2 });
    ui(<QuotesList />);
    expect(await screen.findByText("Gulf Packaging")).toBeTruthy();
    expect(api.apiClient).toHaveBeenCalledWith("/commercial/quotes?page=1&page_size=50&status=issued");
    expect(screen.getByText("Showing 1 to 50 of 61")).toBeTruthy();
    fireEvent.change(screen.getByPlaceholderText("Quotation number, customer name or code"), { target: { value: "gulf" } });
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/customers?status=issued&search=gulf", { scroll: false }));
  });
});
