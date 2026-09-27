import { apiClient } from "@/lib/api-client";
import type { AdminPermissionCatalog, AdminPermissionGroup } from "../types";

const BASE = "/admin/permissions";

export function getAdminPermissionCatalog() {
  return apiClient<AdminPermissionCatalog>(BASE);
}

export async function listAdminPermissions(): Promise<AdminPermissionGroup[]> {
  return (await getAdminPermissionCatalog()).modules;
}
