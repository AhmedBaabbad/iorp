// Quality checks and rejections (QUAL-001). Quantities are decimal strings in the inspected line's unit.
export type QualityCheckType =
  | "in_process_inspection" | "finished_product_inspection" | "sample_inspection" | "reinspection" | "issue_triggered" | "general";
export type QualityCheckStatus = "open" | "under_inspection" | "closed" | "cancelled";
export type QualityCheckResult = "accepted" | "rejected" | "conditional_accept" | "needs_reinspection";
// "return_decision" replaces "close" on an inspection of returned goods (QUAL-RET-001).
export type QualityCheckAction = "edit" | "measure" | "start" | "close" | "return_decision" | "cancel";

export const CHECK_TYPES: QualityCheckType[] = ["in_process_inspection", "finished_product_inspection", "reinspection", "sample_inspection", "issue_triggered", "general"];
export const CHECK_STATUSES: QualityCheckStatus[] = ["open", "under_inspection", "closed", "cancelled"];
export const CHECK_RESULTS: QualityCheckResult[] = ["accepted", "rejected", "conditional_accept", "needs_reinspection"];
// A production lot is inspected against its order; a sample inspection against a commercial sample.
export const ORDER_CHECK_TYPES: QualityCheckType[] = ["in_process_inspection", "finished_product_inspection", "reinspection"];

export type HistoryEntry = { action: string; from_status: string | null; to_status: string; reason: string | null;
  detail: Record<string, string | null> | null; actor_name: string | null; at: string };

export type QualityCheckListItem = {
  id: string;
  inspection_code: string;
  check_type: QualityCheckType;
  status: QualityCheckStatus;
  result: QualityCheckResult | null;
  check_datetime: string;
  production_order_id: string | null;
  production_order_item_id: string | null;
  sample_id: string | null;
  qty_inspected: string;
  qty_accepted: string;
  qty_rejected: string;
  unit: string | null;
  order_number: string | null;
  item_line_no: number | null;
  sample_code: string | null;
  checked_by_name: string | null;
  return_id?: string | null;
  return_line_id?: string | null;
  return_source?: ReturnSource | null;
  actions: QualityCheckAction[];
  created_at: string;
  updated_at: string;
};

// The returned goods an inspection is about (read from shipping).
export type ReturnSource = {
  return_id: string; return_no: string; kind: string; reason: string; responsibility: string; details: string | null;
  shipment_id: string; shipment_no: string; customer_name: string; line_no: number; description: string; production_order_no: string | null;
};

// Returned goods received for quality, each line with its inspection once opened.
export type AwaitingReturnLine = {
  line_id: string; line_no: number; description: string; width_mm: string | null; thickness_mm: string | null; unit: string;
  production_order_id: string | null; production_order_no: string | null; received_quantity: string | null;
  inspection_id: string | null; inspection_code: string | null; inspection_status: QualityCheckStatus | null;
};
export type AwaitingReturn = {
  return_id: string; return_no: string; kind: string; reason: string; responsibility: string; details: string | null; customer_name: string;
  received_at: string | null; shipment_id: string; shipment_no: string; lines: AwaitingReturnLine[];
};

// Where the inspected quantity of returned goods goes; the parts add up to it.
export const RETURN_PARTS = ["to_stock", "use_as_is", "rework", "return_to_process", "scrap", "hold"] as const;
export type ReturnPart = (typeof RETURN_PARTS)[number];
export type ReturnDecisionRequest = Record<ReturnPart, string> & { notes: string | null; concession_approved_by: string | null; open_ncr: boolean };

// A delivery note that carried the same production order (containment).
export type BatchShipment = {
  shipment_id: string; shipment_no: string; status: string; shipment_date: string; customer_name: string;
  quantity: string; delivered_quantity: string | null; unit: string;
};

export type CheckRejectionSummary = { id: string; rejection_code: string; disposition_status: string; disposition: string | null;
  quantity_rejected: string; unit: string };

// A plan line of the inspection (QUAL-SPEC-001): limits resolved for the lot, readings and the verdict.
export type MeasurementStatus = "pending" | "pass" | "fail" | "recorded";
export type Measurement = {
  id: string; position: number; parameter_code: string; name_ar: string; name_en: string; kind: "numeric" | "attribute";
  unit: string | null; method: string | null; requirement: string | null; acceptance: string | null;
  target: string | null; lower_limit: string | null; upper_limit: string | null; readings_required: number;
  readings: string[] | null; attribute_result: "conforming" | "nonconforming" | null; observation: string | null;
  reading_count: number; minimum: string | null; maximum: string | null; mean: string | null; status: MeasurementStatus; measured_at: string | null;
};
export type PlanCandidate = {
  id: string; code: string; revision: number; title: string; product_type: string; grade: string | null;
  matches_product: boolean; missing_keys: string[];
};
export type MeasurementInput = { readings?: string[]; attribute_result?: "conforming" | "nonconforming" | null; observation?: string | null };

export type QualityCheckData = QualityCheckListItem & {
  specification_id: string | null;
  specification_code: string | null;
  specification_revision: number | null;
  lot_values: Record<string, string> | null;
  measurements: Measurement[];
  notes: string | null;
  started_at: string | null;
  closed_at: string | null;
  closed_by_name: string | null;
  cancel_reason: string | null;
  history: HistoryEntry[];
  rejections: CheckRejectionSummary[];
};

export type QualityCheckListFilters = {
  production_order_id?: string;
  check_type?: QualityCheckType | "";
  status?: QualityCheckStatus | "";
  result?: QualityCheckResult | "";
  date_from?: string;
  date_to?: string;
  search?: string;
};

export type CreateQualityCheckRequest = {
  check_type: QualityCheckType;
  check_datetime: string;
  production_order_id?: string | null;
  production_order_item_id?: string | null;
  sample_id?: string | null;
  qty_inspected?: string;
  notes?: string | null;
};

export type UpdateQualityCheckRequest = Partial<Pick<CreateQualityCheckRequest, "check_type" | "check_datetime" | "production_order_item_id" | "sample_id" | "qty_inspected" | "notes">>;

export type CloseQualityCheckRequest = {
  result: QualityCheckResult;
  qty_inspected: string;
  qty_accepted: string;
  qty_rejected: string;
  notes?: string | null;
  rejection_reason?: string | null;
};

export type OrderLine = { id: string; line_no: number; unit: string; planned_quantity: string; spec: Record<string, unknown> | null };
export type InspectableOrder = { id: string; number: string; product_type: string; status: string; unit: string; items: OrderLine[] };
export type SampleOption = { id: string; code: string; product_type: string; unit: string | null; customer: string };
