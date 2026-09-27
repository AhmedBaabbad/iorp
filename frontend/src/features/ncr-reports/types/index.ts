export type NCRStatus = "draft" | "open" | "under_review" | "closed";

export type NCRSourceType =
  | "internal_production"
  | "incoming_material"
  | "supplier"
  | "warehouse"
  | "customer_return"
  | "other";

export type NCRReportType =
  | "material_non_conformance"
  | "product_non_conformance"
  | "process_non_conformance"
  | "packaging_non_conformance"
  | "documentation_non_conformance"
  | "other";

export type NcrReportListFilters = {
  source_type?: NCRSourceType;
  report_type?: NCRReportType;
  status?: NCRStatus;
  report_date?: string;
};

export type NcrReportListItem = {
  id: string;
  organization_id: string;
  report_number: string;
  report_date: string;
  source_type: NCRSourceType;
  report_type: NCRReportType;
  status: NCRStatus;
  title: string;
  reference_code: string | null;
  quality_check_id: string | null;
  quality_rejection_id: string | null;
  created_at: string;
  updated_at: string;
};

export type NcrReportData = NcrReportListItem & {
  description: string;
  detected_by_user_id: string;
};

export type CreateNcrReportRequest = {
  report_date: string;
  source_type: NCRSourceType;
  report_type: NCRReportType;
  title: string;
  description: string;
  reference_code?: string | null;
  quality_check_id?: string | null;
  quality_rejection_id?: string | null;
};

export type UpdateNcrReportStatusRequest = {
  status: NCRStatus;
};
