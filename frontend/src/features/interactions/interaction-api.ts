import { apiClient } from "@/lib/api-client";
import type { Page } from "@/lib/pagination";
import type {
  CustomerInteraction,
  CustomerInteractionCreateRequest,
} from "@/types/interactions";

function customerInteractionsPath(customerId: string) {
  return `/commercial/customers/${customerId}/interactions`;
}

/** One page of the customer's interactions, the latest first. */
export function listCustomerInteractions(customerId: string, page = 1, pageSize = 25) {
  return apiClient<Page<CustomerInteraction>>(`${customerInteractionsPath(customerId)}?page=${page}&page_size=${pageSize}`);
}

/** Corrects a recorded interaction (commercial:interactions:update). */
export function updateCustomerInteraction(customerId: string, interactionId: string, payload: Partial<CustomerInteractionCreateRequest>) {
  return apiClient<CustomerInteraction>(`${customerInteractionsPath(customerId)}/${interactionId}`, { method: "PATCH", body: payload });
}

/** Removes an interaction recorded by mistake (commercial:interactions:delete). */
export function deleteCustomerInteraction(customerId: string, interactionId: string) {
  return apiClient<void>(`${customerInteractionsPath(customerId)}/${interactionId}`, { method: "DELETE" });
}

export function createCustomerInteraction(
  customerId: string,
  payload: CustomerInteractionCreateRequest,
) {
  return apiClient<CustomerInteraction>(customerInteractionsPath(customerId), {
    method: "POST",
    body: payload,
  });
}
