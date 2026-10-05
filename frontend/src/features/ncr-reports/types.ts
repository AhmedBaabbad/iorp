// Non-conformance reports (QUAL-NCR-002). Quantities and amounts are decimal strings.
export type NcrStatus = "open" | "investigation" | "action" | "verification" | "closed" | "cancelled";
export type NcrSourceType = "incoming_material" | "supplier" | "internal_production" | "warehouse" | "customer_return" | "other";
export type NcrReportType = "material_non_conformance" | "product_non_conformance" | "process_non_conformance" | "packaging_non_conformance"
  | "documentation_non_conformance" | "other";
export type NcrSeverity = "minor" | "major" | "critical";
export type NcrAction = "edit" | "contain" | "investigate" | "add_action" | "submit" | "verify" | "cancel";

export const NCR_STATUSES: NcrStatus[] = ["open", "investigation", "action", "verification", "closed", "cancelled"];
// The stages a report moves through, in order (cancelled is not a stage).
export const NCR_STAGES: NcrStatus[] = ["open", "investigation", "action", "verification", "closed"];
export const NCR_SOURCES: NcrSourceType[] = ["incoming_material", "supplier", "internal_production", "warehouse", "customer_return", "other"];
export const NCR_TYPES: NcrReportType[] = ["material_non_conformance", "product_non_conformance", "process_non_conformance", "packaging_non_conformance",
  "documentation_non_conformance", "other"];
export const SEVERITIES: NcrSeverity[] = ["minor", "major", "critical"];
export const DISPOSITIONS = ["return_to_supplier", "use_as_is", "sort", "rework", "regrade", "return_to_process", "scrap", "hold"] as const;
export const ROOT_CAUSE_CATEGORIES = ["man", "machine", "material", "method", "measurement", "environment"] as const;
export const ROOT_CAUSE_METHODS = ["five_whys", "fishbone", "other"] as const;
export const ACTION_KINDS = ["correction", "corrective", "preventive"] as const;
export const SUPPLIER_ACTIONS = ["none", "notify", "return_goods", "scar"] as const;
export const CLAIM_STATUSES = ["none", "claimed", "accepted", "rejected", "recovered"] as const;
export const COSTS = ["cost_material", "cost_labor", "cost_scrap", "cost_transport", "cost_other"] as const;
// Sources whose party is a supplier.
export const SUPPLIER_SOURCES: NcrSourceType[] = ["incoming_material", "supplier"];

export type NcrItemInput = {
  item_name: string; item_reference: string | null; quantity_affected: string | null; unit: string | null; issue_description: string;
  disposition: (typeof DISPOSITIONS)[number] | null; disposition_notes: string | null; notes: string | null;
};
export type NcrItem = NcrItemInput & { id: string; line_no: number };

export type NcrHeader = {
  report_date: string; source_type: NcrSourceType; report_type: NcrReportType; severity: NcrSeverity; title: string; description: string;
  reference_code: string | null; customer_name: string | null; supplier_id: string | null; supplier_name: string | null; supplier_reference: string | null;
  owner_user_id: string | null; due_date: string | null; supplier_action: (typeof SUPPLIER_ACTIONS)[number];
  supplier_response: string | null; supplier_responded_at: string | null;
  cost_material: string | null; cost_labor: string | null; cost_scrap: string | null; cost_transport: string | null; cost_other: string | null;
  claim_amount: string | null; claim_status: (typeof CLAIM_STATUSES)[number];
};
export type NcrCreateInput = Partial<NcrHeader> & Pick<NcrHeader, "report_date" | "source_type" | "report_type" | "title" | "description">
  & { items: NcrItemInput[] };

export type CorrectiveAction = {
  id: string; ncr_id: string; line_no: number; kind: (typeof ACTION_KINDS)[number]; description: string; owner_user_id: string | null;
  owner_name: string | null; due_date: string | null; status: "open" | "done" | "cancelled"; evidence: string | null; completed_at: string | null;
  completed_by_name: string | null; cancel_reason: string | null; overdue: boolean;
  report_number?: string | null; report_title?: string | null; report_status?: NcrStatus | null;
};
export type NcrAttachment = { id: string; file_name: string; content_type: string; size_bytes: number; uploaded_by_name: string | null; uploaded_at: string };
export type NcrHistoryEntry = { action: string; from_status: string | null; to_status: string; reason: string | null; actor_name: string | null; at: string };

export type NcrListItem = {
  id: string; report_number: string; report_date: string; source_type: NcrSourceType; report_type: NcrReportType; status: NcrStatus;
  severity: NcrSeverity; title: string; reference_code: string | null; supplier_name: string | null; customer_name: string | null;
  owner_user_id: string | null; owner_name: string | null; due_date: string | null; overdue: boolean; open_actions: number;
  overdue_actions: number; total_cost: string | null; actions: NcrAction[]; created_at: string;
};
export type NcrReport = NcrListItem & NcrHeader & {
  quality_check_id: string | null; quality_rejection_id: string | null; production_order_id: string | null; return_id: string | null;
  inspection_code: string | null; rejection_code: string | null; order_number: string | null; return_no: string | null; detected_by_name: string | null;
  containment: string | null; contained_at: string | null; contained_by_name: string | null;
  root_cause_category: string | null; root_cause_method: string | null; root_cause: string | null; action_required: boolean | null;
  no_action_justification: string | null; investigated_at: string | null; investigated_by_name: string | null;
  verification_attempts: number; verification_notes: string | null; verified_at: string | null; verified_by_name: string | null;
  closed_at: string | null; cancel_reason: string | null;
  items: NcrItem[]; corrective_actions: CorrectiveAction[]; attachments: NcrAttachment[]; history: NcrHistoryEntry[];
  can_complete_actions: boolean; updated_at: string;
};
export type UserOption = { id: string; name: string };
