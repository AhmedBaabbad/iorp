import { apiClient } from "@/lib/api-client";
import type {
  AccessScope,
  AdminRoleCreateRequest,
  AdminRoleDetail,
  AdminRoleListItem,
  AdminRolePermissionAssignRequest,
  AdminRoleUpdateRequest,
} from "../types";

const BASE = "/admin/roles";

export function listAdminRoles() {
  return apiClient<AdminRoleListItem[]>(BASE);
}

export function getAdminRole(id: string) {
  return apiClient<AdminRoleDetail>(`${BASE}/${id}`);
}

export function createAdminRole(payload: AdminRoleCreateRequest) {
  return apiClient<AdminRoleDetail>(BASE, { method: "POST", body: payload });
}

export function updateAdminRole(id: string, payload: AdminRoleUpdateRequest) {
  return apiClient<AdminRoleDetail>(`${BASE}/${id}`, { method: "PATCH", body: payload });
}

export function assignAdminPermissionToRole(
  roleId: string,
  payload: AdminRolePermissionAssignRequest,
) {
  return apiClient<AdminRoleDetail>(`${BASE}/${roleId}/permissions`, {
    method: "POST",
    body: payload,
  });
}

export function deleteAdminRole(id: string) {
  return apiClient<void>(`${BASE}/${id}`, { method: "DELETE" });
}

export function removeAdminPermissionFromRole(roleId: string, permissionCode: string) {
  return apiClient<void>(`${BASE}/${roleId}/permissions/${permissionCode}`, { method: "DELETE" });
}

export function updateAdminRolePermissionScope(roleId: string, permissionCode: string, scope: AccessScope) {
  return apiClient<AdminRoleDetail>(`${BASE}/${roleId}/permissions/${permissionCode}`, {
    method: "PATCH",
    body: { scope },
  });
}
