import { apiClient } from "@/lib/api-client";
import type {
  CloseQualityCheckRequest, CreateQualityCheckRequest, InspectableOrder, QualityCheckData, QualityCheckListFilters, QualityCheckListItem,
  SampleOption, UpdateQualityCheckRequest,
} from "../types";

const PATH = "/quality/quality-checks";

export function getQualityChecks(filters: QualityCheckListFilters = {}) {
  const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => Boolean(value)) as [string, string][]);
  return apiClient<QualityCheckListItem[]>(`${PATH}${query.size ? `?${query}` : ""}`);
}

export function getQualityCheckById(id: string) {
  return apiClient<QualityCheckData>(`${PATH}/${id}`);
}

// Opens an inspection; a production lot needs its order running, held or completed.
export function createQualityCheck(body: CreateQualityCheckRequest) {
  return apiClient<QualityCheckData>(PATH, { method: "POST", body });
}

export function updateQualityCheck(id: string, body: UpdateQualityCheckRequest) {
  return apiClient<QualityCheckData>(`${PATH}/${id}`, { method: "PATCH", body });
}

export function startQualityCheck(id: string) {
  return apiClient<QualityCheckData>(`${PATH}/${id}/start`, { method: "POST" });
}

// Result and quantities; a rejected quantity opens a rejection awaiting a decision.
export function closeQualityCheck(id: string, body: CloseQualityCheckRequest) {
  return apiClient<QualityCheckData>(`${PATH}/${id}/close`, { method: "POST", body });
}

export function cancelQualityCheck(id: string, reason: string) {
  return apiClient<QualityCheckData>(`${PATH}/${id}/cancel`, { method: "POST", body: { reason } });
}

export function getInspectableOrders(search = "") {
  return apiClient<InspectableOrder[]>(`${PATH}/lookups/orders?q=${encodeURIComponent(search)}`);
}

export function getInspectableSamples(search = "") {
  return apiClient<SampleOption[]>(`${PATH}/lookups/samples?q=${encodeURIComponent(search)}`);
}
