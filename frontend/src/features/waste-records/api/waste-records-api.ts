import { apiClient } from "@/lib/api-client";
import type {
  CreateWasteRecordRequest,
  WasteRecordData,
  WasteRecordListFilters,
  WasteRecordListItem,
} from "../types";

const WASTE_RECORDS_PATH = "/production/waste-records";

export function getWasteRecords(filters: WasteRecordListFilters = {}) {
  const query = new URLSearchParams();

  if (filters.production_order_id) {
    query.set("production_order_id", filters.production_order_id);
  }

  if (filters.shift_report_id) {
    query.set("shift_report_id", filters.shift_report_id);
  }

  if (filters.work_center_id) {
    query.set("work_center_id", filters.work_center_id);
  }

  if (filters.waste_category) {
    query.set("waste_category", filters.waste_category);
  }

  if (filters.waste_date) {
    query.set("waste_date", filters.waste_date);
  }

  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return apiClient<WasteRecordListItem[]>(`${WASTE_RECORDS_PATH}${suffix}`);
}

export function getWasteRecordById(wasteRecordId: string) {
  return apiClient<WasteRecordData>(`${WASTE_RECORDS_PATH}/${wasteRecordId}`);
}

export function createWasteRecord(payload: CreateWasteRecordRequest) {
  return apiClient<WasteRecordData>(WASTE_RECORDS_PATH, {
    method: "POST",
    body: payload,
  });
}
