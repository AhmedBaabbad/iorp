// SHIP-001, SHIP-004: shipments — a delivery note for a registered or named customer, its transport, items and lifecycle;
// delivery outcomes (in part, not received, sent again) and returns against a delivery note.
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { loadMessages } from "@/i18n/messages";
import { ApiClientError } from "@/lib/api-client";
import type { Shipment, ShipmentReturn } from "@/features/shipments/types";

const api = vi.hoisted(() => ({ apiClient: vi.fn() }));
const nav = vi.hoisted(() => ({ push: vi.fn() }));
const perms = vi.hoisted(() => ({ granted: new Set<string>() }));
vi.mock("@/lib/api-client", async importOriginal => ({ ...(await importOriginal<object>()), apiClient: api.apiClient }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: nav.push, replace: vi.fn() }), usePathname: () => "/", useSearchParams: () => new URLSearchParams() }));
vi.mock("@/features/auth/permission-hooks", () => ({ usePermission: (code: string) => perms.granted.has(code),
  useHasAnyPermission: (codes: string[]) => codes.some(code => perms.granted.has(code)) }));
vi.mock("@/hooks/useFormatter", () => ({ useFormatter: () => ({ date: (v: string) => v, dateTime: (v: string) => v, number: (v: string) => v, quantity: (v: string, u?: string) => `${Number(v)} ${u ?? ""}`.trim() }) }));
vi.mock("@/components/layout/page-frame", () => ({ PageFrame: ({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) => <main><h1>{title}</h1>{action}{children}</main> }));

import { ReturnDetail } from "@/features/shipments/components/ReturnDetail";
import { ReturnForm } from "@/features/shipments/components/ReturnForm";
import { ReturnsList } from "@/features/shipments/components/ReturnsList";
import { ShipmentDetail } from "@/features/shipments/components/ShipmentDetail";
import { ShipmentForm } from "@/features/shipments/components/ShipmentForm";
import { S } from "@/lib/shipping-permissions";

let en: Record<string, unknown>;
let ar: Record<string, unknown>;
beforeAll(async () => { en = await loadMessages("en") as Record<string, unknown>; ar = await loadMessages("ar") as Record<string, unknown>; });
beforeEach(() => { api.apiClient.mockReset(); nav.push.mockReset(); perms.granted = new Set(Object.values(S)); });
afterEach(cleanup);
const ui = (node: ReactNode, locale: "en" | "ar" = "en") =>
  render(<NextIntlClientProvider locale={locale} messages={locale === "en" ? en : ar} timeZone="UTC">{node}</NextIntlClientProvider>);
const sent = (path: string, method: string) => api.apiClient.mock.calls.find(([p, o]) => p === path && o?.method === method)?.[1]?.body;

function shipment(over: Partial<Shipment> = {}): Shipment {
  return { id: "s1", shipment_no: "DN-2026-0001", status: "draft", delivery_method: "factory_delivery", shipment_date: "2026-10-04", customer_id: "c1",
    customer_name: "UCIC Company", customer_reference: "UCIC-PO-77", consignee_name: null, consignee_phone: "+966551234567", consignee_email: null,
    notify_consignee: false, delivery_address: null, delivery_city: "Riyadh", location_url: null, driver_name: null, driver_phone: null, driver_id_no: null,
    vehicle_plate: null, vehicle_type: null, carrier_name: null, tracking_no: null, notes: null, dispatched_at: null, delivered_at: null,
    quantities: [{ unit: "roll", quantity: "120.000" }], weight_total_kg: "1200.000", actions: ["edit", "ready", "cancel"], created_at: "", ready_at: null,
    received_by_name: null, delivery_notes: null, cancel_reason: null,
    missing_details: ["driver_name", "vehicle_plate"], created_by_name: "Ahmed", dispatched_by_name: null, delivered_recorded_by_name: null,
    history: [{ action: "created", from_status: null, to_status: "draft", reason: null, actor_name: "Ahmed", at: "2026-10-04T08:00:00Z" }], updated_at: "",
    lines: [{ id: "l1", line_no: 1, description: "PP Strap black", width_mm: "5.000", thickness_mm: "0.350", quantity: "120.000", unit: "roll",
      weight: "1.200", weight_unit: "ton", production_order_id: null, production_order_no: null, delivered_quantity: null }],
    attempt: 1, open_returns: 0, close_reason: null, failed_at: null, gate_weight_kg: null, received_weight_kg: null, weight_check: null,
    returns: [], line_returns: {}, attachments: [], ...over };
}

describe("shipment form", () => {
  it("creates a delivery note for an unregistered, named customer with its transport and items", async () => {
    api.apiClient.mockImplementation((path: string, o?: { method?: string }) => Promise.resolve(o?.method === "POST" ? shipment() : []));
    ui(<ShipmentForm />);
    fireEvent.click(screen.getByLabelText("Unregistered customer"));
    fireEvent.change(screen.getByLabelText("Customer name"), { target: { value: "Walk-in buyer" } });
    fireEvent.change(screen.getByLabelText("Delivery method"), { target: { value: "pickup" } });
    fireEvent.change(screen.getByLabelText("Collected by"), { target: { value: "Fahad" } });
    fireEvent.change(screen.getByLabelText("Vehicle plate"), { target: { value: "أ ب ج 1234" } });
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "PP Strap 15 mm" } });
    fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "40" } });
    fireEvent.change(screen.getByLabelText("Width (mm)"), { target: { value: "15" } });
    fireEvent.change(screen.getByLabelText("Thickness (mm)"), { target: { value: "0.85" } });
    fireEvent.change(screen.getByLabelText("Weight"), { target: { value: "0.26" } });
    fireEvent.change(screen.getByLabelText("Weight unit"), { target: { value: "ton" } });
    expect(screen.getByText("Total weight: 260 kg")).toBeTruthy();
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Save draft" })); });
    expect(sent("/shipping/shipments", "POST")).toMatchObject({ customer_id: null, customer_name: "Walk-in buyer", delivery_method: "pickup",
      driver_name: "Fahad", vehicle_plate: "أ ب ج 1234", notify_consignee: false,
      lines: [{ description: "PP Strap 15 mm", width_mm: "15", thickness_mm: "0.85", quantity: "40", unit: "roll", weight: "0.26", weight_unit: "ton" }] });
    expect(nav.push).toHaveBeenCalledWith("/shipments/s1");
  });

  it("chooses a registered customer and shows the contacts it brings", async () => {
    api.apiClient.mockResolvedValue([{ id: "c1", customer_code: "C-1", name: "UCIC Company", phone: "0551234567", email: "orders@ucic.example", city: "Riyadh" }]);
    ui(<ShipmentForm />, "ar");
    await screen.findByRole("option", { name: "UCIC Company — C-1" });  // the list arrives after the search pause
    fireEvent.change(screen.getByLabelText("العميل", { selector: "select" }), { target: { value: "c1" } });
    expect(await screen.findByText(/0551234567 · orders@ucic.example/)).toBeTruthy();
    const save = screen.getByRole("button", { name: "حفظ المسودة" }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);  // an item is still needed
    fireEvent.change(screen.getByLabelText("الوصف"), { target: { value: "PP Strap 5 mm" } });
    fireEvent.change(screen.getByLabelText("الكمية"), { target: { value: "120" } });
    expect(save.disabled).toBe(false);
  });
});

describe("shipment detail", () => {
  it("names the missing transport details and explains the server's refusal", async () => {
    api.apiClient.mockImplementation((path: string, o?: { method?: string }) => o?.method === "POST"
      ? Promise.reject(new ApiClientError("x", 400, { detail: { code: "METHOD_DETAILS_REQUIRED", fields: "driver_name,vehicle_plate" } }))
      : Promise.resolve(shipment()));
    ui(<ShipmentDetail shipmentId="s1" />, "ar");
    expect(await screen.findByText("لتجهيز الشحنة أكمل: اسم السائق، رقم اللوحة")).toBeTruthy();
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "جاهزة للتحميل" })); });
    expect(screen.getByRole("alert").textContent).toBe("أكمل بيانات النقل: اسم السائق، رقم اللوحة");
  });

  it("dispatches, then confirms delivery with the receiver's name", async () => {
    const ready = shipment({ status: "ready", driver_name: "Saleh", vehicle_plate: "1234", missing_details: [], actions: ["reopen", "dispatch", "cancel"] });
    const left = { ...ready, status: "dispatched" as const, dispatched_at: "2026-10-04T09:00:00Z", actions: ["deliver" as const] };
    const done = { ...left, status: "delivered" as const, received_by_name: "Khalid", delivered_at: "2026-10-04T12:00:00Z", actions: [] };
    api.apiClient.mockImplementation((path: string) => Promise.resolve(path.endsWith("/dispatch") ? left : path.endsWith("/deliver") ? done : ready));
    ui(<ShipmentDetail shipmentId="s1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Record dispatch" }));
    const dialog = screen.getByRole("dialog", { name: "Record the dispatch" });
    expect(within(dialog).getByText(/Saleh — 1234/)).toBeTruthy();
    await act(async () => { fireEvent.click(within(dialog).getByRole("button", { name: "Record dispatch" })); });
    fireEvent.click(await screen.findByRole("button", { name: "Confirm delivery" }));
    const deliver = screen.getByRole("dialog", { name: "Confirm delivery" });
    fireEvent.change(within(deliver).getByLabelText("Received by"), { target: { value: "Khalid" } });
    await act(async () => { fireEvent.click(within(deliver).getByRole("button", { name: "Confirm" })); });
    expect(sent("/shipping/shipments/s1/deliver", "POST")).toEqual({ received_by_name: "Khalid", delivery_notes: null, lines: [], refusal_reason: null,
      refusal_details: null, received_weight: null, received_weight_unit: "kg" });
    expect(await screen.findByText("Delivered", { selector: "span" })).toBeTruthy();
  });

  it("hides what the user may not do", async () => {
    perms.granted = new Set([S.SHIPMENTS_READ]);
    api.apiClient.mockResolvedValue(shipment({ actions: [] }));
    ui(<ShipmentDetail shipmentId="s1" />);
    await screen.findByText("DN-2026-0001");
    expect(screen.queryByRole("button", { name: "Ready for loading" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Edit" })).toBeNull();
  });
});

describe("shipment lines", () => {
  it("has only description, width, thickness, quantity with its unit and one weight with its unit", async () => {
    api.apiClient.mockResolvedValue([]);
    ui(<ShipmentForm />, "ar");
    for (const label of ["الوصف", "العرض (مم)", "السماكة (مم)", "الكمية", "الوزن"]) expect(screen.getByLabelText(label)).toBeTruthy();
    for (const gone of ["الوزن الصافي", "الوزن الإجمالي", "عدد العبوات", "نوع العبوة", "رقم الدفعة"]) expect(screen.queryByLabelText(gone)).toBeNull();
    const unit = screen.getByLabelText("الوحدة", { selector: "select" });
    for (const name of ["لفة", "كيلوجرام (كجم)", "طن", "طبلية", "متر طولي (م.ط)", "قطعة"]) expect(within(unit).getByRole("option", { name })).toBeTruthy();
    const weight = screen.getByLabelText("وحدة الوزن", { selector: "select" }) as HTMLSelectElement;
    expect(Array.from(weight.options).map(o => o.value).filter(Boolean)).toEqual(["g", "kg", "ton", "lb", "oz"]);
    expect(weight.value).toBe("kg");
  });

  it("shows width, thickness and the weight with its unit on the detail", async () => {
    api.apiClient.mockResolvedValue(shipment());
    ui(<ShipmentDetail shipmentId="s1" />, "ar");
    expect(await screen.findByText("0.35")).toBeTruthy();
    expect(screen.getByText("1.2 طن")).toBeTruthy();
    expect(screen.getByText("الإجمالي: 120 لفة · الوزن 1200 كجم")).toBeTruthy();
  });
});

const onTheRoad = (over: Partial<Shipment> = {}) => shipment({ status: "dispatched", driver_name: "Saleh", vehicle_plate: "1234", missing_details: [],
  dispatched_at: "2026-10-04T09:00:00Z", actions: ["deliver", "fail"], ...over });

describe("delivery outcomes", () => {
  it("records a partial delivery: the refused quantity and why", async () => {
    api.apiClient.mockResolvedValue(onTheRoad());
    ui(<ShipmentDetail shipmentId="s1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Confirm delivery" }));
    const dialog = screen.getByRole("dialog", { name: "Confirm delivery" });
    fireEvent.change(within(dialog).getByLabelText("Received by"), { target: { value: "Khalid" } });
    fireEvent.change(within(dialog).getByLabelText("Received 1"), { target: { value: "100" } });
    expect(within(dialog).getByText("Refused: 1: 20 roll. It comes back under a return note.")).toBeTruthy();
    const confirm = within(dialog).getByRole("button", { name: "Confirm" }) as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);  // the reason is required
    fireEvent.change(within(dialog).getByLabelText("Why was part refused?"), { target: { value: "quality_issue" } });
    fireEvent.change(within(dialog).getByLabelText("Weight received (customer weighbridge, optional)"), { target: { value: "1180" } });
    await act(async () => { fireEvent.click(confirm); });
    expect(sent("/shipping/shipments/s1/deliver", "POST")).toEqual({ received_by_name: "Khalid", delivery_notes: null,
      lines: [{ line_id: "l1", delivered_quantity: "100" }], refusal_reason: "quality_issue", refusal_details: null, received_weight: "1180", received_weight_unit: "kg" });
  });

  it("records a failed delivery with its reason", async () => {
    api.apiClient.mockResolvedValue(onTheRoad());
    ui(<ShipmentDetail shipmentId="s1" />, "ar");
    fireEvent.click(await screen.findByRole("button", { name: "لم تُستلم — راجعة" }));
    const dialog = screen.getByRole("dialog", { name: "لم تُستلم" });
    fireEvent.change(within(dialog).getByLabelText("السبب"), { target: { value: "site_closed" } });
    await act(async () => { fireEvent.click(within(dialog).getByRole("button", { name: "تسجيل" })); });
    expect(sent("/shipping/shipments/s1/fail", "POST")).toEqual({ reason: "site_closed", details: null });
  });

  it("explains a returning note, then sends it again under the same number with another driver", async () => {
    const coming = onTheRoad({ status: "returned", actions: [], returns: [{ id: "r1", return_no: "RT-2026-0003", kind: "delivery", status: "approved",
      reason: "site_closed", attempt: 1, requested_at: "" }] });
    api.apiClient.mockResolvedValueOnce(coming);
    const first = ui(<ShipmentDetail shipmentId="s1" />, "ar");
    expect(await screen.findByText("لم تُستلم: البضاعة راجعة بالمرتجع RT-2026-0003. استلمها في المصنع ثم أعد إرسال الإشعار أو أغلقه.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "RT-2026-0003" }).getAttribute("href")).toBe("/shipment-returns/r1");
    first.unmount();
    const back = { ...coming, actions: ["reschedule", "close"] as Shipment["actions"], returns: [{ ...coming.returns[0], status: "received" as const }] };
    api.apiClient.mockResolvedValue(back);
    ui(<ShipmentDetail shipmentId="s1" />);
    expect(await screen.findByText(/The goods are back at the factory/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Send again" }));
    const dialog = screen.getByRole("dialog", { name: "Send the note again" });
    expect(within(dialog).getByText(/attempt 2/)).toBeTruthy();
    fireEvent.change(within(dialog).getByLabelText("Driver"), { target: { value: "Fahad" } });
    await act(async () => { fireEvent.click(within(dialog).getByRole("button", { name: "Ready for loading" })); });
    expect(sent("/shipping/shipments/s1/reschedule", "POST")).toMatchObject({ driver_name: "Fahad", vehicle_plate: "1234", delivery_method: "factory_delivery" });
  });

  it("shows the weight check and keeps the signed note", async () => {
    api.apiClient.mockResolvedValue(onTheRoad({ status: "delivered", actions: ["return"], gate_weight_kg: "1420.000", received_weight_kg: "1395.000",
      weight_check: { reference_kg: "1420.000", received_kg: "1395.000", difference_kg: "-25.000", difference_pct: "-1.76", tolerance_pct: "1.00", within_tolerance: false },
      attachments: [{ id: "a1", kind: "proof_of_delivery", file_name: "signed.pdf", content_type: "application/pdf", size_bytes: 9, uploaded_by_name: "Ahmed", uploaded_at: "" }] }));
    ui(<ShipmentDetail shipmentId="s1" />);
    expect(await screen.findByText("Outside the tolerance (1%) — check with the customer")).toBeTruthy();
    expect(screen.getByText("signed.pdf")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Register a customer return" }).getAttribute("href")).toBe("/shipment-returns/new?shipment=s1");
  });
});

function customerReturn(over: Partial<ShipmentReturn> = {}): ShipmentReturn {
  return { id: "r1", return_no: "RT-2026-0001", kind: "customer", status: "requested", shipment_id: "s1", shipment_no: "DN-2026-0001", attempt: 1,
    customer_id: "c1", customer_name: "UCIC Company", reason: "quality_defect", responsibility: "factory", customer_reference: "RMA-9", requested_at: "",
    is_late: false, received_at: null, quantities: [{ unit: "roll", quantity: "20.000" }], weight_kg: "200.000", actions: ["approve", "reject", "cancel"],
    quality_required: false, quality_status: null, quality: null,
    details: null, carrier_claim_ref: null, delivery_method: "factory_delivery", delivered_at: null, decided_at: null, decision_note: null, receipt_notes: null,
    cancel_reason: null, received_weight_kg: null, created_by_name: "Ahmed", decided_by_name: null, received_by_name: null, history: [], attachments: [],
    lines: [{ id: "rl1", shipment_line_id: "l1", line_no: 1, description: "PP Strap black", width_mm: "5.000", thickness_mm: "0.350", unit: "roll",
      weight_unit: "kg", production_order_no: "PO-2026-000014", quantity: "20.000", weight: "200.000", received_quantity: null, received_weight: null }],
    updated_at: "", ...over };
}

describe("returns", () => {
  it("registers a customer return against a delivered note, up to what may still be returned", async () => {
    const note = shipment({ status: "delivered", actions: ["return"], delivered_at: new Date().toISOString(),
      line_returns: { l1: { returned: "0.000", returnable: "120.000" } } });
    api.apiClient.mockImplementation((path: string, o?: { method?: string }) => Promise.resolve(
      o?.method === "POST" ? customerReturn() : path === "/shipping/settings" ? { return_window_days: 30 } : note));
    ui(<ReturnForm shipmentId="s1" />);
    const quantity = await screen.findByLabelText("Quantity to return 1");
    const create = screen.getByRole("button", { name: "Register the return" }) as HTMLButtonElement;
    fireEvent.change(quantity, { target: { value: "150" } });
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "quality_defect" } });
    expect(create.disabled).toBe(true);
    fireEvent.change(quantity, { target: { value: "20" } });
    await act(async () => { fireEvent.click(create); });
    expect(sent("/shipping/returns", "POST")).toEqual({ shipment_id: "s1", reason: "quality_defect", details: null, customer_reference: "UCIC-PO-77",
      carrier_claim_ref: null, lines: [{ shipment_line_id: "l1", quantity: "20", weight: null }] });
    expect(nav.push).toHaveBeenCalledWith("/shipment-returns/r1");
  });

  it("approves a late return only with a note, and receives what actually arrived", async () => {
    api.apiClient.mockResolvedValue(customerReturn({ is_late: true }));
    const first = ui(<ReturnDetail returnId="r1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    const approve = screen.getByRole("dialog", { name: "Approve the return" });
    expect(within(approve).getByText("A late return: write why it is accepted.")).toBeTruthy();
    expect((within(approve).getByRole("button", { name: "Approve" }) as HTMLButtonElement).disabled).toBe(true);
    first.unmount();
    api.apiClient.mockResolvedValue(customerReturn({ status: "approved", actions: ["receive", "cancel"] }));
    ui(<ReturnDetail returnId="r1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Receive at the factory" }));
    const dialog = screen.getByRole("dialog", { name: "Receive the returned goods" });
    fireEvent.change(within(dialog).getByLabelText("Received 1"), { target: { value: "18" } });
    expect((within(dialog).getByLabelText("Send to quality") as HTMLInputElement).disabled).toBe(true);  // a quality reason
    await act(async () => { fireEvent.click(within(dialog).getByRole("button", { name: "Received" })); });
    expect(sent("/shipping/returns/r1/receive", "POST")).toEqual({ notes: null, send_to_quality: true,
      lines: [{ return_line_id: "rl1", received_quantity: "18", received_weight: "200" }] });
  });

  it("lists returns with their delivery note, kind and responsibility", async () => {
    api.apiClient.mockResolvedValue([customerReturn({ kind: "delivery", reason: "customer_refused", responsibility: "customer", status: "approved" })]);
    ui(<ReturnsList />, "ar");
    expect(await screen.findByRole("link", { name: "RT-2026-0001" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "DN-2026-0001" }).getAttribute("href")).toBe("/shipments/s1");
    for (const text of ["مرتجع قبل الاستلام", "رفض العميل الاستلام", "العميل", "معتمد — بانتظار الاستلام"]) expect(screen.getAllByText(text).length).toBeGreaterThan(0);
  });
});
