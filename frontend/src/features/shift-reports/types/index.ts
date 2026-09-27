export type ShiftReportStatus = "draft" | "submitted" | "approved";

export type ShiftReportListFilters = {
  status?: ShiftReportStatus;
  work_center_id?: string;
  shift_definition_id?: string;
  report_date?: string;
};

export type ShiftReportListItem = {
  id: string;
  organization_id: string;
  work_center_id: string;
  shift_definition_id: string;
  production_order_id: string | null;
  report_date: string;
  shift_started_at: string | null;
  shift_ended_at: string | null;
  status: ShiftReportStatus;
  summary: string;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
};

export type ShiftReportData = ShiftReportListItem & {
  notes: string | null;
};

export type CreateShiftReportRequest = {
  work_center_id: string;
  shift_definition_id: string;
  production_order_id?: string | null;
  report_date: string;
  shift_started_at?: string | null;
  shift_ended_at?: string | null;
  summary: string;
  notes?: string | null;
};
