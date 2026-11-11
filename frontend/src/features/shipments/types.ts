// Shipments and delivery notes (SHIP-001), delivery outcomes and returns (SHIP-004). Quantities and weights are decimal strings.
export type ShipmentStatus = "draft" | "ready" | "dispatched" | "delivered" | "partially_delivered" | "returned" | "not_delivered" | "cancelled";
export type DeliveryMethod = "pickup" | "factory_delivery" | "carrier";
export type ShipmentAction = "edit" | "ready" | "reopen" | "dispatch" | "deliver" | "fail" | "reschedule" | "close" | "cancel" | "return";

export const SHIPMENT_STATUSES: ShipmentStatus[] = ["draft", "ready", "dispatched", "delivered", "partially_delivered", "returned", "not_delivered", "cancelled"];
export const DELIVERY_METHODS: DeliveryMethod[] = ["factory_delivery", "pickup", "carrier"];

// What is shipped: description, width and thickness (mm), quantity in a unit from src/lib/units.ts, the full weight,
// and the production order (batch) it comes from.
export type ShipmentLineInput = {
  description: string; width_mm: string | null; thickness_mm: string | null; quantity: string; unit: string;
  weight: string | null; weight_unit: string; production_order_id?: string | null;
};
export type ShipmentLine = ShipmentLineInput & { id: string; line_no: number; production_order_no: string | null; delivered_quantity: string | null };

export type ShipmentHeader = {
  driver_id?: string|null; vehicle_id?: string|null; carrier_id?: string|null; driver_affiliation?: string|null; customer_contact_id?: string|null; delivery_site_id?: string|null;
  customer_id: string | null; customer_name: string | null; customer_reference: string | null;
  consignee_name: string | null; consignee_phone: string | null; consignee_email: string | null; notify_consignee: boolean;
  delivery_address: string | null; delivery_country?: string | null; delivery_city: string | null; location_url: string | null;
  driver_name: string | null; driver_phone: string | null; driver_id_no: string | null; vehicle_plate: string | null; vehicle_type: string | null;
  carrier_name: string | null; tracking_no: string | null; notes: string | null;
};

export type ShipmentInput = ShipmentHeader & { delivery_method: DeliveryMethod; shipment_date: string; lines: ShipmentLineInput[] };

export type HistoryEntry = { action: string; from_status: string | null; to_status: string; reason: string | null; actor_name: string | null; at: string;
  return_no?: string | null };

export type Attachment = { id: string; kind: string; file_name: string; content_type: string; size_bytes: number; uploaded_by_name: string | null; uploaded_at: string };

export type WeightCheck = { reference_kg: string; received_kg: string; difference_kg: string; difference_pct: string; tolerance_pct: string; within_tolerance: boolean };

export type ShipmentListItem = {
  driver_affiliation?:string|null;
  id: string; shipment_no: string; status: ShipmentStatus; delivery_method: DeliveryMethod; shipment_date: string;
  customer_id: string | null; customer_name: string; customer_reference: string | null; consignee_name: string | null; delivery_city: string | null;
  driver_name: string | null; vehicle_plate: string | null; carrier_name: string | null; dispatched_at: string | null; delivered_at: string | null;
  quantities: { unit: string; quantity: string }[]; weight_total_kg: string | null; attempt: number; open_returns: number;
  actions: ShipmentAction[]; created_at: string;
};

export type Shipment = ShipmentListItem & ShipmentHeader & {
  ready_at: string | null; received_by_name: string | null; delivery_notes: string | null; cancel_reason: string | null;
  close_reason: string | null; failed_at: string | null; gate_weight_kg: string | null; received_weight_kg: string | null;
  weight_check: WeightCheck | null; returns: ReturnSummary[]; line_returns: Record<string, { returned: string; returnable: string }>;
  attachments: Attachment[]; lines: ShipmentLine[]; missing_details: string[];
  created_by_name: string | null; dispatched_by_name: string | null; delivered_recorded_by_name: string | null;
  history: HistoryEntry[]; updated_at: string;
};

export type CustomerOption = { country?: string | null; id: string; customer_code: string; name: string; phone: string | null; email: string | null; city: string | null };
export type ProductionOrderOption = { id: string; number: string; product_type: string; status: string; planned_quantity: string; unit: string };

export type ShippingSettings = { note_prefix: string; return_prefix: string; return_window_days: number; weight_tolerance_pct: string };

// ── returns ─────────────────────────────────────────────────────────────────────────────────────
// delivery: not received at the door (a failed delivery, or the refused part of a partial one);
// customer: sent back by the customer after receiving the goods.
export type ReturnKind = "delivery" | "customer";
export type ReturnStatus = "requested" | "approved" | "rejected" | "received" | "cancelled";
export type ReturnAction = "approve" | "reject" | "receive" | "cancel";
export const RETURN_STATUSES: ReturnStatus[] = ["requested", "approved", "received", "rejected", "cancelled"];
export const DELIVERY_REASONS = ["customer_refused", "site_closed", "no_receiver", "wrong_address", "transit_damage", "quality_issue", "other"] as const;
export const CUSTOMER_REASONS = ["quality_defect", "spec_mismatch", "wrong_item", "transit_damage", "excess_quantity", "customer_cancelled", "other"] as const;
export type DeliveryReason = (typeof DELIVERY_REASONS)[number];
export type CustomerReason = (typeof CUSTOMER_REASONS)[number];

// Reasons that put the goods in question: quality inspects them on receipt (mirrors returns.QUALITY_REASONS).
export const QUALITY_REASONS = ["quality_issue", "quality_defect", "spec_mismatch", "transit_damage", "other"];
// Where returned goods stand once received: back in stock, or with quality (awaiting, inspecting, decided, done).
export type ReturnQualityStatus = "not_required" | "awaiting" | "inspecting" | "decided" | "done";
export type ReturnQuality = {
  expected: boolean;
  inspections: { id: string; inspection_code: string; status: string; result: string | null; return_line_id: string | null;
    qty_inspected: string; qty_accepted: string }[];
  decisions: { id: string; rejection_code: string; disposition: string | null; disposition_status: string; quantity: string; unit: string;
    return_line_id: string | null }[];
};

export type ReturnSummary = { id: string; return_no: string; kind: ReturnKind; status: ReturnStatus; reason: string; attempt: number; requested_at: string };

export type ReturnLine = {
  id: string; shipment_line_id: string; line_no: number; description: string; width_mm: string | null; thickness_mm: string | null;
  unit: string; weight_unit: string; production_order_no: string | null; quantity: string; weight: string | null;
  received_quantity: string | null; received_weight: string | null;
};

export type ReturnListItem = {
  id: string; return_no: string; kind: ReturnKind; status: ReturnStatus; shipment_id: string; shipment_no: string; attempt: number;
  customer_id: string | null; customer_name: string; reason: string; responsibility: string; customer_reference: string | null;
  requested_at: string; is_late: boolean; received_at: string | null; quantities: { unit: string; quantity: string }[]; weight_kg: string | null;
  quality_required: boolean; quality_status: ReturnQualityStatus | null; actions: ReturnAction[];
};

export type ShipmentReturn = ReturnListItem & {
  details: string | null; carrier_claim_ref: string | null; delivery_method: DeliveryMethod; delivered_at: string | null;
  decided_at: string | null; decision_note: string | null; receipt_notes: string | null; cancel_reason: string | null;
  received_weight_kg: string | null; created_by_name: string | null; decided_by_name: string | null; received_by_name: string | null;
  lines: ReturnLine[]; history: HistoryEntry[]; attachments: Attachment[]; quality: ReturnQuality | null; updated_at: string;
};

export type ReturnInput = {
  shipment_id: string; reason: CustomerReason; details: string | null; customer_reference: string | null; carrier_claim_ref: string | null;
  lines: { shipment_line_id: string; quantity: string; weight: string | null }[];
};
