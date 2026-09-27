import { apiClient } from "@/lib/api-client";
import type {
  CreateQualityRejectionRequest,
  QualityRejectionData,
  QualityRejectionListFilters,
  QualityRejectionListItem,
  UpdateDispositionStatusRequest,
} from "../types";

const QUALITY_REJECTIONS_PATH = "/quality-rejections";

export function getQualityRejections(filters: QualityRejectionListFilters = {}) {
  const query = new URLSearchParams();

  if (filters.rejection_reason) {
    query.set("rejection_reason", filters.rejection_reason);
  }

  if (filters.disposition) {
    query.set("disposition", filters.disposition);
  }

  if (filters.disposition_status) {
    query.set("disposition_status", filters.disposition_status);
  }

  if (filters.quality_check_id) {
    query.set("quality_check_id", filters.quality_check_id);
  }

  if (filters.rejection_date) {
    query.set("rejection_date", filters.rejection_date);
  }

  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return apiClient<QualityRejectionListItem[]>(`${QUALITY_REJECTIONS_PATH}${suffix}`);
}

export function getQualityRejectionById(rejectionId: string) {
  return apiClient<QualityRejectionData>(`${QUALITY_REJECTIONS_PATH}/${rejectionId}`);
}

export function createQualityRejection(payload: CreateQualityRejectionRequest) {
  return apiClient<QualityRejectionData>(QUALITY_REJECTIONS_PATH, {
    method: "POST",
    body: payload,
  });
}

export function updateDispositionStatus(
  rejectionId: string,
  payload: UpdateDispositionStatusRequest = { disposition_status: "executed" },
) {
  return apiClient<QualityRejectionData>(`${QUALITY_REJECTIONS_PATH}/${rejectionId}`, {
    method: "PATCH",
    body: payload,
  });
}
