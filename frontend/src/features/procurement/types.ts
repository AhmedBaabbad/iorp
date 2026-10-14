// Procurement (PROC-001): suppliers, materials and goods receipts. Quantities and weights are decimal strings.
export type SupplierStatus = "pending" | "approved" | "conditional" | "blocked";
export const SUPPLIER_STATUSES: SupplierStatus[] = ["pending", "approved", "conditional", "blocked"];
export const SUPPLIER_CATEGORIES = ["raw_material", "packaging", "consumables", "services", "other"] as const;
export const MATERIAL_CATEGORIES = ["resin", "masterbatch", "additive", "core", "carton", "film", "accessory", "other"] as const;
export type ReceiptStatus = "draft" | "received" | "cancelled";
export const RECEIPT_STATUSES: ReceiptStatus[] = ["draft", "received", "cancelled"];

export type HistoryEntry = { action: string; from_status: string | null; to_status: string | null; reason: string | null; actor_name: string | null; at: string };

export type SupplierInput = {
  name: string; category: string;  // MD-003: a key of the organization's supplier categories
  supplies: string | null; contact_name: string | null; phone: string | null;
  email: string | null; address: string | null; city: string | null; country: string | null; vat_number: string | null; cr_number: string | null;
  notes: string | null;
};
// The supplier's score over a period (PROC-002), from its incoming lots and the non-conformance reports about it.
export type Evaluation = {
  months: number; since: string; lots_inspected: number; lots_released: number; lots_rejected: number; acceptance_pct: string | null;
  ncr_count: number; ncr_penalty: number; ncr_cost: string; cost_penalty: number; score: string | null; grade: "A" | "B" | "C" | "D" | null;
  suggested_status: SupplierStatus | null;
};
// Where a received lot stands with quality.
export type LotStatus = "not_required" | "awaiting" | "inspecting" | "released" | "partly_released" | "rejected";
export type LotQuality = { status: LotStatus; inspection: { id: string; inspection_code: string; status: string; result: string | null;
  qty_inspected: string; qty_accepted: string; closed_at: string | null } | null };

export type Supplier = SupplierInput & {
  id: string; supplier_code: string; status: SupplierStatus; status_reason: string | null; status_changed_at: string | null;
  status_changed_by_name: string | null; receipts_count: number; last_receipt_date: string | null; ncr_count: number; open_ncr_count: number;
  actions: ("edit" | "set_status")[]; history: HistoryEntry[];
  non_conformances: { id: string; report_number: string; report_date: string; title: string; status: string; severity: string; reference_code: string | null }[];
  recent_receipts: { id: string; receipt_no: string; receipt_date: string; status: ReceiptStatus }[]; evaluation: Evaluation | null; created_at: string;
};
export type SupplierOption = { id: string; supplier_code: string; name: string; status: SupplierStatus };

export type MaterialInput = {
  name: string; category: string;  // MD-003: a key of the organization's material categories
  unit: string; inspection_required: boolean; spec_product_type: string | null;
  active: boolean; notes: string | null;
};
export type Material = MaterialInput & { id: string; material_code: string };

export type ReceiptLineInput = {
  material_id: string | null; description: string | null; supplier_lot: string | null; quantity: string; unit: string; package_count: number | null;
  weight: string | null; weight_unit: string; notes: string | null; po_line_id?: string | null;
};
export type ReceiptLine = ReceiptLineInput & { id: string; line_no: number; description: string; inspection_required: boolean };
export type ReceiptInput = {
  driver_id?: string|null; vehicle_id?: string|null; driver_affiliation?: string|null;
  supplier_id: string; receipt_date: string; supplier_delivery_no: string | null; supplier_invoice_no: string | null; purchase_reference: string | null;
  vehicle_plate: string | null; driver_name: string | null; notes: string | null; purchase_order_id?: string | null; lines: ReceiptLineInput[];
};
export type ReceiptListItem = {
  id: string; receipt_no: string; status: ReceiptStatus; receipt_date: string; supplier_id: string; supplier_name: string;
  supplier_status: SupplierStatus | null; supplier_delivery_no: string | null; supplier_invoice_no: string | null; purchase_reference: string | null;
  purchase_order_id: string | null; po_number: string | null;
  quantities: { unit: string; quantity: string }[]; weight_kg: string | null; inspection_lines: number; lots_pending: number;
  actions: ("edit" | "receive" | "cancel")[];
  created_at: string;
};
export type Receipt = ReceiptListItem & Omit<ReceiptInput, "lines" | "supplier_id" | "receipt_date" | "purchase_order_id"> & {
  received_at: string | null; received_by_name: string | null; created_by_name: string | null; cancel_reason: string | null;
  lines: ReceiptLine[]; line_quality: Record<string, LotQuality>; history: HistoryEntry[]; updated_at: string;
};

export type ProcurementSettings = { receipt_prefix: string; po_prefix: string; po_terms_ar: string | null; po_terms_en: string | null };

// Purchase orders (PROC-003): amounts are computed by the server; 15 % VAT for a local supplier, none for an import.
export type OrderStatus = "draft" | "approved" | "sent" | "partially_received" | "received" | "closed" | "cancelled";
export const ORDER_STATUSES: OrderStatus[] = ["draft", "approved", "sent", "partially_received", "received", "closed", "cancelled"];
export const CURRENCIES = ["SAR", "USD"] as const;
export type Currency = (typeof CURRENCIES)[number];
export const PAYMENT_TERMS = ["advance", "on_delivery", "net_15", "net_30", "net_45", "net_60", "net_90", "letter_of_credit", "other"] as const;
export const INCOTERMS = ["EXW", "FCA", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP"] as const;
export type OrderAction = "edit" | "approve" | "send" | "receive" | "close" | "cancel";

export type OrderLineInput = { material_id: string | null; description: string | null; notes: string | null; quantity: string; unit: string; unit_price: string };
export type OrderLine = OrderLineInput & { id: string; line_no: number; description: string; line_total: string };
export type OrderInput = {
  supplier_contact_id?: string|null;
  supplier_id: string; order_date: string; required_date: string | null; attention: string | null; supplier_quote_ref: string | null;
  subject: string | null; currency: Currency; tax_rate: number; discount_amount: string | null; payment_terms: (typeof PAYMENT_TERMS)[number] | null;
  payment_terms_note: string | null; incoterm: (typeof INCOTERMS)[number] | null; delivery_place: string | null; notes: string | null;
  lines: OrderLineInput[];
};
export type OrderListItem = {
  id: string; po_number: string; status: OrderStatus; order_date: string; required_date: string | null; supplier_id: string; supplier_name: string;
  supplier_status: SupplierStatus | null; supplier_quote_ref: string | null; subject: string | null; currency: Currency; tax_rate: string;
  total_amount: string; line_count: number; received_pct: string; actions: OrderAction[]; created_at: string;
};
export type Order = OrderListItem & Omit<OrderInput, "lines" | "tax_rate" | "discount_amount" | "supplier_id" | "currency"> & {
  subtotal_amount: string; discount_amount: string; tax_amount: string; approved_at: string | null; approved_by_name: string | null;
  approval?: { signer_name: string; authority_name: string; delegated: boolean } | null;
  sent_at: string | null; sent_by_name: string | null; closed_at: string | null; close_reason: string | null; cancel_reason: string | null;
  created_by_name: string | null; lines: OrderLine[]; line_received: Record<string, { received: string; remaining: string }>;
  receipts: { id: string; receipt_no: string; receipt_date: string; status: ReceiptStatus }[]; history: HistoryEntry[]; updated_at: string;
};
// An order goods may be received against, with what each line still expects.
export type OpenOrder = { id: string; po_number: string; order_date: string; status: OrderStatus;
  lines: { id: string; line_no: number; material_id: string | null; description: string; unit: string; quantity: string; remaining: string }[] };
