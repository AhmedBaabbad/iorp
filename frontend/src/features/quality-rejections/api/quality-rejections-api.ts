import { apiClient } from "@/lib/api-client";
import type {
  CreateQualityRejectionRequest, QualityRejectionData, QualityRejectionListFilters, QualityRejectionListItem, RejectionDecisionRequest,
  UpdateQualityRejectionRequest,
} from "../types";

const PATH = "/quality/quality-rejections";

export function getQualityRejections(filters: QualityRejectionListFilters = {}) {
  const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => Boolean(value)) as [string, string][]);
  return apiClient<QualityRejectionListItem[]>(`${PATH}${query.size ? `?${query}` : ""}`);
}

export function getQualityRejectionById(id: string) {
  return apiClient<QualityRejectionData>(`${PATH}/${id}`);
}

// A rejection not opened by closing a check: from a closed check or for a named production order.
export function createQualityRejection(body: CreateQualityRejectionRequest) {
  return apiClient<QualityRejectionData>(PATH, { method: "POST", body });
}

export function updateQualityRejection(id: string, body: UpdateQualityRejectionRequest) {
  return apiClient<QualityRejectionData>(`${PATH}/${id}`, { method: "PATCH", body });
}

export function decideQualityRejection(id: string, body: RejectionDecisionRequest) {
  return apiClient<QualityRejectionData>(`${PATH}/${id}/decide`, { method: "POST", body });
}

export function executeQualityRejection(id: string, execution_notes?: string | null) {
  return apiClient<QualityRejectionData>(`${PATH}/${id}/execute`, { method: "POST", body: { execution_notes: execution_notes || null } });
}
