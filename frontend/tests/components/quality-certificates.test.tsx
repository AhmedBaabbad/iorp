// QUAL-COA-001: certificates of analysis — prepared from a closed inspection, completed, approved and numbered.
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";
import type { Certificate } from "@/features/quality-certificates/types";

const api = vi.hoisted(() => ({ apiClient: vi.fn() }));
const nav = vi.hoisted(() => ({ push: vi.fn() }));
const perms = vi.hoisted(() => ({ granted: new Set<string>() }));
vi.mock("@/lib/api-client", async importOriginal => ({ ...(await importOriginal<object>()), apiClient: api.apiClient }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: nav.push, replace: vi.fn() }), usePathname: () => "/", useSearchParams: () => new URLSearchParams() }));
vi.mock("@/features/auth/permission-hooks", () => ({ usePermission: (code: string) => perms.granted.has(code) }));
vi.mock("@/hooks/useFormatter", () => ({ useFormatter: () => ({ date: (v: string) => v, dateTime: (v: string) => v, number: (v: string) => v, quantity: (v: string, u?: string) => `${v} ${u ?? ""}`.trim() }) }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) => <main><h1>{title}</h1>{action}{children}</main> }));

import { CertificateDetail } from "@/features/quality-certificates/components/CertificateDetail";
import { CheckCertificatesSection } from "@/features/quality-certificates/components/CheckCertificatesSection";
import { Q } from "@/lib/quality-permissions";

let en: Record<string, unknown>;
let ar: Record<string, unknown>;
beforeAll(async () => { en = await loadMessages("en") as Record<string, unknown>; ar = await loadMessages("ar") as Record<string, unknown>; });
beforeEach(() => { api.apiClient.mockReset(); nav.push.mockReset(); perms.granted = new Set(Object.values(Q)); });
afterEach(cleanup);
const ui = (node: ReactNode, locale: "en" | "ar" = "en") =>
  render(<NextIntlClientProvider locale={locale} messages={locale === "en" ? en : ar} timeZone="UTC">{node}</NextIntlClientProvider>);
const call = (path: string, method: string) => api.apiClient.mock.calls.find(([p, o]) => p === path && o?.method === method)?.[1]?.body;

function certificate(over: Partial<Certificate> = {}): Certificate {
  return { id: "c1", certificate_no: null, status: "draft", quality_check_id: "k1", production_order_id: "po1", customer_name: "UCIC Company",
    batch_no: "PO-2026-000001-L1", product_description: "PP Strap 5 × 0.35 mm × 10 kg", quantity: "120.000", unit_label: "roll", inspection_code: "QI-2026-0001",
    issued_at: null, issued_by_name: null, supersedes_no: null, superseded_by_no: null, actions: ["edit", "issue"], created_at: "",
    production_order_item_id: "l1", customer_id: "cu1", customer_po: null, delivery_ref: null, grade: "Full Automatic", production_date: "2026-10-03",
    inspection_date: "2026-10-03", package_count: null, sample_size: "12 roll", sampling_reference: null, retained_sample: false, retention_ref: null,
    deviation_note: null, remarks: null, inspection_result: "accepted", specification_code: "ROF-TDS-PP-001", specification_revision: 1,
    measurements: [{ code: "WIDTH", name_ar: "العرض", name_en: "Width", kind: "numeric", unit: "mm", method: "Calibrated vernier caliper", requirement: null,
      acceptance: null, target: "5", lower: "4.8", upper: "5.2", count: 3, minimum: "4.9", maximum: "5.1", mean: "5", attribute_result: null, observation: null, status: "pass" }],
    inspector_name: "Shafi", supersedes_id: null, prepared_by_name: "Shafi", revoked_at: null, revoked_by_name: null, revoke_reason: null, history: [], ...over };
}

describe("certificate", () => {
  it("completes a draft, then approves and numbers it", async () => {
    const issued = certificate({ certificate_no: "ROF-COA-0013", status: "issued", issued_at: "2026-10-03T20:00:00Z", issued_by_name: "Ahmed", actions: ["revoke", "replace"] });
    api.apiClient.mockImplementation((path: string, o?: { method?: string; body?: object }) => Promise.resolve(
      o?.method === "POST" ? issued : o?.method === "PATCH" ? certificate({ customer_po: "UCIC-PO-4471" }) : certificate()));
    ui(<CertificateDetail certificateId="c1" />);
    expect(await screen.findByText("5 (4.9 – 5.1, n=3)")).toBeTruthy();
    expect(screen.getByText("4.8 – 5.2")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Customer PO"), { target: { value: "UCIC-PO-4471" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Save" })); });
    expect(call("/quality/quality-certificates/c1", "PATCH")).toMatchObject({ customer_po: "UCIC-PO-4471", customer_name: "UCIC Company", batch_no: "PO-2026-000001-L1" });
    fireEvent.click(screen.getByRole("button", { name: "Approve and issue" }));
    const dialog = screen.getByRole("dialog", { name: "Approve and issue the certificate" });
    await act(async () => { fireEvent.click(within(dialog).getByRole("button", { name: "Approve and issue" })); });
    expect(await screen.findByRole("heading", { name: "ROF-COA-0013" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Save" })).toBeNull();  // issued certificates are final
    expect(screen.getByRole("button", { name: "Corrected replacement" })).toBeTruthy();
  });

  it("asks for the approved deviation on a conditional acceptance, in Arabic", async () => {
    api.apiClient.mockResolvedValue(certificate({ inspection_result: "conditional_accept" }));
    ui(<CertificateDetail certificateId="c1" />, "ar");
    expect(await screen.findByLabelText("الانحراف المعتمد")).toBeTruthy();
    expect(screen.getByText("مسودة غير صالحة للإرسال: أكمل البيانات ثم «اعتماد وإصدار» لتأخذ رقمها.")).toBeTruthy();
  });
});

describe("certificates on an inspection", () => {
  it("prepares a draft for the lot's customer", async () => {
    api.apiClient.mockImplementation((path: string, o?: { method?: string }) => Promise.resolve(
      path.includes("/sources") ? { certifiable: true, blocker: null, customers: [{ id: "cu1", name: "UCIC Company" }] }
        : o?.method === "POST" ? certificate() : { items: [], total: 0, page: 1, page_size: 100, pages: 0 }));
    ui(<CheckCertificatesSection checkId="k1" />);
    fireEvent.change(await screen.findByLabelText("Customer PO"), { target: { value: "PO-1" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Prepare certificate" })); });
    expect(call("/quality/quality-certificates", "POST")).toEqual({ quality_check_id: "k1", customer_id: "cu1", customer_po: "PO-1" });
    expect(nav.push).toHaveBeenCalledWith("/quality-certificates/c1");
  });

  it("explains why an inspection cannot be certified", async () => {
    api.apiClient.mockImplementation((path: string) => Promise.resolve(path.includes("/sources")
      ? { certifiable: false, blocker: "CERTIFICATE_NEEDS_MEASUREMENTS", customers: [] } : { items: [], total: 0, page: 1, page_size: 100, pages: 0 }));
    ui(<CheckCertificatesSection checkId="k1" />);
    expect(await screen.findByText(/has no measurement plan/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Prepare certificate" })).toBeNull();
  });
});
