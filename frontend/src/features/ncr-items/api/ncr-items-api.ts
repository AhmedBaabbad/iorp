import { apiClient } from "@/lib/api-client";
import type {
  CreateNcrItemRequest,
  NcrItemData,
  NcrItemListItem,
} from "../types";

function ncrReportItemsPath(reportId: string) {
  return `/quality/non-conformance-reports/${reportId}/items`;
}

export function getItemsByReport(reportId: string) {
  return apiClient<NcrItemListItem[]>(ncrReportItemsPath(reportId));
}

export function createItem(reportId: string, payload: CreateNcrItemRequest) {
  return apiClient<NcrItemData>(ncrReportItemsPath(reportId), {
    method: "POST",
    body: payload,
  });
}

export function getItemById(itemId: string) {
  return apiClient<NcrItemData>(`/quality/non-conformance-items/${itemId}`);
}
