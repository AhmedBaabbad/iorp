export type QualityCheckType =
  | "in_process_inspection"
  | "finished_product_inspection"
  | "sample_inspection"
  | "reinspection"
  | "issue_triggered"
  | "general";

export type QualityCheckStatus = "open" | "under_inspection" | "closed";

export type QualityCheckResult =
  | "accepted"
  | "rejected"
  | "conditional_accept"
  | "needs_reinspection";

export type QualityCheckListFilters = {
  check_type?: QualityCheckType;
  status?: QualityCheckStatus;
  result?: QualityCheckResult;
  production_order_id?: string;
  shift_report_id?: string;
};

export type QualityCheckListItem = {
  id: string;
  organization_id: string;
  inspection_code: string;
  check_datetime: string;
  check_type: QualityCheckType;
  status: QualityCheckStatus;
  result: QualityCheckResult | null;
  qty_inspected: number;
  qty_accepted: number;
  qty_rejected: number;
  production_order_id: string | null;
  production_output_id: string | null;
  shift_report_id: string | null;
  created_at: string;
  updated_at: string;
};

export type QualityCheckData = QualityCheckListItem & {
  production_order_item_id: string | null;
  notes: string | null;
  checked_by_user_id: string;
};

export type CreateQualityCheckRequest = {
  production_order_id?: string | null;
  production_order_item_id?: string | null;
  production_output_id?: string | null;
  shift_report_id?: string | null;
  check_datetime: string;
  check_type: QualityCheckType;
  qty_inspected: number;
  qty_accepted: number;
  qty_rejected: number;
  notes?: string | null;
};

export type UpdateQualityCheckStatusRequest = {
  status: QualityCheckStatus;
  result?: QualityCheckResult | null;
};
