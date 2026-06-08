import { apiClient } from "@/lib/api-client";
import type {
  FollowUpCompleteRequest,
  FollowUpCreateRequest,
  FollowUpListItem,
} from "@/types/followups";

function customerFollowUpsPath(customerId: string) {
  return `/commercial/customers/${customerId}/follow-ups`;
}

export function listCustomerFollowUps(customerId: string) {
  return apiClient<FollowUpListItem[]>(customerFollowUpsPath(customerId));
}

export function createCustomerFollowUp(customerId: string, payload: FollowUpCreateRequest) {
  return apiClient<FollowUpListItem>(customerFollowUpsPath(customerId), {
    method: "POST",
    body: payload,
  });
}

export function completeFollowUp(followUpId: string, payload: FollowUpCompleteRequest = {}) {
  return apiClient<FollowUpListItem>(`/commercial/follow-ups/${followUpId}/complete`, {
    method: "PATCH",
    body: payload,
  });
}
