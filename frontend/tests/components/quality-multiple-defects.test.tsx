// PROD-QUALITY-FIX-001 item 5: several defects per inspection (each type once) and per rejection; severity = the highest.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";
import type { QualityCheckData } from "@/features/quality-checks/types";
import type { QualityRejectionData } from "@/features/quality-rejections/types";

const api = vi.hoisted(() => ({ apiClient: vi.fn() }));
const nav = vi.hoisted(() => ({ push: vi.fn(), params: new URLSearchParams() }));
const perms = vi.hoisted(() => ({ granted: new Set<string>() }));
vi.mock("@/lib/api-client", async importOriginal => ({ ...(await importOriginal<object>()), apiClient: api.apiClient }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: nav.push, replace: vi.fn() }), usePathname: () => "/", useSearchParams: () => nav.params }));
vi.mock("@/features/auth/permission-hooks", () => ({ usePermission: (code: string) => perms.granted.has(code) }));
vi.mock("@/hooks/useFormatter", () => ({ useFormatter: () => ({ date: (v: string) => v, dateTime: (v: string) => v, number: (v: string) => v, quantity: (v: string, u?: string) => `${v} ${u ?? ""}`.trim() }) }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) => <main><h1>{title}</h1>{action}{children}</main> }));

import { QualityChecksList } from "@/features/quality-checks/components/QualityChecksList";
import { QualityDefectForm } from "@/features/quality-defects/components/QualityDefectForm";
import { QualityRejectionDetail } from "@/features/quality-rejections/components/QualityRejectionDetail";
import { QualityRejectionForm } from "@/features/quality-rejections/components/QualityRejectionForm";
import { Q } from "@/lib/quality-permissions";

let en: Record<string, unknown>;
beforeAll(async () => { en = await loadMessages("en") as Record<string, unknown>; });
beforeEach(() => { api.apiClient.mockReset(); nav.push.mockReset(); nav.params = new URLSearchParams(); perms.granted = new Set(Object.values(Q)); });
afterEach(cleanup);
const ui = (node: ReactNode) => render(<NextIntlClientProvider locale="en" messages={en} timeZone="UTC">{node}</NextIntlClientProvider>);
const sent = (path: string, method: string) => api.apiClient.mock.calls.find(([p, o]) => p === path && o?.method === method)?.[1]?.body;

const check = (over: Partial<QualityCheckData> = {}) => ({ id: "c1", inspection_code: "QI-2026-0001", check_type: "finished_product_inspection", status: "closed",
  result: "rejected", check_datetime: "2026-10-01T08:00:00Z", production_order_id: "po1", production_order_item_id: null, sample_id: null, qty_inspected: "100",
  qty_accepted: "90", qty_rejected: "10", unit: "kg", order_number: "PO-1", item_line_no: null, sample_code: null, checked_by_name: "Sara", actions: [],
  created_at: "", updated_at: "", ...over });
const defectRow = (id: string, category: string, severity: string, description: string) => ({ id, organization_id: "o", quality_check_id: "c1",
  production_order_id: null, production_order_item_id: null, defect_date: "2026-10-01", defect_category: category, severity, defect_count: 2, description,
  created_at: "", updated_at: "" });
function rejection(over: Partial<QualityRejectionData> = {}): QualityRejectionData {
  return { id: "r1", rejection_code: "QR-2026-0001", quality_check_id: "c1", production_order_id: "po1", production_order_item_id: null,
    rejection_date: "2026-10-01", rejection_reason: "out_of_spec", disposition: null, disposition_status: "pending", quantity_rejected: "10", unit: "kg",
    order_number: "PO-1", item_line_no: null, inspection_code: "QI-2026-0001", unresolved: true, actions: ["edit", "decide"], created_at: "",
    rejection_notes: "Out of spec", rejected_by_name: "Sara", decision_notes: null, concession_approved_by: null, decided_at: null, decided_by_name: null,
    execution_notes: null, executed_at: null, executed_by_name: null, history: [], updated_at: "", severity: null, defects: [], ...over };
}

describe("inspections list", () => {
  it("shows the highest severity and defect chips with +N, and filters by defect type", async () => {
    api.apiClient.mockResolvedValue([check({ severity: "critical", defects: [
      { defect_category: "thickness", severity: "critical", defect_count: 1 }, { defect_category: "color", severity: "major", defect_count: 2 },
      { defect_category: "surface", severity: "minor", defect_count: 5 }] } as Partial<QualityCheckData>)]);
    ui(<QualityChecksList />);
    const table = await screen.findByRole("table", { name: /quality/i });
    expect(within(table).getByText("Critical")).toBeTruthy();
    expect(within(table).getByText("Thickness / Gauge")).toBeTruthy();
    expect(within(table).getByText("Color Deviation")).toBeTruthy();
    const more = within(table).getByText("+1");
    expect(more.getAttribute("title")).toBe("Surface Defect");
    fireEvent.change(screen.getByLabelText("Defect type"), { target: { value: "surface" } });
    await waitFor(() => expect(api.apiClient.mock.calls.some(([p]) => String(p).includes("defect_category=surface"))).toBe(true));
  });
});

describe("recording defects", () => {
  it("records several defect types at once and never offers a type already recorded", async () => {
    api.apiClient.mockResolvedValue([]);
    const onCreated = vi.fn().mockResolvedValue(undefined);
    ui(<QualityDefectForm qualityCheckId="c1" recordedCategories={["dimension"]} onCreated={onCreated} onCancel={() => undefined} />);
    const first = screen.getByRole("group", { name: "Defect 1" });
    expect((within(first).getByRole("option", { name: "Dimension" }) as HTMLOptionElement).disabled).toBe(true);
    fireEvent.change(within(first).getByLabelText("Description"), { target: { value: "Gauge low" } });
    fireEvent.click(screen.getByRole("button", { name: "Add another defect type" }));
    const second = screen.getByRole("group", { name: "Defect 2" });
    fireEvent.change(within(second).getByLabelText("Severity"), { target: { value: "critical" } });
    fireEvent.change(within(second).getByLabelText("Description"), { target: { value: "Scratches" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Record 2 defects" })); });
    const body = sent("/quality/quality-checks/c1/defects/batch", "POST") as { defects: { defect_category: string; severity: string }[] };
    expect(body.defects.map(d => [d.defect_category, d.severity])).toEqual([["thickness", "minor"], ["surface", "critical"]]);
    expect(onCreated).toHaveBeenCalled();
  });
});

describe("rejection defects", () => {
  it("shows each defect with its own affected quantity and the highest severity", async () => {
    api.apiClient.mockResolvedValue(rejection({ severity: "critical", defects: [
      { quality_defect_id: "d1", defect_category: "thickness", severity: "critical", defect_count: 3, description: "Gauge low", affected_quantity: "8" },
      { quality_defect_id: "d2", defect_category: "surface", severity: "minor", defect_count: 5, description: "Scratches", affected_quantity: "6" }] }));
    ui(<QualityRejectionDetail qualityRejectionId="r1" />);
    const table = await screen.findByRole("table", { name: "Defects" });
    expect(within(table).getByText("8 kg")).toBeTruthy();
    expect(within(table).getByText("6 kg")).toBeTruthy();
    // 8 + 6 > 10 rejected: overlapping defects are shown apart, never totalled.
    expect(screen.queryByText("14 kg")).toBeNull();
    expect(screen.getByText(/never added up/)).toBeTruthy();
  });

  it("picks several defects of the inspection, removes one, and saves them with optional affected quantities", async () => {
    api.apiClient.mockImplementation((path: string, o?: { method?: string }) => {
      if (path === "/quality/quality-rejections/r1" && o?.method === "PATCH") return Promise.resolve(rejection());
      if (path === "/quality/quality-rejections/r1") return Promise.resolve(rejection());
      if (path === "/quality/quality-checks/c1/defects") return Promise.resolve([defectRow("d1", "thickness", "critical", "Gauge low"),
        defectRow("d2", "surface", "minor", "Scratches"), defectRow("d3", "color", "major", "Light colour")]);
      return Promise.resolve([]);
    });
    ui(<QualityRejectionForm rejectionId="r1" />);
    const available = await screen.findByRole("list", { name: "Defects of the inspection" });
    fireEvent.change(screen.getByLabelText("Find a defect"), { target: { value: "scr" } });
    expect(within(available).getAllByRole("button")).toHaveLength(1);
    fireEvent.click(within(available).getByRole("button", { name: "Add Surface Defect" }));
    fireEvent.change(screen.getByLabelText("Find a defect"), { target: { value: "" } });
    fireEvent.click(within(available).getByRole("button", { name: "Add Thickness / Gauge" }));
    fireEvent.click(within(available).getByRole("button", { name: "Add Color Deviation" }));
    fireEvent.click(screen.getByRole("button", { name: "Remove Color Deviation" }));
    fireEvent.change(screen.getByLabelText("Affected quantity for Thickness / Gauge"), { target: { value: "8" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Save" })); });
    expect((sent("/quality/quality-rejections/r1", "PATCH") as { defects: unknown[] }).defects).toEqual([
      { quality_defect_id: "d2", affected_quantity: null }, { quality_defect_id: "d1", affected_quantity: "8" }]);
  });
});
