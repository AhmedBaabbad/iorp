import { apiClient } from "@/lib/api-client";
import type {
  PermissionGroup,
  RoleCreateRequest,
  RoleDetail,
  RoleListItem,
  RolePermissionAssignRequest,
  RoleUpdateRequest,
} from "../types";

const BASE = "/foundation/roles";
const PERMS_BASE = "/foundation/permissions";

export function listRoles() {
  return apiClient<RoleListItem[]>(BASE);
}

export function getRole(id: string) {
  return apiClient<RoleDetail>(`${BASE}/${id}`);
}

export function createRole(payload: RoleCreateRequest) {
  return apiClient<RoleDetail>(BASE, { method: "POST", body: payload });
}

export function updateRole(id: string, payload: RoleUpdateRequest) {
  return apiClient<RoleDetail>(`${BASE}/${id}`, { method: "PATCH", body: payload });
}

export function deleteRole(id: string) {
  return apiClient<void>(`${BASE}/${id}`, { method: "DELETE" });
}

export function assignPermissionToRole(roleId: string, payload: RolePermissionAssignRequest) {
  return apiClient<RoleDetail>(`${BASE}/${roleId}/permissions`, { method: "POST", body: payload });
}

export function removePermissionFromRole(roleId: string, permissionId: string) {
  return apiClient<void>(`${BASE}/${roleId}/permissions/${permissionId}`, { method: "DELETE" });
}

export function listPermissions() {
  return apiClient<PermissionGroup[]>(PERMS_BASE);
}
