// Quality checks and rejections (QUAL-001). Quantities are decimal strings in the inspected line's unit.
export type QualityCheckType =
  | "in_process_inspection" | "finished_product_inspection" | "sample_inspection" | "reinspection" | "issue_triggered" | "general";
export type QualityCheckStatus = "open" | "under_inspection" | "closed" | "cancelled";
export type QualityCheckResult = "accepted" | "rejected" | "conditional_accept" | "needs_reinspection";
export type QualityCheckAction = "edit" | "measure" | "start" | "close" | "cancel";

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
  actions: QualityCheckAction[];
  created_at: string;
  updated_at: string;
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
