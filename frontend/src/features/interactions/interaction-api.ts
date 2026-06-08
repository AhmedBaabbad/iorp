import { apiClient } from "@/lib/api-client";
import type {
  CustomerInteraction,
  CustomerInteractionCreateRequest,
} from "@/types/interactions";

function customerInteractionsPath(customerId: string) {
  return `/commercial/customers/${customerId}/interactions`;
}

export function listCustomerInteractions(customerId: string) {
  return apiClient<CustomerInteraction[]>(customerInteractionsPath(customerId));
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
