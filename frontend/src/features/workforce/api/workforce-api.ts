import { apiClient } from "@/lib/api-client";
import type {
  CreateWorkforceMemberRequest,
  LinkUserRequest,
  UpdateWorkforceMemberRequest,
  WorkforceMember,
  WorkforceMemberDeleteResult,
  WorkforceMemberDeletionImpact,
  WorkforceMemberFilters,
  WorkforceMemberListItem,
} from "../types";
import type { AdminUserListItem } from "@/features/admin-users/types";

const WORKFORCE_MEMBERS_PATH = "/workforce-members";

function toQueryString(filters?: WorkforceMemberFilters) {
  if (!filters) return "";
  const params = new URLSearchParams();
  if (filters.worker_type) params.set("worker_type", filters.worker_type);
  if (filters.status) params.set("status", filters.status);
  if (filters.employment_type) params.set("employment_type", filters.employment_type);
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function getWorkforceMembers(filters?: WorkforceMemberFilters, token?: string | null) {
  return apiClient<WorkforceMemberListItem[]>(
    `${WORKFORCE_MEMBERS_PATH}${toQueryString(filters)}`,
    { token },
  );
}

export function getWorkforceMemberById(id: string, token?: string | null) {
  return apiClient<WorkforceMember>(`${WORKFORCE_MEMBERS_PATH}/${id}`, { token });
}

export function createWorkforceMember(
  data: CreateWorkforceMemberRequest,
  token?: string | null,
) {
  return apiClient<WorkforceMember>(WORKFORCE_MEMBERS_PATH, {
    method: "POST",
    body: data,
    token,
  });
}

export function updateWorkforceMember(
  id: string,
  data: UpdateWorkforceMemberRequest,
  token?: string | null,
) {
  return apiClient<WorkforceMember>(`${WORKFORCE_MEMBERS_PATH}/${id}`, {
    method: "PATCH",
    body: data,
    token,
  });
}

export function deleteWorkforceMember(id: string, token?: string | null) {
  return apiClient<WorkforceMemberDeleteResult>(`${WORKFORCE_MEMBERS_PATH}/${id}`, {
    method: "DELETE",
    token,
  });
}

export function getWorkforceMemberDeletionImpact(memberId: string, token?: string | null) {
  return apiClient<WorkforceMemberDeletionImpact>(
    `${WORKFORCE_MEMBERS_PATH}/${memberId}/deletion-impact`,
    { token },
  );
}

export function linkUserToMember(memberId: string, userId: string, token?: string | null) {
  const payload: LinkUserRequest = { user_id: userId };
  return apiClient<WorkforceMember>(`${WORKFORCE_MEMBERS_PATH}/${memberId}/link-user`, {
    method: "POST",
    body: payload,
    token,
  });
}

export function unlinkUserFromMember(memberId: string, token?: string | null) {
  return apiClient<WorkforceMember>(`${WORKFORCE_MEMBERS_PATH}/${memberId}/link-user`, {
    method: "DELETE",
    token,
  });
}

export function getUsers(token?: string | null) {
  return apiClient<AdminUserListItem[]>("/admin/users?selection=true", { token });
}
