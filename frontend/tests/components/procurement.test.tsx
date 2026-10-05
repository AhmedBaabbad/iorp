// PROC-001: procurement — suppliers and their standing, goods receipts from draft to received, materials.
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";
import type { Material, Receipt, Supplier } from "@/features/procurement/types";

const api = vi.hoisted(() => ({ apiClient: vi.fn() }));
const nav = vi.hoisted(() => ({ push: vi.fn() }));
const perms = vi.hoisted(() => ({ granted: new Set<string>() }));
vi.mock("@/lib/api-client", async importOriginal => ({ ...(await importOriginal<object>()), apiClient: api.apiClient }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: nav.push, replace: vi.fn() }), usePathname: () => "/", useSearchParams: () => new URLSearchParams() }));
vi.mock("@/features/auth/permission-hooks", () => ({ usePermission: (code: string) => perms.granted.has(code),
  useHasAnyPermission: (codes: string[]) => codes.some(code => perms.granted.has(code)) }));
vi.mock("@/hooks/useFormatter", () => ({ useFormatter: () => ({ date: (v: string) => v, dateTime: (v: string) => v, number: (v: string) => v,
  quantity: (v: string, u?: string) => `${Number(v)} ${u ?? ""}`.trim() }) }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) => <main><h1>{title}</h1>{action}{children}</main> }));

import { ReceiptDetail, ReceiptForm } from "@/features/procurement/components/Receipts";
import { SupplierDetail, SuppliersList } from "@/features/procurement/components/Suppliers";
import { PR } from "@/lib/procurement-permissions";
import { Q } from "@/lib/quality-permissions";

let en: Record<string, unknown>;
let ar: Record<string, unknown>;
beforeAll(async () => { en = await loadMessages("en") as Record<string, unknown>; ar = await loadMessages("ar") as Record<string, unknown>; });
beforeEach(() => { api.apiClient.mockReset(); nav.push.mockReset(); perms.granted = new Set([...Object.values(PR), ...Object.values(Q)]); });
afterEach(cleanup);
const ui = (node: ReactNode, locale: "en" | "ar" = "en") =>
  render(<NextIntlClientProvider locale={locale} messages={locale === "en" ? en : ar} timeZone="UTC">{node}</NextIntlClientProvider>);
const sent = (path: string, method: string) => api.apiClient.mock.calls.find(([p, o]) => p === path && o?.method === method)?.[1]?.body;

const supplier = (over: Partial<Supplier> = {}): Supplier => ({ id: "s1", supplier_code: "SUP-0001", name: "Gulf Polymers", category: "raw_material",
  status: "pending", status_reason: null, status_changed_at: null, status_changed_by_name: null, supplies: "PP homopolymer", contact_name: "Omar",
  phone: "+966551234567", email: null, address: null, city: "Jubail", country: null, vat_number: null, cr_number: null, notes: null, receipts_count: 3,
  last_receipt_date: "2026-10-05", ncr_count: 2, open_ncr_count: 1, actions: ["edit", "set_status"], history: [], non_conformances: [], recent_receipts: [],
  evaluation: null, created_at: "", ...over });
const evaluation = { months: 12, since: "2025-10-05", lots_inspected: 10, lots_released: 8, lots_rejected: 2, acceptance_pct: "80.00", ncr_count: 2,
  ncr_penalty: 7, ncr_cost: "3000.00", cost_penalty: 3, score: "70.00", grade: "C" as const, suggested_status: "conditional" as const };
const material: Material = { id: "m1", material_code: "MAT-0001", name: "PP homopolymer H030", category: "resin", unit: "kg", inspection_required: true,
  spec_product_type: "pp_resin", active: true, notes: null };
const receipt = (over: Partial<Receipt> = {}): Receipt => ({ id: "r1", receipt_no: "GRN-2026-0001", status: "draft", receipt_date: "2026-10-05", supplier_id: "s1",
  supplier_name: "Gulf Polymers", supplier_status: "approved", supplier_delivery_no: "DN-GP-4471", supplier_invoice_no: null, purchase_reference: null,
  quantities: [{ unit: "kg", quantity: "20000.000" }], weight_kg: null, inspection_lines: 1, lots_pending: 0, actions: ["edit", "receive", "cancel"], created_at: "",
  vehicle_plate: null, driver_name: null, notes: null, received_at: null, received_by_name: null, created_by_name: "Sara", cancel_reason: null,
  lines: [{ id: "l1", line_no: 1, material_id: "m1", description: "PP homopolymer H030", supplier_lot: "SUP-7781", quantity: "20000.000", unit: "kg",
    package_count: 800, weight: null, weight_unit: "kg", inspection_required: true, notes: null }], line_quality: {}, history: [], updated_at: "", ...over });

describe("suppliers", () => {
  it("lists suppliers with their standing and open non-conformances", async () => {
    api.apiClient.mockResolvedValue([supplier()]);
    ui(<SuppliersList />, "ar");
    expect(await screen.findByRole("link", { name: "SUP-0001" })).toBeTruthy();
    expect(screen.getAllByText("بانتظار التقييم").length).toBe(2);  // the filter option and the badge
    expect(screen.getByText("1 مفتوحة")).toBeTruthy();
  });

  it("shows the grade in the list and the evaluation with its suggested standing", async () => {
    api.apiClient.mockResolvedValue([supplier({ evaluation })]);
    ui(<SuppliersList />);
    expect(await screen.findByText("C · 70")).toBeTruthy();
    cleanup();
    api.apiClient.mockResolvedValue(supplier({ status: "approved", evaluation }));
    ui(<SupplierDetail supplierId="s1" />);
    const panel = await screen.findByRole("region", { name: "Supplier evaluation" });
    expect(within(panel).getByText("8 of 10 (80%)")).toBeTruthy();
    expect(within(panel).getByText("2 — minus 7 points")).toBeTruthy();
    expect(within(panel).getByText("70 / 100")).toBeTruthy();
    expect(within(panel).getByRole("status").textContent).toContain("Conditional");
  });

  it("does not score a supplier without inspected lots", async () => {
    api.apiClient.mockResolvedValue(supplier({ evaluation: { ...evaluation, lots_inspected: 0, lots_released: 0, lots_rejected: 0, acceptance_pct: null,
      score: null, grade: null, suggested_status: null } }));
    ui(<SupplierDetail supplierId="s1" />);
    const panel = await screen.findByRole("region", { name: "Supplier evaluation" });
    expect(within(panel).getByText("Not scored")).toBeTruthy();
    expect(within(panel).getByText(/No inspected lot in this period/)).toBeTruthy();
  });

  it("blocks a supplier only with a reason", async () => {
    api.apiClient.mockImplementation((path: string, o?: { method?: string }) => Promise.resolve(o?.method === "POST" ? supplier({ status: "blocked" }) : supplier()));
    ui(<SupplierDetail supplierId="s1" />);
    expect((await screen.findByRole("link", { name: "New receipt" })).getAttribute("href")).toBe("/goods-receipts/new?supplier=s1");
    expect(screen.getByRole("link", { name: "Raise a non-conformance" }).getAttribute("href")).toBe("/non-conformance-reports/new?supplier=s1");
    fireEvent.click(screen.getByRole("button", { name: "Change standing" }));
    const dialog = screen.getByRole("dialog", { name: "Change standing" });
    fireEvent.click(within(dialog).getByLabelText("Blocked"));
    const confirm = within(dialog).getByRole("button", { name: "Confirm" }) as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);
    fireEvent.change(within(dialog).getByLabelText("Reason"), { target: { value: "Repeated contamination" } });
    await act(async () => { fireEvent.click(confirm); });
    expect(sent("/procurement/suppliers/s1/status", "POST")).toEqual({ status: "blocked", reason: "Repeated contamination" });
  });
});

describe("goods receipts", () => {
  it("records a delivery with the material's unit and the supplier's lot", async () => {
    api.apiClient.mockImplementation((path: string, o?: { method?: string }) => Promise.resolve(
      o?.method === "POST" ? receipt() : path.startsWith("/procurement/materials") ? [material]
        : path.startsWith("/procurement/suppliers/lookup") ? [{ id: "s1", supplier_code: "SUP-0001", name: "Gulf Polymers", status: "conditional" }] : []));
    ui(<ReceiptForm />);
    const supplierSelect = screen.getByLabelText("Supplier");
    await screen.findByRole("option", { name: "Gulf Polymers — SUP-0001" });
    fireEvent.change(supplierSelect, { target: { value: "s1" } });
    expect(screen.getByText(/This supplier is not on the approved list/)).toBeTruthy();
    await screen.findByRole("option", { name: "PP homopolymer H030 — MAT-0001" });
    fireEvent.change(screen.getByLabelText("Material"), { target: { value: "m1" } });
    expect(screen.getByText("This material is inspected on arrival.")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Supplier's lot"), { target: { value: "SUP-7781" } });
    fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "20000" } });
    fireEvent.change(screen.getByLabelText("Packages"), { target: { value: "800" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Save draft" })); });
    expect(sent("/procurement/receipts", "POST")).toMatchObject({ supplier_id: "s1",
      lines: [{ material_id: "m1", description: null, supplier_lot: "SUP-7781", quantity: "20000", unit: "kg", package_count: 800, weight: null, weight_unit: "kg" }] });
    expect(nav.push).toHaveBeenCalledWith("/goods-receipts/r1");
  });

  it("confirms the receipt, then offers a non-conformance report for a lot", async () => {
    api.apiClient.mockImplementation((path: string, o?: { method?: string }) => Promise.resolve(o?.method === "POST"
      ? receipt({ status: "received", actions: ["cancel"], received_by_name: "Sara", received_at: "2026-10-05T10:00:00Z" }) : receipt()));
    ui(<ReceiptDetail receiptId="r1" />, "ar");
    const receive = await screen.findByRole("button", { name: "تأكيد الاستلام" });
    await act(async () => { fireEvent.click(receive); });
    const link = await screen.findByRole("link", { name: "فتح تقرير عدم مطابقة" });
    expect(link.getAttribute("href")).toBe("/non-conformance-reports/new?supplier=s1&reference=GRN-2026-0001%20%2F%20SUP-7781&item=PP%20homopolymer%20H030");
  });

  it("shows whether quality released each received lot", async () => {
    api.apiClient.mockResolvedValue(receipt({ status: "received", actions: ["cancel"], lots_pending: 0, line_quality: { l1: { status: "partly_released",
      inspection: { id: "c1", inspection_code: "QC-0007", status: "closed", result: "partial", qty_inspected: "20000.000", qty_accepted: "15000.000",
        closed_at: "2026-10-05T12:00:00Z" } } } }));
    ui(<ReceiptDetail receiptId="r1" />, "ar");
    expect(await screen.findByText("معتمدة جزئياً")).toBeTruthy();
    expect(screen.getByRole("link", { name: "QC-0007" }).getAttribute("href")).toBe("/quality-checks/c1");
  });
});
