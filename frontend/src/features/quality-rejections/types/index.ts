// Quality rejections (QUAL-001): pending → decided (disposition) → executed.
import type { DefectCategory, DefectSeverity } from "@/features/quality-defects/types";
import type { HistoryEntry } from "@/features/quality-checks/types";

export type RejectionReason =
  | "failed_quality_check" | "critical_defect" | "out_of_spec" | "dimension_failure" | "surface_failure" | "packaging_failure" | "labeling_issue" | "other";
export type Disposition = "hold" | "scrap" | "rework" | "return_to_process" | "use_as_is";
export type DispositionStatus = "pending" | "decided" | "executed";
export type RejectionAction = "edit" | "decide" | "execute";

export const REJECTION_REASONS: RejectionReason[] = ["failed_quality_check", "critical_defect", "out_of_spec", "dimension_failure", "surface_failure", "packaging_failure", "labeling_issue", "other"];
export const DISPOSITIONS: Disposition[] = ["hold", "scrap", "rework", "return_to_process", "use_as_is"];
export const DISPOSITION_STATUSES: DispositionStatus[] = ["pending", "decided", "executed"];

export type QualityRejectionListItem = {
  id: string;
  rejection_code: string;
  quality_check_id: string | null;
  production_order_id: string | null;
  production_order_item_id: string | null;
  rejection_date: string;
  rejection_reason: RejectionReason;
  disposition: Disposition | null;
  disposition_status: DispositionStatus;
  quantity_rejected: string;
  unit: string;
  order_number: string | null;
  item_line_no: number | null;
  inspection_code: string | null;
  // Pending, or decided as a hold: blocks closing the production order.
  unresolved: boolean;
  actions: RejectionAction[];
  // The highest severity among the rejection's defects (critical > major > minor); null without defects.
  severity?: DefectSeverity | null;
  // affected_quantity is per defect: defects overlap, so these are never added up.
  defects?: { quality_defect_id: string; defect_category: DefectCategory; severity: DefectSeverity; defect_count: number; description: string;
    affected_quantity: string | null }[];
  created_at: string;
};

export type QualityRejectionData = QualityRejectionListItem & {
  rejection_notes: string;
  rejected_by_name: string | null;
  decision_notes: string | null;
  concession_approved_by: string | null;
  decided_at: string | null;
  decided_by_name: string | null;
  execution_notes: string | null;
  executed_at: string | null;
  executed_by_name: string | null;
  history: HistoryEntry[];
  updated_at: string;
};

export type QualityRejectionListFilters = {
  production_order_id?: string;
  quality_check_id?: string;
  rejection_reason?: RejectionReason | "";
  disposition?: Disposition | "";
  disposition_status?: DispositionStatus | "";
  date_from?: string;
  date_to?: string;
  search?: string;
};

export type CreateQualityRejectionRequest = {
  quality_check_id?: string | null;
  production_order_id?: string | null;
  production_order_item_id?: string | null;
  rejection_date: string;
  rejection_reason: RejectionReason;
  rejection_notes: string;
  quantity_rejected: string;
  defects?: RejectionDefectInput[];
};

export type RejectionDefectInput = { quality_defect_id: string; affected_quantity?: string | null };

export type UpdateQualityRejectionRequest = Partial<Pick<CreateQualityRejectionRequest, "rejection_date" | "rejection_reason" | "rejection_notes" | "quantity_rejected" | "defects">>;

export type RejectionDecisionRequest = { disposition: Disposition; decision_notes?: string | null; concession_approved_by?: string | null };
