import { apiClient } from "@/lib/api-client";
import type { WasteRecordData, WasteRecordInput, WasteRecordListFilters, WasteRecordListItem, WasteRecordUpdate, WasteSummary } from "./types";

const PATH = "/production/waste-records";

export function getWasteRecords(filters: WasteRecordListFilters = {}) {
  const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => Boolean(value)) as [string, string][]);
  return apiClient<WasteRecordListItem[]>(`${PATH}${query.size ? `?${query}` : ""}`);
}

export function getWasteRecordById(id: string) {
  return apiClient<WasteRecordData>(`${PATH}/${id}`);
}

// While the order is in progress, on hold or completed; closed orders are locked.
export function createWasteRecord(body: WasteRecordInput) {
  return apiClient<WasteRecordData>(PATH, { method: "POST", body });
}

export function updateWasteRecord(id: string, body: WasteRecordUpdate) {
  return apiClient<WasteRecordData>(`${PATH}/${id}`, { method: "PATCH", body });
}

export function deleteWasteRecord(id: string) {
  return apiClient<void>(`${PATH}/${id}`, { method: "DELETE" });
}

// An order's waste per unit and category; kept apart from the final result's scrap.
export function getWasteSummary(orderId: string) {
  return apiClient<WasteSummary>(`${PATH}/summary?production_order_id=${orderId}`);
}

export type RunOption = { id: string; run_date: string; status: string; work_center_id: string };

export function getOrderRuns(orderId: string) {
  return apiClient<RunOption[]>(`/production/runs?production_order_id=${orderId}`);
}
