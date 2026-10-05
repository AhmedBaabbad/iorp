import { apiClient } from "@/lib/api-client";
import type {
  Attachment, CustomerOption, DeliveryMethod, DeliveryReason, ProductionOrderOption, ReturnInput, ReturnKind, ReturnListItem, ReturnStatus,
  Shipment, ShipmentInput, ShipmentListItem, ShipmentReturn, ShipmentStatus, ShippingSettings,
} from "./types";

const PATH = "/shipping/shipments";
const RETURNS = "/shipping/returns";

const query = (filters: Record<string, string | undefined>) => {
  const q = new URLSearchParams(Object.entries(filters).filter(([, v]) => Boolean(v)) as [string, string][]);
  return q.size ? `?${q}` : "";
};

export type ShipmentFilters = { status?: ShipmentStatus | ""; method?: DeliveryMethod | ""; date_from?: string; date_to?: string; search?: string };

export const getShipments = (filters: ShipmentFilters = {}) => apiClient<ShipmentListItem[]>(`${PATH}${query(filters)}`);
export const getShipment = (id: string) => apiClient<Shipment>(`${PATH}/${id}`);
// Registered customers, with the contacts a delivery note copies.
export const getShippingCustomers = (search = "") => apiClient<CustomerOption[]>(`${PATH}/lookups/customers?q=${encodeURIComponent(search)}`);
// Production orders a line may come from (its batch).
export const getShippingProductionOrders = (search = "") =>
  apiClient<ProductionOrderOption[]>(`${PATH}/lookups/production-orders?q=${encodeURIComponent(search)}`);
export const createShipment = (body: ShipmentInput) => apiClient<Shipment>(PATH, { method: "POST", body });
export const updateShipment = (id: string, body: Partial<ShipmentInput>) => apiClient<Shipment>(`${PATH}/${id}`, { method: "PATCH", body });

// Lifecycle: ready for loading, back to draft, left the factory, received (in full or in part), not received and coming
// back, set out again under the same number, closed as not delivered, cancelled before leaving.
export type DispatchBody = { gate_weight?: string | null; gate_weight_unit?: string };
export type DeliverBody = {
  received_by_name: string; received_at?: string | null; delivery_notes?: string | null;
  lines?: { line_id: string; delivered_quantity: string }[]; refusal_reason?: DeliveryReason | null; refusal_details?: string | null;
  received_weight?: string | null; received_weight_unit?: string;
};
export type RescheduleBody = Partial<Pick<ShipmentInput, "delivery_method" | "shipment_date" | "driver_name" | "driver_phone" | "driver_id_no"
  | "vehicle_plate" | "vehicle_type" | "carrier_name" | "tracking_no">>;
const step = <B,>(id: string, name: string, body?: B) => apiClient<Shipment>(`${PATH}/${id}/${name}`, { method: "POST", body });
export const readyShipment = (id: string) => step(id, "ready");
export const reopenShipment = (id: string) => step(id, "reopen");
export const dispatchShipment = (id: string, body: DispatchBody = {}) => step(id, "dispatch", body);
export const deliverShipment = (id: string, body: DeliverBody) => step(id, "deliver", body);
export const failShipment = (id: string, body: { reason: DeliveryReason; details: string | null }) => step(id, "fail", body);
export const rescheduleShipment = (id: string, body: RescheduleBody) => step(id, "reschedule", body);
export const closeShipment = (id: string, reason: string) => step(id, "close", { reason });
export const cancelShipment = (id: string, reason: string) => step(id, "cancel", { reason });

export const getShippingSettings = () => apiClient<ShippingSettings>("/shipping/settings");
export const updateShippingSettings = (body: Partial<ShippingSettings>) => apiClient<ShippingSettings>("/shipping/settings", { method: "PATCH", body });

// ── returns ─────────────────────────────────────────────────────────────────────────────────────
export type ReturnFilters = { status?: ReturnStatus | ""; kind?: ReturnKind | ""; shipment_id?: string; date_from?: string; date_to?: string; search?: string };
export const getReturns = (filters: ReturnFilters = {}) => apiClient<ReturnListItem[]>(`${RETURNS}${query(filters)}`);
export const getReturn = (id: string) => apiClient<ShipmentReturn>(`${RETURNS}/${id}`);
export const createReturn = (body: ReturnInput) => apiClient<ShipmentReturn>(RETURNS, { method: "POST", body });
const returnStep = <B,>(id: string, name: string, body: B) => apiClient<ShipmentReturn>(`${RETURNS}/${id}/${name}`, { method: "POST", body });
export const approveReturn = (id: string, note: string | null) => returnStep(id, "approve", { note });
export const rejectReturn = (id: string, reason: string) => returnStep(id, "reject", { reason });
export const cancelReturn = (id: string, reason: string) => returnStep(id, "cancel", { reason });
export type ReceiveBody = { notes: string | null; lines: { return_line_id: string; received_quantity: string; received_weight: string | null }[] };
export const receiveReturn = (id: string, body: ReceiveBody) => returnStep(id, "receive", body);

// ── files: the signed note (proof of delivery), photos of returned goods ────────────────────────
export type AttachmentOwner = { kind: "shipment" | "return"; id: string };
const filesOf = (owner: AttachmentOwner) => `${owner.kind === "shipment" ? PATH : RETURNS}/${owner.id}/attachments`;
export function uploadAttachment(owner: AttachmentOwner, file: File, kind: string) {
  const body = new FormData();
  body.append("kind", kind);
  body.append("file", file);
  return apiClient<Attachment[]>(filesOf(owner), { method: "POST", body });
}
export const removeAttachment = (owner: AttachmentOwner, attachmentId: string) =>
  apiClient<Attachment[]>(`${filesOf(owner)}/${attachmentId}`, { method: "DELETE" });
export async function openAttachment(owner: AttachmentOwner, attachment: Attachment) {
  const response = await apiClient<Response>(`${filesOf(owner)}/${attachment.id}`, { raw: true });
  const url = URL.createObjectURL(await response.blob());
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

async function save(path: string, fallback: string) {
  const response = await apiClient<Response>(path, { raw: true });
  const disposition = response.headers.get("content-disposition") ?? "";
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = encoded ? decodeURIComponent(encoded) : fallback;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export const downloadDeliveryNote = (id: string, lang: "ar" | "en") => save(`${PATH}/${id}/document.pdf?lang=${lang}`, `delivery-note-${lang}.pdf`);
export const downloadReturnNote = (id: string, lang: "ar" | "en") => save(`${RETURNS}/${id}/document.pdf?lang=${lang}`, `return-note-${lang}.pdf`);
