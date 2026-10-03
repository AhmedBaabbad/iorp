// Final order result (PROD-OUTPUT-001). Quantities are decimal strings, as the API sends them.
export type Disposition = "customer_good" | "stock_good" | "sample" | "scrap" | "rework";
export type EntryAction = "edit" | "delete" | "correct";

export type ResultSummary = {
  customer_good: string; stock_good: string; good_total: string;
  samples_total: string; samples_loss: string; scrap_total: string; loss_total: string; rework_total: string; total_output: string;
  planned_qty: string; allocated_qty: string | null;
  fulfillment_pct: string | null; yield_pct: string | null; loss_pct: string | null; variance_qty: string;
  secondary_totals: { unit: string; quantity: string }[];
};

export type ResultEntry = {
  id: string; production_order_item_id: string | null; line_no: number | null; disposition: Disposition;
  quantity: string; unit: string; secondary_quantity: string | null; secondary_unit: string | null; counts_as_loss: boolean;
  reason_code: string | null; notes: string | null; entry_type: "original" | "correction";
  corrects_entry_id: string | null; correction_reason: string | null;
  created_by_user_id: string; created_by_name: string | null; updated_by_user_id: string | null; created_at: string; updated_at: string;
};

export type ResultOriginal = ResultEntry & { effective_quantity: string; corrections: ResultEntry[]; actions: EntryAction[] };

export type ResultItem = {
  id: string; line_no: number; unit: string; planned_quantity: string; target_spec_json: Record<string, unknown> | null;
  allocated_quantity: string | null; summary: ResultSummary;
};

export type OrderResult = {
  order: { id: string; number: string; status: string; product_type: string; unit: string };
  available: boolean; editable: boolean; locked: boolean;
  // Where customer allocations sit: per item, per order (by unit), or none at all.
  allocation_level: "item" | "order" | "none";
  items: ResultItem[];
  // Whole-order totals, one per unit: different units are never added together.
  totals: (ResultSummary & { unit: string })[];
  entries: ResultOriginal[];
  close_check: { ready: boolean; has_entries: boolean; missing_item_ids: string[] };
  actions: "create"[];
};

export type ResultEntryInput = {
  production_order_item_id?: string | null;
  disposition: Disposition;
  quantity: string;
  secondary_quantity?: string | null;
  secondary_unit?: string | null;
  counts_as_loss?: boolean | null;
  reason_code?: string | null;
  notes?: string | null;
};

export type ResultCorrectionInput = { quantity: string; secondary_quantity?: string | null; correction_reason: string };

export type ResultOverviewRow = {
  id: string; number: string; status: "completed" | "closed"; product_type: string;
  entry_count: number; correction_count: number; ready_to_close: boolean;
  totals: (ResultSummary & { unit: string })[];
};
