import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ApiClientError } from "@/lib/api-client";

const api = vi.hoisted(() => ({ request: vi.fn(), create: vi.fn(), samples: vi.fn() }));
vi.mock("next-intl", () => ({ useTranslations: () => Object.assign((key: string, values?: { days?: number }) => values?.days ? `${key}:${values.days}` : key, { has: () => true }), useLocale: () => "en" }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));
vi.mock("@/lib/api-client", async original => ({ ...await original<object>(), apiClient: api.request }));
vi.mock("@/features/quotes/api/quotes-api", () => ({ createQuote: api.create, listSamplesForQuoteCustomer: api.samples }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ children }: { children: ReactNode }) => <main>{children}</main> }));
vi.mock("@/hooks/useFormatter", () => ({ useFormatter: () => ({ decimal: String }) }));
vi.mock("@/features/customers", () => ({ CustomerPicker: ({ onChange }: { onChange: (id: string) => void }) => <button type="button" onClick={() => onChange("c1")}>Choose customer</button> }));
vi.mock("@/features/masterdata", () => ({ useBusinessSettings: () => ({ loaded: true, vatRate: 15, currency: "SAR" }), useProducts: () => [],
  ProductSelect: ({ value, onChange, ariaLabel }: { value: string; onChange: (v: string) => void; ariaLabel: string }) => <input aria-label={ariaLabel} value={value} onChange={e => onChange(e.target.value)} /> }));
vi.mock("@/components/forms/SpecEditor", () => ({ SpecEditor: ({ value, onChange }: { value: string; onChange: (v: string) => void }) => <textarea aria-label="Specification" value={value} onChange={e => onChange(e.target.value)} /> }));
vi.mock("@/features/quotes/components/QuoteLineFields", () => ({ LineDescriptionFields: () => null, QuoteHeadingFields: () => null, UnitSelect: () => null, DiscountAllField: () => null, LineDiscountField: () => null }));
vi.mock("@/features/quotes/components/QuoteItemsTable", () => ({ QuoteItemsTable: () => null }));
vi.mock("@/features/quotes/components/QuoteTotals", () => ({ QuoteTotals: () => null }));
import { QuoteForm } from "@/features/quotes/components/QuoteForm";

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] }); vi.setSystemTime(new Date("2026-11-11T09:00:00Z"));
  api.request.mockReset().mockResolvedValue({ quote_validity_days: 12 });
  api.create.mockReset(); api.samples.mockReset().mockResolvedValue([]);
});
afterEach(() => { cleanup(); vi.useRealTimers(); });

it("uses the organization policy and follows issue date until validity is manually edited", async () => {
  const { container } = render(<QuoteForm />);
  const [issue, valid] = Array.from(container.querySelectorAll<HTMLInputElement>('input[type="datetime-local"]'));
  await waitFor(() => expect(valid.value).toContain("2026-11-23"));
  fireEvent.change(issue, { target: { value: "2026-12-01T09:00" } });
  expect(valid.value).toBe("2026-12-13T09:00");
  fireEvent.change(valid, { target: { value: "2026-12-05T09:00" } });
  fireEvent.change(issue, { target: { value: "2026-12-02T09:00" } });
  expect(valid.value).toBe("2026-12-05T09:00");
});

it("shows the server's actual allowed validity limit", async () => {
  api.create.mockRejectedValue(new ApiClientError("Bad request", 400, { detail: { code: "QUOTE_VALIDITY_EXCEEDED", quote_validity_days: 7 } }));
  const { container } = render(<QuoteForm />);
  await waitFor(() => expect(screen.getByRole("button", { name: "actions.create" }).hasAttribute("disabled")).toBe(false));
  fireEvent.submit(container.querySelector("form")!);
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "errors.validityExceeded:7");
});

async function chooseSample() {
  api.samples.mockResolvedValue([{ id: "s1", customer_id: "c1", sample_code: "S-1", product_type: "film", requested_spec_json: { width: 20 } }]);
  await waitFor(() => expect(screen.getByRole("button", { name: "actions.create" }).hasAttribute("disabled")).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: "fields.customer" }));
  await screen.findByRole("option", { name: /S-1/ });
  fireEvent.change(screen.getByRole("combobox", { name: "fields.sample" }), { target: { value: "s1" } });
}

it("copies sample product/specification into an empty editable line", async () => {
  render(<QuoteForm />);
  await chooseSample();
  expect(screen.getByLabelText("items.fields.productType")).toHaveProperty("value", "film");
  expect(screen.getByLabelText("Specification")).toHaveProperty("value", '{"width":20}');
  fireEvent.change(screen.getByLabelText("Specification"), { target: { value: '{"width":25}' } });
  expect(screen.getByLabelText("Specification")).toHaveProperty("value", '{"width":25}');
});

it("preserves written lines and adds the sample only on explicit request", async () => {
  render(<QuoteForm />);
  fireEvent.change(screen.getByLabelText("Specification"), { target: { value: '{"keep":true}' } });
  await chooseSample();
  expect(screen.getByLabelText("Specification")).toHaveProperty("value", '{"keep":true}');
  fireEvent.click(screen.getByRole("button", { name: "items.addFromSample" }));
  expect(screen.getAllByLabelText("Specification").map(node => (node as HTMLInputElement).value)).toEqual(['{"keep":true}', '{"width":20}']);
});
