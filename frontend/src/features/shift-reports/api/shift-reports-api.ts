import { apiClient } from "@/lib/api-client";
import type {
  CreateShiftReportRequest,
  ShiftReportData,
  ShiftReportListFilters,
  ShiftReportListItem,
  ShiftReportStatus,
} from "../types";

const SHIFT_REPORTS_PATH = "/production/shift-reports";

export function getShiftReports(filters: ShiftReportListFilters = {}) {
  const query = new URLSearchParams();

  if (filters.status) {
    query.set("status", filters.status);
  }

  if (filters.work_center_id) {
    query.set("work_center_id", filters.work_center_id);
  }

  if (filters.shift_definition_id) {
    query.set("shift_definition_id", filters.shift_definition_id);
  }

  if (filters.report_date) {
    query.set("report_date", filters.report_date);
  }

  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return apiClient<ShiftReportListItem[]>(`${SHIFT_REPORTS_PATH}${suffix}`);
}

export function getShiftReportById(shiftReportId: string) {
  return apiClient<ShiftReportData>(`${SHIFT_REPORTS_PATH}/${shiftReportId}`);
}

export function createShiftReport(payload: CreateShiftReportRequest) {
  return apiClient<ShiftReportData>(SHIFT_REPORTS_PATH, {
    method: "POST",
    body: payload,
  });
}

export function updateShiftReportStatus(
  shiftReportId: string,
  status: ShiftReportStatus,
) {
  return apiClient<ShiftReportData>(`${SHIFT_REPORTS_PATH}/${shiftReportId}`, {
    method: "PATCH",
    body: { status },
  });
}
