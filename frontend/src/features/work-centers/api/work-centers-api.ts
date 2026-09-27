import { apiClient } from "@/lib/api-client";
import type {
  CreateWorkCenterRequest,
  UpdateWorkCenterRequest,
  WorkCenterData,
  WorkCenterDeleteSummary,
  WorkCenterListItem,
} from "../types";

const WORK_CENTERS_PATH = "/production/work-centers";

export function getWorkCenters() {
  return apiClient<WorkCenterListItem[]>(WORK_CENTERS_PATH);
}

export function getWorkCenterById(workCenterId: string) {
  return apiClient<WorkCenterData>(`${WORK_CENTERS_PATH}/${workCenterId}`);
}

export function createWorkCenter(payload: CreateWorkCenterRequest) {
  return apiClient<WorkCenterData>(WORK_CENTERS_PATH, {
    method: "POST",
    body: payload,
  });
}

export function updateWorkCenter(workCenterId: string, payload: UpdateWorkCenterRequest) {
  return apiClient<WorkCenterData>(`${WORK_CENTERS_PATH}/${workCenterId}`, {
    method: "PATCH",
    body: payload,
  });
}

export function getWorkCenterDeleteSummary(workCenterId: string) {
  return apiClient<WorkCenterDeleteSummary>(
    `${WORK_CENTERS_PATH}/${workCenterId}/delete-summary`,
  );
}

export function deleteWorkCenter(workCenterId: string) {
  return apiClient<void>(`${WORK_CENTERS_PATH}/${workCenterId}`, { method: "DELETE" });
}
