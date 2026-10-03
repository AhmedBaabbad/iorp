import { apiClient } from "@/lib/api-client";
import type { OrderResult, ResultCorrectionInput, ResultEntryInput, ResultOverviewRow } from "./types";

const base = (orderId: string) => `/production/production-orders/${orderId}/result`;

export function getOrderResult(orderId: string) {
  return apiClient<OrderResult>(base(orderId));
}

// Completed orders only. Every write answers with the recomputed result.
export function createResultEntry(orderId: string, body: ResultEntryInput) {
  return apiClient<OrderResult>(`${base(orderId)}/entries`, { method: "POST", body });
}

export function updateResultEntry(orderId: string, entryId: string, body: Partial<ResultEntryInput>) {
  return apiClient<OrderResult>(`${base(orderId)}/entries/${entryId}`, { method: "PATCH", body });
}

export function deleteResultEntry(orderId: string, entryId: string) {
  return apiClient<void>(`${base(orderId)}/entries/${entryId}`, { method: "DELETE" });
}

// Closed orders only: a signed delta with a mandatory reason; the original entry stays as it was.
export function correctResultEntry(orderId: string, entryId: string, body: ResultCorrectionInput) {
  return apiClient<OrderResult>(`${base(orderId)}/entries/${entryId}/corrections`, { method: "POST", body });
}

// Completed and closed orders with their result totals, for the results screen.
export function getResultsOverview(status?: "completed" | "closed") {
  return apiClient<ResultOverviewRow[]>(`/production/production-results${status ? `?status=${status}` : ""}`);
}
