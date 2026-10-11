// QUAL-NCR-002: non-conformance reports — opening one with its items, the stages (containment, root cause, actions,
// verification), the corrective actions list, and their follow-up (QUAL-CAPA-001).
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";
import type { CorrectiveAction, NcrReport } from "@/features/ncr-reports/types";

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

import { CorrectiveActionsList } from "@/features/ncr-reports/components/CorrectiveActionsList";
import { NcrReportDetail } from "@/features/ncr-reports/components/NcrReportDetail";
import { NcrReportForm } from "@/features/ncr-reports/components/NcrReportForm";
import { resetCapaAlerts } from "@/features/ncr-reports/use-capa-alerts";
import { Q } from "@/lib/quality-permissions";

let en: Record<string, unknown>;
let ar: Record<string, unknown>;
beforeAll(async () => { en = await loadMessages("en") as Record<string, unknown>; ar = await loadMessages("ar") as Record<string, unknown>; });
beforeEach(() => { api.apiClient.mockReset(); nav.push.mockReset(); perms.granted = new Set(Object.values(Q)); resetCapaAlerts(); });
afterEach(cleanup);
const ui = (node: ReactNode, locale: "en" | "ar" = "en") =>
  render(<NextIntlClientProvider locale={locale} messages={locale === "en" ? en : ar} timeZone="UTC">{node}</NextIntlClientProvider>);
const sent = (path: string, method: string) => api.apiClient.mock.calls.find(([p, o]) => p === path && o?.method === method)?.[1]?.body;

const action = (over: Partial<CorrectiveAction> = {}): CorrectiveAction => ({ id: "a1", ncr_id: "n1", line_no: 1, kind: "corrective",
  description: "Dryer check before release", owner_user_id: null, owner_name: "Gulf Polymers", due_date: "2026-10-10", status: "open", evidence: null,
  completed_at: null, completed_by_name: null, cancel_reason: null, overdue: false, ...over });

function report(over: Partial<NcrReport> = {}): NcrReport {
  return { id: "n1", report_number: "NCR-2026-0001", report_date: "2026-10-05", source_type: "incoming_material", report_type: "material_non_conformance",
    status: "open", severity: "major", title: "Wet PP granules", description: "Moisture above specification", reference_code: "SUP-7781",
    supplier_id: null, supplier_name: "Gulf Polymers", customer_name: null, owner_user_id: null, owner_name: null, due_date: null, overdue: false, open_actions: 0,
    overdue_actions: 0, total_cost: null, review_pending: false, review_due: false, actions: ["edit", "contain", "cancel"], created_at: "", supplier_reference: "DN-GP-4471", supplier_action: "none",
    supplier_response: null, supplier_responded_at: null, cost_material: null, cost_labor: null, cost_scrap: null, cost_transport: null, cost_other: null,
    claim_amount: null, claim_status: "none", quality_check_id: null, quality_rejection_id: null, production_order_id: null, return_id: null,
    inspection_code: null, rejection_code: null, order_number: null, return_no: null, detected_by_name: "Sara", containment: null, contained_at: null,
    contained_by_name: null, root_cause_category: null, root_cause_method: null, root_cause: null, action_required: null, no_action_justification: null,
    investigated_at: null, investigated_by_name: null, verification_attempts: 0, verification_notes: null, verified_at: null, verified_by_name: null,
    closed_at: null, cancel_reason: null, effectiveness_due_date: null, effectiveness_result: null, effectiveness_notes: null,
    effectiveness_reviewed_at: null, effectiveness_reviewed_by_name: null, recurrence: null, items: [{ id: "i1", line_no: 1, item_name: "PP granules", item_reference: "SUP-7781", quantity_affected: "2.000",
      unit: "ton", issue_description: "Moisture 0.12 %", disposition: "return_to_supplier", disposition_notes: null, notes: null }],
    corrective_actions: [], attachments: [], history: [], can_complete_actions: true, updated_at: "", ...over };
}

describe("non-conformance report form", () => {
  it("opens a report for a supplier's material with what it affects", async () => {
    api.apiClient.mockImplementation((path: string, o?: { method?: string }) => Promise.resolve(o?.method === "POST" ? report() : []));
    ui(<NcrReportForm />);
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Wet PP granules" } });
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "Moisture above specification" } });
    fireEvent.change(screen.getByLabelText("Supplier"), { target: { value: "Gulf Polymers" } });
    fireEvent.change(screen.getByLabelText("Action with the supplier"), { target: { value: "scar" } });
    expect(screen.getByText(/The supplier must find the cause/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Item"), { target: { value: "PP granules" } });
    fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("Unit"), { target: { value: "ton" } });
    fireEvent.change(screen.getByLabelText("Problem"), { target: { value: "Moisture 0.12 %" } });
    fireEvent.change(screen.getByLabelText("Decision"), { target: { value: "return_to_supplier" } });
    fireEvent.change(screen.getByLabelText("Material cost"), { target: { value: "9000" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Open the report" })); });
    expect(sent("/quality/non-conformance-reports", "POST")).toMatchObject({ source_type: "incoming_material", severity: "major", title: "Wet PP granules",
      supplier_name: "Gulf Polymers", supplier_action: "scar", cost_material: "9000", customer_name: null,
      items: [{ item_name: "PP granules", quantity_affected: "2", unit: "ton", issue_description: "Moisture 0.12 %", disposition: "return_to_supplier" }] });
    expect(nav.push).toHaveBeenCalledWith("/non-conformance-reports/n1");
  });
});

describe("non-conformance report stages", () => {
  it("records the containment, then the root cause", async () => {
    api.apiClient.mockImplementation((path: string) => Promise.resolve(path.endsWith("/contain")
      ? report({ status: "investigation", containment: "Lot quarantined", actions: ["edit", "investigate", "add_action", "cancel"] }) : report()));
    ui(<NcrReportDetail ncrReportId="n1" />, "ar");
    expect(await screen.findByText("إرجاع للمورد")).toBeTruthy();
    expect(screen.getByText("1. التسجيل").getAttribute("aria-current")).toBe("step");
    fireEvent.click(screen.getByRole("button", { name: "تسجيل الاحتواء" }));
    const dialog = screen.getByRole("dialog", { name: "الاحتواء" });
    fireEvent.change(within(dialog).getByLabelText("الاحتواء"), { target: { value: "Lot quarantined" } });
    await act(async () => { fireEvent.click(within(dialog).getByRole("button", { name: "تسجيل الاحتواء" })); });
    expect(sent("/quality/non-conformance-reports/n1/contain", "POST")).toEqual({ containment: "Lot quarantined" });
    expect(await screen.findByRole("button", { name: "تسجيل السبب الجذري" })).toBeTruthy();
  });

  it("closes a minor case from the investigation only with the reason no action is needed", async () => {
    api.apiClient.mockResolvedValue(report({ status: "investigation", actions: ["edit", "investigate", "add_action", "cancel"] }));
    ui(<NcrReportDetail ncrReportId="n1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Record root cause" }));
    const dialog = screen.getByRole("dialog", { name: "Root cause" });
    fireEvent.change(within(dialog).getByLabelText("Cause category (6M)"), { target: { value: "material" } });
    fireEvent.change(within(dialog).getByLabelText("Root cause"), { target: { value: "Silo not dried" } });
    fireEvent.click(within(dialog).getByLabelText(/no corrective action is needed/));
    const close = within(dialog).getByRole("button", { name: "Record and close" }) as HTMLButtonElement;
    expect(close.disabled).toBe(true);
    fireEvent.change(within(dialog).getByLabelText("Why no corrective action is needed"), { target: { value: "Isolated lot" } });
    await act(async () => { fireEvent.click(close); });
    expect(sent("/quality/non-conformance-reports/n1/investigate", "POST")).toEqual({ root_cause_category: "material", root_cause_method: null,
      root_cause: "Silo not dried", action_required: false, no_action_justification: "Isolated lot" });
  });

  it("completes an action with its evidence and verifies the result", async () => {
    api.apiClient.mockResolvedValue(report({ status: "action", root_cause: "Silo not dried", root_cause_category: "material",
      actions: ["edit", "add_action", "submit", "cancel"], corrective_actions: [action()] }));
    const first = ui(<NcrReportDetail ncrReportId="n1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Mark done" }));
    const dialog = screen.getByRole("dialog", { name: "Mark the action done" });
    fireEvent.change(within(dialog).getByLabelText(/Evidence/), { target: { value: "Release record shows the dryer check" } });
    await act(async () => { fireEvent.click(within(dialog).getByRole("button", { name: "Mark done" })); });
    expect(sent("/quality/non-conformance-reports/n1/actions/a1/complete", "POST")).toEqual({ evidence: "Release record shows the dryer check" });
    first.unmount();
    api.apiClient.mockResolvedValue(report({ status: "verification", actions: ["edit", "verify", "cancel"], corrective_actions: [action({ status: "done" })] }));
    ui(<NcrReportDetail ncrReportId="n1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Verify effectiveness" }));
    const verify = screen.getByRole("dialog", { name: "Verify effectiveness" });
    fireEvent.click(within(verify).getByLabelText("Not effective — back to actions"));
    const confirm = within(verify).getByRole("button", { name: "Verify effectiveness" }) as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);  // why it was not effective
    fireEvent.click(within(verify).getByLabelText("Effective — close the report"));
    expect((within(verify).getByLabelText(/Review again after/) as HTMLSelectElement).value).toBe("90");
    await act(async () => { fireEvent.click(confirm); });
    expect(sent("/quality/non-conformance-reports/n1/verify", "POST")).toEqual({ effective: true, notes: null, review_days: 90 });
  });
});

describe("corrective action follow-up", () => {
  const related = { id: "n0", report_number: "NCR-2026-0000", report_date: "2026-09-20", title: "Wet granules again", status: "closed" as const,
    severity: "major" as const, matched_on: ["supplier" as const, "item" as const], earlier: true };

  it("shows the reports a recurring problem repeats and needs a corrective action for it", async () => {
    api.apiClient.mockResolvedValue(report({ status: "investigation", actions: ["edit", "investigate", "add_action", "cancel"],
      recurrence: { window_days: 180, earlier: 2, since_closing: 0, recurring: true, related: [related, { ...related, id: "n9", report_number: "NCR-2026-0009" }] } }));
    ui(<NcrReportDetail ncrReportId="n1" />);
    const section = await screen.findByRole("region", { name: "Recurrence" });
    expect(within(section).getByText("Recurring")).toBeTruthy();
    expect(within(section).getByRole("link", { name: "NCR-2026-0000" }).getAttribute("href")).toBe("/non-conformance-reports/n0");
    expect(within(section).getAllByText("supplier، affected item").length).toBe(2);
    fireEvent.click(screen.getByRole("button", { name: "Record root cause" }));
    const dialog = screen.getByRole("dialog", { name: "Root cause" });
    expect(within(dialog).getByRole("status").textContent).toContain("not an isolated case");
    expect(within(dialog).queryByLabelText(/no corrective action is needed/)).toBeNull();
  });

  it("reviews a closed report's effectiveness later; not effective needs the reason", async () => {
    api.apiClient.mockResolvedValue(report({ status: "closed", actions: ["review_effectiveness"], review_pending: true, review_due: true,
      verified_at: "2026-07-01T10:00:00Z", verified_by_name: "Huda", effectiveness_due_date: "2026-09-29", closed_at: "2026-07-01T10:00:00Z",
      recurrence: { window_days: 180, earlier: 0, since_closing: 1, recurring: false, related: [{ ...related, earlier: false }] } }));
    ui(<NcrReportDetail ncrReportId="n1" />);
    expect((await screen.findAllByText(/The effectiveness review is due/)).length).toBe(1);
    expect(screen.getAllByText(/1 similar reports were raised after this one was closed/).length).toBe(1);
    fireEvent.click(screen.getByRole("button", { name: "Review effectiveness" }));
    const dialog = screen.getByRole("dialog", { name: "Effectiveness review" });
    fireEvent.click(within(dialog).getByLabelText("Not effective — it came back"));
    expect(within(dialog).getByText("The report reopens to its corrective actions.")).toBeTruthy();
    const confirm = within(dialog).getByRole("button", { name: "Record the review" }) as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);
    fireEvent.change(within(dialog).getByLabelText("Why it was not effective"), { target: { value: "Wet granules on lot SUP-7802" } });
    await act(async () => { fireEvent.click(confirm); });
    expect(sent("/quality/non-conformance-reports/n1/review-effectiveness", "POST")).toEqual({ effective: false, notes: "Wet granules on lot SUP-7802" });
  });

  it("verifies without a later review", async () => {
    api.apiClient.mockResolvedValue(report({ status: "verification", actions: ["edit", "verify", "cancel"], corrective_actions: [action({ status: "done" })] }));
    ui(<NcrReportDetail ncrReportId="n1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Verify effectiveness" }));
    const verify = screen.getByRole("dialog", { name: "Verify effectiveness" });
    fireEvent.click(within(verify).getByLabelText("Effective — close the report"));
    fireEvent.change(within(verify).getByLabelText(/Review again after/), { target: { value: "0" } });
    await act(async () => { fireEvent.click(within(verify).getByRole("button", { name: "Verify effectiveness" })); });
    expect(sent("/quality/non-conformance-reports/n1/verify", "POST")).toEqual({ effective: true, notes: null, review_days: 0 });
  });
});

describe("corrective actions list", () => {
  it("lists actions across reports with what is late", async () => {
    const rows = [action({ overdue: true, report_number: "NCR-2026-0001", report_title: "Wet PP granules" })];
    api.apiClient.mockImplementation((path: string) => Promise.resolve(path === "/quality/ncr-actions/alerts" ? []
      : { items: rows, total: 1, page: 1, page_size: 50, pages: 1 }));
    ui(<CorrectiveActionsList />, "ar");
    expect(await screen.findByRole("link", { name: "NCR-2026-0001" })).toBeTruthy();
    expect(screen.getAllByText("متأخر").length).toBeGreaterThan(0);
    // The list opens on the open actions, as one server page (ARCH-PAGE-001).
    expect(api.apiClient.mock.calls.map(([path]) => path)).toContain("/quality/ncr-actions?status=open&page=1&page_size=50");
    expect(screen.queryByRole("region", { name: "يحتاج متابعتك" })).toBeNull();  // no alerts in that answer
  });

  it("shows what needs the user's attention first", async () => {
    api.apiClient.mockImplementation((path: string) => Promise.resolve(path === "/quality/ncr-actions/alerts"
      ? { total: 2, open_actions: 3, overdue: 1, report_overdue: 0, review_due: 1, due_soon: 0, items: [
        { kind: "overdue", ncr_id: "n1", report_number: "NCR-2026-0001", title: "Dryer check before release", due_date: "2026-10-01" },
        { kind: "review_due", ncr_id: "n2", report_number: "NCR-2026-0002", title: "Torn cartons", due_date: "2026-10-04" }] }
      : []));
    ui(<CorrectiveActionsList />, "ar");
    const panel = await screen.findByRole("region", { name: "يحتاج متابعتك" });
    expect(within(panel).getByText("1 متأخرة")).toBeTruthy();
    expect(within(panel).getByText("1 مراجعات مستحقة")).toBeTruthy();
    expect(within(panel).getByRole("link", { name: "NCR-2026-0002" }).getAttribute("href")).toBe("/non-conformance-reports/n2");
  });
});
