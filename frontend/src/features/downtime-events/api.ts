import { apiClient } from "@/lib/api-client";
import type { DowntimeEvent, DowntimeFilters, DowntimeInput, DowntimeSummary } from "./types";

const PATH = "/production/downtime-events";
const query = (filters: DowntimeFilters) => {
  const q = new URLSearchParams(Object.entries(filters).filter(([, v]) => Boolean(v)) as [string, string][]);
  return q.size ? `?${q}` : "";
};

export function getDowntimeEvents(filters: DowntimeFilters = {}) {
  return apiClient<DowntimeEvent[]>(`${PATH}${query(filters)}`);
}

// Totals for reports, over the same filters as the list.
export function getDowntimeSummary(filters: DowntimeFilters = {}) {
  return apiClient<DowntimeSummary>(`${PATH}/summary${query(filters)}`);
}

export function getDowntimeEventById(id: string) {
  return apiClient<DowntimeEvent>(`${PATH}/${id}`);
}

// Without end_time the stop stays open until closed.
export function createDowntimeEvent(body: DowntimeInput) {
  return apiClient<DowntimeEvent>(PATH, { method: "POST", body });
}

export function updateDowntimeEvent(id: string, body: Partial<DowntimeInput>) {
  return apiClient<DowntimeEvent>(`${PATH}/${id}`, { method: "PATCH", body });
}

// Ends an open stop, now unless another end is given.
export function closeDowntimeEvent(id: string, endTime?: string | null) {
  return apiClient<DowntimeEvent>(`${PATH}/${id}/close`, { method: "POST", body: endTime ? { end_time: endTime } : {} });
}

export function deleteDowntimeEvent(id: string) {
  return apiClient<void>(`${PATH}/${id}`, { method: "DELETE" });
}

export type RunOption = { id: string; run_date: string; status: string; work_center_id: string; production_order_id: string };

export function getOrderRuns(orderId: string) {
  return apiClient<RunOption[]>(`/production/runs?production_order_id=${orderId}`);
}
