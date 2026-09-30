import { apiClient } from "@/lib/api-client";
import type {
  CreateQualityCheckRequest,
  QualityCheckData,
  QualityCheckListFilters,
  QualityCheckListItem,
  UpdateQualityCheckStatusRequest,
} from "../types";

const QUALITY_CHECKS_PATH = "/quality-checks";

export function getQualityChecks(filters: QualityCheckListFilters = {}) {
  const query = new URLSearchParams();

  if (filters.check_type) {
    query.set("check_type", filters.check_type);
  }

  if (filters.status) {
    query.set("check_status", filters.status);
  }

  if (filters.result) {
    query.set("result", filters.result);
  }

  if (filters.production_order_id) {
    query.set("production_order_id", filters.production_order_id);
  }

  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return apiClient<QualityCheckListItem[]>(`${QUALITY_CHECKS_PATH}${suffix}`);
}

export function getQualityCheckById(qualityCheckId: string) {
  return apiClient<QualityCheckData>(`${QUALITY_CHECKS_PATH}/${qualityCheckId}`);
}

export function createQualityCheck(payload: CreateQualityCheckRequest) {
  return apiClient<QualityCheckData>(QUALITY_CHECKS_PATH, {
    method: "POST",
    body: payload,
  });
}

export function updateQualityCheckStatus(
  qualityCheckId: string,
  payload: UpdateQualityCheckStatusRequest,
) {
  return apiClient<QualityCheckData>(`${QUALITY_CHECKS_PATH}/${qualityCheckId}`, {
    method: "PATCH",
    body: payload,
  });
}
