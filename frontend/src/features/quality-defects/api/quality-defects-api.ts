import { apiClient } from "@/lib/api-client";
import type {
  CreateQualityDefectRequest,
  QualityDefectData,
  QualityDefectListItem,
} from "../types";

function qualityCheckDefectsPath(qualityCheckId: string) {
  return `/quality-checks/${qualityCheckId}/defects`;
}

export function getDefectsByCheck(qualityCheckId: string) {
  return apiClient<QualityDefectListItem[]>(qualityCheckDefectsPath(qualityCheckId));
}

export function createDefect(
  qualityCheckId: string,
  payload: CreateQualityDefectRequest,
) {
  return apiClient<QualityDefectData>(qualityCheckDefectsPath(qualityCheckId), {
    method: "POST",
    body: payload,
  });
}

export function getDefectById(defectId: string) {
  return apiClient<QualityDefectData>(`/quality-defects/${defectId}`);
}
