import { apiClient } from "@/lib/api-client";
import type {
  CreateNcrReportRequest,
  NcrReportData,
  NcrReportListFilters,
  NcrReportListItem,
  UpdateNcrReportStatusRequest,
} from "../types";

const BASE = "/quality/non-conformance-reports";

export function getNCRReports(filters: NcrReportListFilters = {}) {
  const query = new URLSearchParams();

  if (filters.source_type) {
    query.set("source_type", filters.source_type);
  }

  if (filters.report_type) {
    query.set("report_type", filters.report_type);
  }

  if (filters.status) {
    query.set("ncr_status", filters.status);
  }

  if (filters.report_date) {
    query.set("report_date", filters.report_date);
  }

  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return apiClient<NcrReportListItem[]>(`${BASE}${suffix}`);
}

export function getNcrReportById(ncrReportId: string) {
  return apiClient<NcrReportData>(`${BASE}/${ncrReportId}`);
}

export function createNcrReport(payload: CreateNcrReportRequest) {
  return apiClient<NcrReportData>(BASE, {
    method: "POST",
    body: payload,
  });
}

export function updateNcrReportStatus(
  ncrReportId: string,
  payload: UpdateNcrReportStatusRequest,
) {
  return apiClient<NcrReportData>(`${BASE}/${ncrReportId}`, {
    method: "PATCH",
    body: payload,
  });
}
