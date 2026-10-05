// PROC-002: incoming inspection — received lots waiting for quality, and the decision that splits a lot.
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";
import type { AwaitingReceipt, QualityCheckData } from "@/features/quality-checks/types";

const api = vi.hoisted(() => ({ apiClient: vi.fn() }));
const nav = vi.hoisted(() => ({ push: vi.fn() }));
const perms = vi.hoisted(() => ({ granted: new Set<string>() }));
vi.mock("@/lib/api-client", async importOriginal => ({ ...(await importOriginal<object>()), apiClient: api.apiClient }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: nav.push, replace: vi.fn() }), usePathname: () => "/", useSearchParams: () => new URLSearchParams() }));
vi.mock("@/features/auth/permission-hooks", () => ({ usePermission: (code: string) => perms.granted.has(code),
  useHasAnyPermission: (codes: string[]) => codes.some(code => perms.granted.has(code)) }));
vi.mock("@/hooks/useFormatter", () => ({ useFormatter: () => ({ date: (v: string) => v, dateTime: (v: string) => v, number: (v: string) => v,
  quantity: (v: string, u?: string) => `${Number(v)} ${u ?? ""}`.trim() }) }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ title, children }: { title: string; children: ReactNode }) => <main><h1>{title}</h1>{children}</main> }));

import { LotDecisionDialog, QualityIncomingList } from "@/features/quality-checks/components/IncomingInspection";
import { Q } from "@/lib/quality-permissions";

let en: Record<string, unknown>;
beforeAll(async () => { en = await loadMessages("en") as Record<string, unknown>; });
beforeEach(() => { api.apiClient.mockReset(); nav.push.mockReset(); perms.granted = new Set(Object.values(Q)); });
afterEach(cleanup);
const ui = (node: ReactNode) => render(<NextIntlClientProvider locale="en" messages={en} timeZone="UTC">{node}</NextIntlClientProvider>);

const awaiting: AwaitingReceipt[] = [{ receipt_id: "r1", receipt_no: "GRN-2026-0001", receipt_date: "2026-10-05", received_at: null, supplier_id: "s1",
  supplier_name: "Gulf Polymers", supplier_delivery_no: "DN-GP-4471", lines: [{ line_id: "l1", line_no: 1, description: "PP homopolymer H030",
    material_code: "MAT-0001", spec_product_type: "pp_resin", supplier_lot: "SUP-7781", quantity: "20000.000", unit: "kg", inspection_id: null,
    inspection_code: null, inspection_status: null }] }];

describe("incoming inspection", () => {
  it("opens an inspection for a received lot", async () => {
    api.apiClient.mockImplementation((path: string, o?: { method?: string }) => Promise.resolve(o?.method === "POST" ? { id: "c9" } : awaiting));
    ui(<QualityIncomingList />);
    const open = await screen.findByRole("button", { name: "Open the inspection" });
    expect(screen.getByText("SUP-7781")).toBeTruthy();
    await act(async () => { fireEvent.click(open); });
    expect(api.apiClient).toHaveBeenCalledWith("/quality/incoming/lines/l1/inspection", { method: "POST" });
    expect(nav.push).toHaveBeenCalledWith("/quality-checks/c9");
  });

  it("records the decision only when the parts add up to the lot", () => {
    const onConfirm = vi.fn();
    ui(<LotDecisionDialog check={{ qty_inspected: "100.000", unit: "kg" } as QualityCheckData} busy={false} onClose={() => {}} onConfirm={onConfirm} />);
    const decide = screen.getByRole("button", { name: "Record the decision" }) as HTMLButtonElement;
    fireEvent.change(screen.getByLabelText(/Released for use/), { target: { value: "80" } });
    expect(decide.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(/^Scrap/), { target: { value: "20" } });
    expect(decide.disabled).toBe(false);
    expect(screen.getByText(/opens a non-conformance report about the supplier/)).toBeTruthy();
    fireEvent.click(decide);
    expect(onConfirm).toHaveBeenCalledWith({ released: "80", use_as_is: "0", sort: "0", return_to_supplier: "0", scrap: "20", hold: "0",
      notes: null, concession_approved_by: null });
  });

  it("asks who approved a concession", () => {
    ui(<LotDecisionDialog check={{ qty_inspected: "100.000", unit: "kg" } as QualityCheckData} busy={false} onClose={() => {}} onConfirm={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/Use as is/), { target: { value: "100" } });
    const decide = screen.getByRole("button", { name: "Record the decision" }) as HTMLButtonElement;
    expect(decide.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Concession approved by"), { target: { value: "Quality manager" } });
    fireEvent.change(screen.getByLabelText(/Notes \(required/), { target: { value: "Melt index slightly high" } });
    expect(decide.disabled).toBe(false);
  });
});
