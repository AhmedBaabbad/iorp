// Procurement (PROC-001): suppliers, materials and goods receipts. Quantities and weights are decimal strings.
export type SupplierStatus = "pending" | "approved" | "conditional" | "blocked";
export const SUPPLIER_STATUSES: SupplierStatus[] = ["pending", "approved", "conditional", "blocked"];
export const SUPPLIER_CATEGORIES = ["raw_material", "packaging", "consumables", "services", "other"] as const;
export const MATERIAL_CATEGORIES = ["resin", "masterbatch", "additive", "core", "carton", "film", "accessory", "other"] as const;
export type ReceiptStatus = "draft" | "received" | "cancelled";
export const RECEIPT_STATUSES: ReceiptStatus[] = ["draft", "received", "cancelled"];

export type HistoryEntry = { action: string; from_status: string | null; to_status: string | null; reason: string | null; actor_name: string | null; at: string };

export type SupplierInput = {
  name: string; category: (typeof SUPPLIER_CATEGORIES)[number]; supplies: string | null; contact_name: string | null; phone: string | null;
  email: string | null; address: string | null; city: string | null; country: string | null; vat_number: string | null; cr_number: string | null;
  notes: string | null;
};
export type Supplier = SupplierInput & {
  id: string; supplier_code: string; status: SupplierStatus; status_reason: string | null; status_changed_at: string | null;
  status_changed_by_name: string | null; receipts_count: number; last_receipt_date: string | null; ncr_count: number; open_ncr_count: number;
  actions: ("edit" | "set_status")[]; history: HistoryEntry[];
  non_conformances: { id: string; report_number: string; report_date: string; title: string; status: string; severity: string; reference_code: string | null }[];
  recent_receipts: { id: string; receipt_no: string; receipt_date: string; status: ReceiptStatus }[]; created_at: string;
};
export type SupplierOption = { id: string; supplier_code: string; name: string; status: SupplierStatus };

export type MaterialInput = {
  name: string; category: (typeof MATERIAL_CATEGORIES)[number]; unit: string; inspection_required: boolean; spec_product_type: string | null;
  active: boolean; notes: string | null;
};
export type Material = MaterialInput & { id: string; material_code: string };

export type ReceiptLineInput = {
  material_id: string | null; description: string | null; supplier_lot: string | null; quantity: string; unit: string; package_count: number | null;
  weight: string | null; weight_unit: string; notes: string | null;
};
export type ReceiptLine = ReceiptLineInput & { id: string; line_no: number; description: string; inspection_required: boolean };
export type ReceiptInput = {
  supplier_id: string; receipt_date: string; supplier_delivery_no: string | null; supplier_invoice_no: string | null; purchase_reference: string | null;
  vehicle_plate: string | null; driver_name: string | null; notes: string | null; lines: ReceiptLineInput[];
};
export type ReceiptListItem = {
  id: string; receipt_no: string; status: ReceiptStatus; receipt_date: string; supplier_id: string; supplier_name: string;
  supplier_status: SupplierStatus | null; supplier_delivery_no: string | null; supplier_invoice_no: string | null; purchase_reference: string | null;
  quantities: { unit: string; quantity: string }[]; weight_kg: string | null; inspection_lines: number; actions: ("edit" | "receive" | "cancel")[];
  created_at: string;
};
export type Receipt = ReceiptListItem & Omit<ReceiptInput, "lines" | "supplier_id" | "receipt_date"> & {
  received_at: string | null; received_by_name: string | null; created_by_name: string | null; cancel_reason: string | null;
  lines: ReceiptLine[]; history: HistoryEntry[]; updated_at: string;
};
