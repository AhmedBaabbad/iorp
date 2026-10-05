import type { CommercialOrderStatus } from "@/features/commercial-orders/types";
import type { DowntimeCategory, DowntimeStatus } from "@/features/downtime-events/types";
import type { ProductionOrderPriority, ProductionOrderStatus } from "@/features/production-orders/types";
import type { QualityCheckResult, QualityCheckStatus } from "@/features/quality-checks/types";
import type { DefectCategory, DefectSeverity } from "@/features/quality-defects/types";
import type { Disposition, DispositionStatus } from "@/features/quality-rejections/types";
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
  open: { background: "var(--surface-muted)", color: "var(--text-muted)" },
  under_inspection: { background: "var(--warning-soft)", color: "var(--warning)" },
  closed: { background: "var(--success-soft)", color: "var(--success)" },
  cancelled: { background: "var(--surface-muted)", color: "var(--text-muted)" },
};

export const qualityCheckResultColors: Record<QualityCheckResult | "pending", BadgeColor> = {
  accepted: { background: "var(--success-soft)", color: "var(--success)" },
  rejected: { background: "var(--danger-soft)", color: "var(--danger)" },
  conditional_accept: { background: "var(--warning-soft)", color: "var(--warning)" },
  needs_reinspection: { background: "var(--warning-soft)", color: "var(--warning)" },
  pending: { background: "var(--surface-muted)", color: "var(--text-muted)" },
};

export const defectSeverityColors: Record<DefectSeverity, BadgeColor> = {
  minor: { background: "var(--surface-muted)", color: "var(--text-muted)" },
  major: { background: "var(--warning-soft)", color: "var(--warning)" },
  critical: { background: "var(--danger-soft)", color: "var(--danger)" },
};

export const defectCategoryColors: Record<DefectCategory, BadgeColor> = {
  dimension: { background: "var(--accent-soft)", color: "var(--accent-strong)" },
  thickness: { background: "var(--accent-soft)", color: "var(--accent-strong)" },
  surface: { background: "var(--surface-muted)", color: "var(--text-muted)" },
  color: { background: "var(--accent-soft)", color: "var(--purple)" },
  strength: { background: "var(--warning-soft)", color: "var(--warning)" },
  winding: { background: "var(--warning-soft)", color: "var(--warning)" },
  weight: { background: "var(--warning-soft)", color: "var(--warning)" },
  packaging: { background: "var(--teal-soft)", color: "var(--teal)" },
  labeling: { background: "var(--teal-soft)", color: "var(--teal)" },
  finish: { background: "var(--surface-muted)", color: "var(--text-muted)" },
  other: { background: "var(--surface-muted)", color: "var(--text-muted)" },
};

export const qualityRejectionDispositionColors: Record<Disposition, BadgeColor> = {
  hold: { background: "var(--warning-soft)", color: "var(--warning)" },
  scrap: { background: "var(--danger-soft)", color: "var(--danger)" },
  rework: { background: "var(--accent-soft)", color: "var(--accent-strong)" },
  return_to_process: { background: "var(--surface-muted)", color: "var(--text-muted)" },
  use_as_is: { background: "var(--teal-soft)", color: "var(--teal)" },
};

export const qualityRejectionDispositionStatusColors: Record<DispositionStatus, BadgeColor> = {
  pending: { background: "var(--warning-soft)", color: "var(--warning)" },
  decided: { background: "var(--accent-soft)", color: "var(--accent-strong)" },
  executed: { background: "var(--success-soft)", color: "var(--success)" },
};

export const productionOrderStatusColors: Record<ProductionOrderStatus, BadgeColor> = {
  draft: { background: "var(--surface-muted)", color: "var(--text-muted)" },
  released: { background: "var(--accent-soft)", color: "var(--accent-strong)" },
  in_progress: { background: "var(--teal-soft)", color: "var(--teal)" },
  on_hold: { background: "var(--warning-soft)", color: "var(--warning)" },
  completed: { background: "var(--success-soft)", color: "var(--success)" },
  closed: { background: "var(--purple-soft)", color: "var(--purple)" },
  cancelled: { background: "var(--danger-soft)", color: "var(--danger)" },
};

export const productionOrderPriorityColors: Record<ProductionOrderPriority, BadgeColor> = {
  high: { background: "var(--warning-soft)", color: "var(--warning)" },
  urgent: { background: "var(--danger-soft)", color: "var(--danger)" },
  normal: { background: "var(--accent-soft)", color: "var(--accent-strong)" },
  low: { background: "var(--surface-muted)", color: "var(--text-muted)" },
};

export const workCenterStatusColors: Record<WorkCenterStatus, BadgeColor> = {
  active: { background: "var(--success-soft)", color: "var(--success)" },
  inactive: { background: "var(--surface-muted)", color: "var(--text-muted)" },
  under_maintenance: { background: "var(--warning-soft)", color: "var(--warning)" },
};

export const workCenterTypeColors: Record<WorkCenterType, BadgeColor> = {
  extrusion: { background: "var(--accent-soft)", color: "var(--accent-strong)" },
  rewinding: { background: "var(--accent-soft)", color: "var(--accent-strong)" },
  packing: { background: "var(--accent-soft)", color: "var(--accent-strong)" },
  quality_station: { background: "var(--accent-soft)", color: "var(--accent-strong)" },
  generic: { background: "var(--accent-soft)", color: "var(--accent-strong)" },
};

export const downtimeStatusColors: Record<DowntimeStatus, BadgeColor> = {
  open: { background: "var(--danger-soft)", color: "var(--danger)" },
  closed: { background: "var(--surface-muted)", color: "var(--text-muted)" },
};

export const downtimeCategoryColors: Record<DowntimeCategory, BadgeColor> = {
  breakdown: { background: "var(--danger-soft)", color: "var(--danger)" },
  changeover_setup: { background: "var(--warning-soft)", color: "var(--warning)" },
  material_shortage: { background: "var(--warning-soft)", color: "var(--warning)" },
  waiting_labor: { background: "var(--warning-soft)", color: "var(--warning)" },
  quality_issue: { background: "var(--purple-soft)", color: "var(--purple)" },
  utilities: { background: "var(--danger-soft)", color: "var(--danger)" },
  other: { background: "var(--surface-muted)", color: "var(--text-muted)" },
  planned_maintenance: { background: "var(--accent-soft)", color: "var(--accent-strong)" },
  break_meeting: { background: "var(--surface-muted)", color: "var(--text-muted)" },
  no_orders: { background: "var(--surface-muted)", color: "var(--text-muted)" },
};

export const shiftTypeColors: Record<ShiftType, BadgeColor> = {
  morning: { background: "var(--surface-muted)", color: "var(--text-muted)" },
  evening: { background: "var(--surface-muted)", color: "var(--text-muted)" },
  night: { background: "var(--surface-muted)", color: "var(--text-muted)" },
  custom: { background: "var(--surface-muted)", color: "var(--text-muted)" },
};

export const shiftStatusColors: Record<ShiftStatus, BadgeColor> = {
  active: { background: "var(--success-soft)", color: "var(--success)" },
  inactive: { background: "var(--surface-muted)", color: "var(--text-muted)" },
};

export const wasteCategoryColors: Record<WasteCategory, BadgeColor> = {
  startup_setup: { background: "var(--warning-soft)", color: "var(--warning)" },
  changeover: { background: "var(--warning-soft)", color: "var(--warning)" },
  process: { background: "var(--surface-muted)", color: "var(--text-muted)" },
  material_defect: { background: "var(--purple-soft)", color: "var(--purple)" },
  machine_fault: { background: "var(--danger-soft)", color: "var(--danger)" },
  handling_damage: { background: "var(--danger-soft)", color: "var(--danger)" },
  contamination: { background: "var(--purple-soft)", color: "var(--purple)" },
  other: { background: "var(--surface-muted)", color: "var(--text-muted)" },
};

export const customerStatusColors: Record<CustomerStatus, BadgeColor> = {
  active: { background: "var(--success-soft)", color: "var(--success)" },
  inactive: { background: "var(--surface-muted)", color: "var(--text-muted)" },
  on_hold: { background: "var(--warning-soft)", color: "var(--warning)" },
  archived: { background: "var(--surface-muted)", color: "var(--text-muted)" },
  blacklisted: { background: "var(--danger-soft)", color: "var(--danger)" },
};

export const customerRelationshipStageColors: Record<RelationshipStage, BadgeColor> = {
  lead: { background: "var(--surface-muted)", color: "var(--text-muted)" },
  contacted: { background: "var(--accent-soft)", color: "var(--accent-strong)" },
  qualified: { background: "var(--accent-soft)", color: "var(--accent-strong)" },
  prospect: { background: "var(--accent-soft)", color: "var(--accent-strong)" },
  negotiating: { background: "var(--warning-soft)", color: "var(--warning)" },
  trial_customer: { background: "var(--accent-soft)", color: "var(--purple)" },
  active_customer: { background: "var(--success-soft)", color: "var(--success)" },
  repeat_customer: { background: "var(--success-soft)", color: "var(--success)" },
  strategic_customer: { background: "var(--teal-soft)", color: "var(--teal)" },
};

export const customerPriorityLevelColors: Record<PriorityLevel, BadgeColor> = {
  low: { background: "var(--surface-muted)", color: "var(--text-muted)" },
  medium: { background: "var(--warning-soft)", color: "var(--warning)" },
  high: { background: "var(--danger-soft)", color: "var(--danger)" },
};

export const sampleStatusColors: Record<SampleStatus, BadgeColor> = {
  requested: { background: "var(--accent-soft)", color: "var(--accent-strong)" },
  in_preparation: { background: "var(--warning-soft)", color: "var(--warning)" },
  delivered: { background: "var(--success-soft)", color: "var(--success)" },
  evaluated: { background: "var(--accent-soft)", color: "var(--purple)" },
  cancelled: { background: "var(--surface-muted)", color: "var(--text-muted)" },
};

export const sampleEvaluationResultStatusColors: Record<
  SampleEvaluationResultStatus,
  BadgeColor
> = {
  accepted: { background: "var(--success-soft)", color: "var(--success)" },
  rejected: { background: "var(--danger-soft)", color: "var(--danger)" },
  needs_modification: { background: "var(--warning-soft)", color: "var(--warning)" },
};

export const quoteStatusColors: Record<QuoteStatus, BadgeColor> = {
  draft: { background: "var(--surface-muted)", color: "var(--text-muted)" },
  issued: { background: "var(--accent-soft)", color: "var(--accent-strong)" },
  accepted: { background: "var(--success-soft)", color: "var(--success)" },
  rejected: { background: "var(--danger-soft)", color: "var(--danger)" },
  expired: { background: "var(--warning-soft)", color: "var(--warning)" },
};

export const commercialOrderStatusColors: Record<CommercialOrderStatus, BadgeColor> = {
  draft: { background: "var(--surface-muted)", color: "var(--text-muted)" },
  confirmed: { background: "var(--accent-soft)", color: "var(--accent-strong)" },
  converted_to_production: { background: "var(--accent-soft)", color: "var(--purple)" },
  cancelled: { background: "var(--danger-soft)", color: "var(--danger)" },
};

export const commercialFollowUpStatusColors: Record<FollowUpStatus, BadgeColor> = {
  pending: { background: "var(--warning-soft)", color: "var(--warning)" },
  in_progress: { background: "var(--accent-soft)", color: "var(--accent-strong)" },
  completed: { background: "var(--success-soft)", color: "var(--success)" },
  cancelled: { background: "var(--surface-muted)", color: "var(--text-muted)" },
};

export const commercialFollowUpPriorityColors: Record<FollowUpPriority, BadgeColor> = {
  low: { background: "var(--surface-muted)", color: "var(--text-muted)" },
  medium: { background: "var(--accent-soft)", color: "var(--accent-strong)" },
  high: { background: "var(--warning-soft)", color: "var(--warning)" },
  urgent: { background: "var(--danger-soft)", color: "var(--danger)" },
};
