import type { ActionFollowUpStatus } from "@/features/action-follow-ups/types";
import type { ClosureStatus, ClosureVerificationResult } from "@/features/closure-verifications/types";
import type { CommercialOrderStatus } from "@/features/commercial-orders/types";
import type {
  CorrectiveActionPriority,
  CorrectiveActionStatus,
  CorrectiveActionType,
} from "@/features/corrective-actions/types";
import type { DowntimeCategory, DowntimeStatus } from "@/features/downtime-events/types";
import type { NCRSourceType, NCRStatus } from "@/features/ncr-reports/types";
import type { ProductionOrderPriority, ProductionOrderStatus } from "@/features/production-orders/types";
import type { ProductionOutputStatus } from "@/features/production-outputs/types";
import type { QualityCheckResult, QualityCheckStatus } from "@/features/quality-checks/types";
import type { DefectCategory, DefectSeverity } from "@/features/quality-defects/types";
import type { Disposition, DispositionStatus } from "@/features/quality-rejections/types";
import type { ShiftReportStatus } from "@/features/shift-reports/types";
import type { ShiftStatus, ShiftType } from "@/features/shifts/types";
import type { WasteCategory } from "@/features/waste-records/types";
import type { WorkCenterStatus, WorkCenterType } from "@/features/work-centers/types";
import type { QuoteStatus } from "@/features/quotes/types";
import type { SampleEvaluationResultStatus } from "@/features/sample-evaluations/types";
import type { SampleStatus } from "@/features/samples/types";
import type { CustomerStatus, PriorityLevel, RelationshipStage } from "@/types/customers";
import type { FollowUpPriority, FollowUpStatus } from "@/types/followups";

export type BadgeColor = { background: string; color: string };

export const qualityCheckStatusColors: Record<QualityCheckStatus, BadgeColor> = {
  open: { background: "#f3f4f6", color: "#4b5563" },
  under_inspection: { background: "#fef3c7", color: "#92400e" },
  closed: { background: "#dcfce7", color: "#166534" },
};

export const qualityCheckResultColors: Record<QualityCheckResult | "pending", BadgeColor> = {
  accepted: { background: "#dcfce7", color: "#166534" },
  rejected: { background: "#fee2e2", color: "#991b1b" },
  conditional_accept: { background: "#fef3c7", color: "#92400e" },
  needs_reinspection: { background: "#ffedd5", color: "#9a3412" },
  pending: { background: "#f3f4f6", color: "#4b5563" },
};

export const defectSeverityColors: Record<DefectSeverity, BadgeColor> = {
  minor: { background: "#f3f4f6", color: "#4b5563" },
  major: { background: "#ffedd5", color: "#9a3412" },
  critical: { background: "#fee2e2", color: "#991b1b" },
};

export const defectCategoryColors: Record<DefectCategory, BadgeColor> = {
  dimension: { background: "#dbeafe", color: "#1e40af" },
  thickness: { background: "#dbeafe", color: "#1e40af" },
  surface: { background: "#f3f4f6", color: "#4b5563" },
  color: { background: "#ede9fe", color: "#5b21b6" },
  strength: { background: "#ffedd5", color: "#9a3412" },
  winding: { background: "#ffedd5", color: "#9a3412" },
  weight: { background: "#fef9c3", color: "#854d0e" },
  packaging: { background: "#ccfbf1", color: "#0f766e" },
  labeling: { background: "#ccfbf1", color: "#0f766e" },
  finish: { background: "#f3f4f6", color: "#4b5563" },
  other: { background: "#f3f4f6", color: "#4b5563" },
};

export const qualityRejectionDispositionColors: Record<Disposition, BadgeColor> = {
  hold: { background: "#fef3c7", color: "#92400e" },
  scrap: { background: "#fee2e2", color: "#991b1b" },
  rework: { background: "#dbeafe", color: "#1e40af" },
  return_to_process: { background: "#f3f4f6", color: "#4b5563" },
};

export const qualityRejectionDispositionStatusColors: Record<DispositionStatus, BadgeColor> = {
  pending: { background: "#ffedd5", color: "#9a3412" },
  executed: { background: "#dcfce7", color: "#166534" },
};

export const ncrStatusColors: Record<NCRStatus, BadgeColor> = {
  draft: { background: "#f3f4f6", color: "#4b5563" },
  open: { background: "#dbeafe", color: "#1e40af" },
  under_review: { background: "#fef3c7", color: "#92400e" },
  closed: { background: "#dcfce7", color: "#166534" },
};

export const ncrSourceTypeColors: Record<NCRSourceType, BadgeColor> = {
  internal_production: { background: "#dbeafe", color: "#1e40af" },
  incoming_material: { background: "#ede9fe", color: "#5b21b6" },
  supplier: { background: "#fef3c7", color: "#92400e" },
  warehouse: { background: "#ccfbf1", color: "#0f766e" },
  customer_return: { background: "#fee2e2", color: "#991b1b" },
  other: { background: "#f3f4f6", color: "#4b5563" },
};

export const correctiveActionStatusColors: Record<CorrectiveActionStatus, BadgeColor> = {
  open: { background: "#f3f4f6", color: "#4b5563" },
  in_progress: { background: "#dbeafe", color: "#1e40af" },
  completed: { background: "#dcfce7", color: "#166534" },
  closed: { background: "#dcfce7", color: "#166534" },
};

export const correctiveActionPriorityColors: Record<CorrectiveActionPriority, BadgeColor> = {
  urgent: { background: "#fee2e2", color: "#991b1b" },
  high: { background: "#ffedd5", color: "#9a3412" },
  normal: { background: "#dbeafe", color: "#1e40af" },
  low: { background: "#f3f4f6", color: "#4b5563" },
};

export const correctiveActionTypeColors: Record<CorrectiveActionType, BadgeColor> = {
  corrective: { background: "#fee2e2", color: "#991b1b" },
  preventive: { background: "#dbeafe", color: "#1e40af" },
  improvement: { background: "#ccfbf1", color: "#115e59" },
  containment: { background: "#ffedd5", color: "#9a3412" },
};

export const followUpStatusColors: Record<ActionFollowUpStatus, BadgeColor> = {
  on_track: { background: "#dcfce7", color: "#166534" },
  delayed: { background: "#ffedd5", color: "#9a3412" },
  blocked: { background: "#fee2e2", color: "#991b1b" },
  completed: { background: "#dcfce7", color: "#166534" },
};

export const closureResultColors: Record<ClosureVerificationResult, BadgeColor> = {
  effective: { background: "#dcfce7", color: "#166534" },
  partially_effective: { background: "#fef3c7", color: "#92400e" },
  not_effective: { background: "#fee2e2", color: "#991b1b" },
};

export const closureStatusColors: Record<ClosureStatus, BadgeColor> = {
  closed: { background: "#dcfce7", color: "#166534" },
  re_opened: { background: "#ffedd5", color: "#9a3412" },
};

export const productionOrderStatusColors: Record<ProductionOrderStatus, BadgeColor> = {
  draft: { background: "#f3f4f6", color: "#4b5563" },
  released: { background: "#dbeafe", color: "#1e40af" },
  in_progress: { background: "#fef3c7", color: "#92400e" },
  completed: { background: "#dcfce7", color: "#166534" },
  cancelled: { background: "#fee2e2", color: "#991b1b" },
};

export const productionOrderPriorityColors: Record<ProductionOrderPriority, BadgeColor> = {
  high: { background: "#fff7ed", color: "#9a3412" },
  urgent: { background: "#fee2e2", color: "#991b1b" },
  normal: { background: "#dbeafe", color: "#1e40af" },
  low: { background: "#f3f4f6", color: "#4b5563" },
};

export const workCenterStatusColors: Record<WorkCenterStatus, BadgeColor> = {
  active: { background: "#dcfce7", color: "#166534" },
  inactive: { background: "#f3f4f6", color: "#4b5563" },
  under_maintenance: { background: "#fef3c7", color: "#92400e" },
};

export const workCenterTypeColors: Record<WorkCenterType, BadgeColor> = {
  extrusion: { background: "#eef2ff", color: "#3730a3" },
  rewinding: { background: "#eef2ff", color: "#3730a3" },
  packing: { background: "#eef2ff", color: "#3730a3" },
  quality_station: { background: "#eef2ff", color: "#3730a3" },
  generic: { background: "#eef2ff", color: "#3730a3" },
};

export const downtimeStatusColors: Record<DowntimeStatus, BadgeColor> = {
  open: { background: "#fee2e2", color: "#991b1b" },
  closed: { background: "#f3f4f6", color: "#4b5563" },
};

export const downtimeCategoryColors: Record<DowntimeCategory, BadgeColor> = {
  machine: { background: "#fee2e2", color: "#991b1b" },
  material: { background: "#ffedd5", color: "#9a3412" },
  manpower: { background: "#fef9c3", color: "#854d0e" },
  quality: { background: "#f3e8ff", color: "#6b21a8" },
  utilities: { background: "#dbeafe", color: "#1e40af" },
  setup: { background: "#ccfbf1", color: "#0f766e" },
  other: { background: "#f3f4f6", color: "#4b5563" },
};

export const shiftReportStatusColors: Record<ShiftReportStatus, BadgeColor> = {
  draft: { background: "#f3f4f6", color: "#4b5563" },
  submitted: { background: "#dbeafe", color: "#1e40af" },
  approved: { background: "#dcfce7", color: "#166534" },
};

export const shiftTypeColors: Record<ShiftType, BadgeColor> = {
  morning: { background: "#f3f4f6", color: "#4b5563" },
  evening: { background: "#f3f4f6", color: "#4b5563" },
  night: { background: "#f3f4f6", color: "#4b5563" },
  custom: { background: "#f3f4f6", color: "#4b5563" },
};

export const shiftStatusColors: Record<ShiftStatus, BadgeColor> = {
  active: { background: "#dcfce7", color: "#166534" },
  inactive: { background: "#f3f4f6", color: "#4b5563" },
};

export const productionOutputStatusColors: Record<ProductionOutputStatus, BadgeColor> = {
  recorded: { background: "#f3f4f6", color: "#4b5563" },
  verified: { background: "#dbeafe", color: "#1e40af" },
  posted: { background: "#dcfce7", color: "#166534" },
};

export const wasteCategoryColors: Record<WasteCategory, BadgeColor> = {
  startup_loss: { background: "#ffedd5", color: "#9a3412" },
  trim_loss: { background: "#fef9c3", color: "#854d0e" },
  setup_loss: { background: "#fef9c3", color: "#854d0e" },
  rejected_output: { background: "#fee2e2", color: "#991b1b" },
  breakage: { background: "#fee2e2", color: "#991b1b" },
  rewinding_loss: { background: "#ffedd5", color: "#9a3412" },
  end_of_roll_loss: { background: "#f3f4f6", color: "#4b5563" },
  material_loss: { background: "#e7e5e4", color: "#44403c" },
  contamination_loss: { background: "#f3e8ff", color: "#6b21a8" },
  other: { background: "#f3f4f6", color: "#4b5563" },
};

export const customerStatusColors: Record<CustomerStatus, BadgeColor> = {
  active: { background: "#dcfce7", color: "#166534" },
  inactive: { background: "#f3f4f6", color: "#4b5563" },
  on_hold: { background: "#fef3c7", color: "#92400e" },
  archived: { background: "#f3f4f6", color: "#4b5563" },
  blacklisted: { background: "#fee2e2", color: "#991b1b" },
};

export const customerRelationshipStageColors: Record<RelationshipStage, BadgeColor> = {
  lead: { background: "#f3f4f6", color: "#4b5563" },
  contacted: { background: "#dbeafe", color: "#1e40af" },
  qualified: { background: "#dbeafe", color: "#1e40af" },
  prospect: { background: "#dbeafe", color: "#1e40af" },
  negotiating: { background: "#fef3c7", color: "#92400e" },
  trial_customer: { background: "#ede9fe", color: "#5b21b6" },
  active_customer: { background: "#dcfce7", color: "#166534" },
  repeat_customer: { background: "#dcfce7", color: "#166534" },
  strategic_customer: { background: "#ccfbf1", color: "#0f766e" },
};

export const customerPriorityLevelColors: Record<PriorityLevel, BadgeColor> = {
  low: { background: "#f3f4f6", color: "#4b5563" },
  medium: { background: "#fef3c7", color: "#92400e" },
  high: { background: "#fee2e2", color: "#991b1b" },
};

export const sampleStatusColors: Record<SampleStatus, BadgeColor> = {
  requested: { background: "#dbeafe", color: "#1e40af" },
  in_preparation: { background: "#fef3c7", color: "#92400e" },
  delivered: { background: "#dcfce7", color: "#166534" },
  evaluated: { background: "#ede9fe", color: "#5b21b6" },
  cancelled: { background: "#f3f4f6", color: "#4b5563" },
};

export const sampleEvaluationResultStatusColors: Record<
  SampleEvaluationResultStatus,
  BadgeColor
> = {
  accepted: { background: "#dcfce7", color: "#166534" },
  rejected: { background: "#fee2e2", color: "#991b1b" },
  needs_modification: { background: "#fef3c7", color: "#92400e" },
};

export const quoteStatusColors: Record<QuoteStatus, BadgeColor> = {
  draft: { background: "#f3f4f6", color: "#4b5563" },
  issued: { background: "#dbeafe", color: "#1e40af" },
  accepted: { background: "#dcfce7", color: "#166534" },
  rejected: { background: "#fee2e2", color: "#991b1b" },
  expired: { background: "#fef3c7", color: "#92400e" },
};

export const commercialOrderStatusColors: Record<CommercialOrderStatus, BadgeColor> = {
  draft: { background: "#f3f4f6", color: "#4b5563" },
  confirmed: { background: "#dbeafe", color: "#1e40af" },
  converted_to_production: { background: "#ede9fe", color: "#5b21b6" },
  cancelled: { background: "#fee2e2", color: "#991b1b" },
};

export const commercialFollowUpStatusColors: Record<FollowUpStatus, BadgeColor> = {
  pending: { background: "#fef3c7", color: "#92400e" },
  in_progress: { background: "#dbeafe", color: "#1e40af" },
  completed: { background: "#dcfce7", color: "#166534" },
  cancelled: { background: "#f3f4f6", color: "#4b5563" },
};

export const commercialFollowUpPriorityColors: Record<FollowUpPriority, BadgeColor> = {
  low: { background: "#f3f4f6", color: "#4b5563" },
  medium: { background: "#dbeafe", color: "#1e40af" },
  high: { background: "#ffedd5", color: "#9a3412" },
  urgent: { background: "#fee2e2", color: "#991b1b" },
};
