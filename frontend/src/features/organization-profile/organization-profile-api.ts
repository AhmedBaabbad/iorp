import { API_BASE_URL, apiClient, ApiClientError } from "@/lib/api-client";
import type { OrganizationLifecycleStatus } from "@/types/platform";

export type OrganizationProfile = {
  id: string; name: string; code: string; status: OrganizationLifecycleStatus;
  industry_type: string | null; timezone: string; default_locale: "ar" | "en";
  has_logo: boolean; logo_url: string | null; created_at: string; updated_at: string;
};

export const getOrganizationProfile = (token?: string | null) => apiClient<OrganizationProfile>("/organization/profile", { token });
export const updateOrganizationProfile = (body: Pick<OrganizationProfile, "name" | "industry_type" | "timezone" | "default_locale">, token?: string | null) => apiClient<OrganizationProfile>("/organization/profile", { method: "PATCH", body, token });
export const removeOrganizationLogo = (token?: string | null) => apiClient<{ message: string; has_logo: boolean }>("/organization/logo", { method: "DELETE", token });

export async function uploadOrganizationLogo(file: File, token?: string | null) {
  const form = new FormData(); form.append("file", file);
  const response = await fetch(`${API_BASE_URL}/api/v1/organization/logo`, { method: "POST", headers: token ? { Authorization: `Bearer ${token}` } : {}, body: form });
  const data = await response.json();
  if (!response.ok) throw new ApiClientError(data.message ?? data.detail ?? "Request failed.", response.status, data);
  return data as { message: string; has_logo: boolean; logo_url: string };
}
