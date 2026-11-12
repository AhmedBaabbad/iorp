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

export function permanentlyDeleteAdminUser(id: string, reason: string) {
  return apiClient<{deleted:boolean}>(`${BASE}/${id}/permanent`, {method:"DELETE",body:{reason},notify:false});
}

export function listAdminUsers() {
  return apiClient<AdminUserListItem[]>(BASE);
}

export function getAdminUser(id: string) {
  return apiClient<AdminUserDetail>(`${BASE}/${id}`);
}

export function getAdminUserEffectiveAccess(id: string, locale?: string) {
  return apiClient<EffectiveAccessReport>(`${BASE}/${id}/effective-access`, { headers: locale ? { "Accept-Language": locale } : undefined });
}

export function createAdminUser(payload: AdminUserCreateRequest) {
  return apiClient<AdminUserDetail>(BASE, { method: "POST", body: payload, notify: false });
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

export function deactivateAdminUser(id: string, reason: string) {
  return apiClient<AdminUserDetail>(`${BASE}/${id}/deactivate`, { method: "POST", body: { reason } });
}

export function getUserDeactivationImpact(id: string) {
  return apiClient<UserDeactivationImpact>(`${BASE}/${id}/deactivation-impact`);
}

export function lockAdminUser(id: string, reason: string) {
  return apiClient<AdminUserDetail>(`${BASE}/${id}/lock`, { method: "POST", body: { reason } });
}

export function unlockAdminUser(id: string, reason: string) {
  return apiClient<AdminUserDetail>(`${BASE}/${id}/unlock`, { method: "POST", body: { reason } });
}

export function activateAdminUser(id: string, reason: string) {
  return apiClient<AdminUserDetail>(`${BASE}/${id}/activate`, { method: "POST", body: { reason } });
}

/** SEC-002: a reset link e-mailed to the user, who chooses their own password; no administrator ever sets nor learns it. */
export type PasswordResetResult = { method: "link"; email: string };
export function resetAdminUserPassword(id: string) {
  return apiClient<PasswordResetResult>(`${BASE}/${id}/reset-password`, { method: "POST", body: {}, notify: false });
}

/** SEC-001: a user's sign-ins, and signing them out everywhere. */
export type UserSession = { id: string; device: string; ip_address: string | null; started_at: string; last_active_at: string; current: boolean };
export function getAdminUserSessions(id: string) {
  return apiClient<UserSession[]>(`${BASE}/${id}/sessions`);
}
export function endAdminUserSessions(id: string) {
  return apiClient<{ ended: number }>(`${BASE}/${id}/sessions/end`, { method: "POST", notify: false });
}

export function archiveAdminUser(id: string, reason: string, restore = false) {return apiClient<AdminUserDetail>(`${BASE}/${id}/${restore ? "restore" : "archive"}`, {method:"POST",body:{reason}});}
