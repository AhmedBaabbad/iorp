export type RejectionReason =
  | "failed_quality_check"
  | "critical_defect"
  | "out_of_spec"
  | "dimension_failure"
  | "surface_failure"
  | "packaging_failure"
  | "labeling_issue"
  | "other";

export type Disposition =
  | "hold"
  | "scrap"
  | "rework"
  | "return_to_process";

export type DispositionStatus = "pending" | "executed";

export type QualityRejectionListFilters = {
  rejection_reason?: RejectionReason;
  disposition?: Disposition;
  disposition_status?: DispositionStatus;
  quality_check_id?: string;
  rejection_date?: string;
};

export type QualityRejectionListItem = {
  id: string;
  organization_id: string;
  quality_check_id: string | null;
  quality_defect_id: string | null;
  production_output_id: string | null;
  production_order_item_id: string | null;
  rejection_date: string;
  rejection_reason: RejectionReason;
  disposition: Disposition;
  disposition_status: DispositionStatus;
  quantity_rejected: number;
  unit: string;
  created_at: string;
  updated_at: string;
};

export type QualityRejectionData = QualityRejectionListItem & {
  rejection_notes: string;
  rejected_by_user_id: string;
};

export type CreateQualityRejectionRequest = {
  quality_check_id?: string | null;
  quality_defect_id?: string | null;
  production_output_id?: string | null;
  production_order_item_id?: string | null;
  rejection_date: string;
  rejection_reason: RejectionReason;
  rejection_notes: string;
  disposition: Disposition;
  quantity_rejected: number;
  unit: string;
  notes?: string | null;
};

export type UpdateDispositionStatusRequest = {
  disposition_status: DispositionStatus;
};
