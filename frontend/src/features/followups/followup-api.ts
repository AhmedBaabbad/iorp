import { apiClient } from "@/lib/api-client";
import type {
  EligibleFollowUpAssignee,
  FollowUp,
  FollowUpCompleteRequest,
  FollowUpCreateRequest,
  FollowUpListFilters,
  FollowUpListResponse,
  FollowUpBulkReassignResponse,
  FollowUpUpdateRequest,
} from "@/types/followups";

function customerFollowUpsPath(customerId: string) {
  return `/commercial/customers/${customerId}/follow-ups`;
}

function toQueryString(filters?: FollowUpListFilters) {
  if (!filters) return "";
  const params = new URLSearchParams();
  if (filters.scope) params.set("scope", filters.scope);
  if (filters.status) params.set("status", filters.status);
  if (filters.priority) params.set("priority", filters.priority);
  if (filters.customer_id) params.set("customer_id", filters.customer_id);
  if (filters.assigned_user_id) params.set("assigned_user_id", filters.assigned_user_id);
  if (filters.unassigned) params.set("unassigned", "true");
  if (filters.due_from) params.set("due_from", filters.due_from);
  if (filters.due_to) params.set("due_to", filters.due_to);
  if (filters.overdue) params.set("overdue", "true");
  if (filters.search) params.set("search", filters.search);
  if (filters.page) params.set("page", String(filters.page));
  if (filters.page_size) params.set("page_size", String(filters.page_size));
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function listCustomerFollowUps(customerId: string) {
  return apiClient<FollowUp[]>(customerFollowUpsPath(customerId));
}

export function listFollowUps(filters?: FollowUpListFilters) {
  return apiClient<FollowUpListResponse>(`/commercial/follow-ups${toQueryString(filters)}`);
}

export function getFollowUpById(followUpId: string) {
  return apiClient<FollowUp>(`/commercial/follow-ups/${followUpId}`);
}

export function getEligibleAssignees() {
  return apiClient<EligibleFollowUpAssignee[]>("/commercial/follow-ups/eligible-assignees");
}

export function reassignFollowUpsByUser(fromUserId: string, toUserId: string) {
  return apiClient<FollowUpBulkReassignResponse>(
    "/commercial/follow-ups/reassign-by-user",
    {
      method: "POST",
      body: { from_user_id: fromUserId, to_user_id: toUserId },
    },
  );
}

export function createCustomerFollowUp(customerId: string, payload: FollowUpCreateRequest) {
  return apiClient<FollowUp>(customerFollowUpsPath(customerId), {
    method: "POST",
    body: payload,
  });
}

export function updateFollowUp(followUpId: string, payload: FollowUpUpdateRequest) {
  return apiClient<FollowUp>(`/commercial/follow-ups/${followUpId}`, {
    method: "PATCH",
    body: payload,
  });
}

export function deleteFollowUp(followUpId: string) {
  return apiClient<{ status: string }>(`/commercial/follow-ups/${followUpId}`, {
    method: "DELETE",
  });
}

export function completeFollowUp(followUpId: string, payload: FollowUpCompleteRequest = {}) {
  return apiClient<FollowUp>(`/commercial/follow-ups/${followUpId}/complete`, {
    method: "POST",
    body: payload,
  });
}

export function reopenFollowUp(followUpId: string) {
  return apiClient<FollowUp>(`/commercial/follow-ups/${followUpId}/reopen`, {
    method: "POST",
  });
}

export function cancelFollowUp(followUpId: string) {
  return apiClient<FollowUp>(`/commercial/follow-ups/${followUpId}/cancel`, {
    method: "POST",
  });
}
