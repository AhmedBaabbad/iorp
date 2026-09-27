import { apiClient } from "@/lib/api-client";
import type { OrganizationAdminInput, OrganizationInput } from "@/types/organization-provisioning";

export type BootstrapStatus = { initialized: boolean };
export type SetupPayload = {
  bootstrap_token: string;
  platform_root: { full_name: string; email: string; password: string; password_confirmation: string };
  organization: OrganizationInput;
  organization_admin: OrganizationAdminInput;
};

export const getBootstrapStatus = () =>
  apiClient<BootstrapStatus>("/system/bootstrap/status", { token: null });

export const initializeSystem = (body: SetupPayload) =>
  apiClient("/system/bootstrap/initialize", { method: "POST", body, token: null });
