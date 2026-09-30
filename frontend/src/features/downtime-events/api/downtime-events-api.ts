import { apiClient } from "@/lib/api-client";
import type {
  CreateDowntimeEventRequest,
  DowntimeEventData,
  DowntimeEventListFilters,
  DowntimeEventListItem,
  EndDowntimeEventRequest,
} from "../types";

const DOWNTIME_EVENTS_PATH = "/production/downtime-events";

export function getDowntimeEvents(filters: DowntimeEventListFilters = {}) {
  const query = new URLSearchParams();

  if (filters.work_center_id) {
    query.set("work_center_id", filters.work_center_id);
  }

  if (filters.production_order_id) {
    query.set("production_order_id", filters.production_order_id);
  }

  if (filters.status) {
    query.set("status", filters.status);
  }

  if (filters.category) {
    query.set("category", filters.category);
  }

  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return apiClient<DowntimeEventListItem[]>(`${DOWNTIME_EVENTS_PATH}${suffix}`);
}

export function getDowntimeEventById(downtimeEventId: string) {
  return apiClient<DowntimeEventData>(`${DOWNTIME_EVENTS_PATH}/${downtimeEventId}`);
}

export function createDowntimeEvent(payload: CreateDowntimeEventRequest) {
  return apiClient<DowntimeEventData>(DOWNTIME_EVENTS_PATH, {
    method: "POST",
    body: payload,
  });
}

export function endDowntimeEvent(downtimeEventId: string, endTime: string) {
  const payload: EndDowntimeEventRequest = { end_time: endTime };

  return apiClient<DowntimeEventData>(`${DOWNTIME_EVENTS_PATH}/${downtimeEventId}`, {
    method: "PATCH",
    body: payload,
  });
}
