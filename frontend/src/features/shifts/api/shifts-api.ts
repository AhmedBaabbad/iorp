import { apiClient } from "@/lib/api-client";
import type { CreateShiftRequest, ShiftData, ShiftDeletionImpact, ShiftListItem, UpdateShiftRequest } from "../types";

const SHIFT_DEFINITIONS_PATH = "/production/shift-definitions";

export function getShifts() {
  return apiClient<ShiftListItem[]>(SHIFT_DEFINITIONS_PATH);
}

export function getShiftById(shiftId: string) {
  return apiClient<ShiftData>(`${SHIFT_DEFINITIONS_PATH}/${shiftId}`);
}

export function createShift(payload: CreateShiftRequest) {
  return apiClient<ShiftData>(SHIFT_DEFINITIONS_PATH, {
    method: "POST",
    body: payload,
  });
}

export function updateShift(shiftId: string, payload: UpdateShiftRequest) {
  return apiClient<ShiftData>(`${SHIFT_DEFINITIONS_PATH}/${shiftId}`, {
    method: "PATCH",
    body: payload,
  });
}

export function getShiftDeletionImpact(shiftId: string) {
  return apiClient<ShiftDeletionImpact>(`${SHIFT_DEFINITIONS_PATH}/${shiftId}/deletion-impact`);
}

export function deleteShift(shiftId: string) {
  return apiClient<void>(`${SHIFT_DEFINITIONS_PATH}/${shiftId}`, { method: "DELETE" });
}
