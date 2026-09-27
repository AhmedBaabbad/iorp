import { apiClient } from "@/lib/api-client";
import type {
  AdminUserCreateRequest,
  AdminUserDetail,
  AdminUserListItem,
  AdminUserRoleAssignRequest,
  AdminUserUpdateRequest,
  UserDeactivationImpact,
  AssignableRolesResponse,
  RoleAssignmentResponse,
  RoleRemovalResponse,
  UserRolesResponse,
  EffectiveAccessReport,
} from "../types";

const BASE = "/admin/users";

export function listAdminUsers() {
  return apiClient<AdminUserListItem[]>(BASE);
}

export function getAdminUser(id: string) {
  return apiClient<AdminUserDetail>(`${BASE}/${id}`);
}

export function getAdminUserEffectiveAccess(id: string) {
  return apiClient<EffectiveAccessReport>(`${BASE}/${id}/effective-access`);
}

export function createAdminUser(payload: AdminUserCreateRequest) {
  return apiClient<AdminUserDetail>(BASE, { method: "POST", body: payload });
}

export function updateAdminUser(id: string, payload: AdminUserUpdateRequest) {
  return apiClient<AdminUserDetail>(`${BASE}/${id}`, { method: "PATCH", body: payload });
}

export function assignAdminRoleToUser(userId: string, payload: AdminUserRoleAssignRequest) {
  return apiClient<RoleAssignmentResponse>(`${BASE}/${userId}/roles`, { method: "POST", body: payload });
}

export function removeAdminRoleFromUser(userId: string, roleId: string) {
  return apiClient<RoleRemovalResponse>(`${BASE}/${userId}/roles/${roleId}`, { method: "DELETE" });
}

export function getAdminUserRoles(userId: string) {
  return apiClient<UserRolesResponse>(`${BASE}/${userId}/roles`);
}

export function getAssignableAdminRoles(userId: string) {
  return apiClient<AssignableRolesResponse>(`${BASE}/${userId}/assignable-roles`);
}

export function deactivateAdminUser(id: string) {
  return apiClient<AdminUserDetail>(`${BASE}/${id}`, { method: "DELETE" });
}

export function getUserDeactivationImpact(id: string) {
  return apiClient<UserDeactivationImpact>(`${BASE}/${id}/deactivation-impact`);
}

export function lockAdminUser(id: string) {
  return apiClient<AdminUserDetail>(`${BASE}/${id}/lock`, { method: "POST" });
}

export function unlockAdminUser(id: string) {
  return apiClient<AdminUserDetail>(`${BASE}/${id}/unlock`, { method: "POST" });
}

export function activateAdminUser(id: string) {
  return apiClient<AdminUserDetail>(`${BASE}/${id}/activate`, { method: "POST" });
}

export function resetAdminUserPassword(id: string, payload: { new_password: string; new_password_confirmation: string }) {
  return apiClient<{ message: string; sessions_invalidated: boolean }>(`${BASE}/${id}/reset-password`, { method: "POST", body: payload });
}
