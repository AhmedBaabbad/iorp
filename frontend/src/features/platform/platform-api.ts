import { apiClient as baseClient } from "@/lib/api-client";
import { requestStepUp } from "./platform-step-up";
async function apiClient<T>(path: string, options: Parameters<typeof baseClient>[1] = {}): Promise<T> {
  const method = options?.method ?? "GET";
  if (method !== "GET" && (path.startsWith("/platform/organizations") || path.startsWith("/platform/administrators"))) {
    const proof = await requestStepUp({ method, path, body: options?.body, token: options?.token });
    const headers = new Headers(options?.headers); headers.set("X-Platform-Step-Up", proof);
    return baseClient<T>(path, { ...options, headers });
  }
  return baseClient<T>(path, options);
}
import { storePlatformToken } from "@/lib/platform-auth";
import type {
  ChangePlatformPasswordRequest,
  CreateOrganizationRequest,
  CreateOrganizationResponse,
  PlatformAccount,
  PlatformAdministrator,
  PlatformAdministratorCreate,
  PlatformLoginRequest,
  PlatformLoginResponse,
  PlatformOrganizationSummary,
  PlatformOrganizationDetail,
  ResetOrganizationRootPasswordResponse,
} from "@/types/platform";

export type PlatformAuditEvent = {
  id: string; occurred_at: string; event_type: string; category: string; outcome: string; severity: string;
  actor_type: string; actor_id: string | null; actor_email_snapshot: string | null; actor_name_snapshot: string | null;
  target_type: string | null; target_id: string | null; target_display_snapshot: string | null;
  organization_id: string | null; request_id: string | null; correlation_id: string | null;
  ip_address: string | null; user_agent: string | null; reason: string | null;
  changes: unknown; metadata: unknown; error_code: string | null;
};

export type PlatformAuditList = { items: PlatformAuditEvent[]; total: number; page: number; page_size: number; pages: number };

export function listPlatformAuditLogs(query: URLSearchParams, token?: string | null) {
  return apiClient<PlatformAuditList>(`/platform/audit-logs?${query.toString()}`, { token });
}

export function getPlatformAuditLog(id: string, token?: string | null) {
  return apiClient<PlatformAuditEvent>(`/platform/audit-logs/${id}`, { token });
}

export async function platformLogin(payload: PlatformLoginRequest) {
  const response = await apiClient<PlatformLoginResponse>("/platform/login", {
    method: "POST",
    body: payload,
    token: null,
  });

  storePlatformToken(response.access_token);

  return response;
}

export function platformLogout() {
  return apiClient<void>("/platform/logout", { method: "POST", token: null, skipRefresh: true });
}

export function listPlatformAdministrators(token?: string | null) {
  return apiClient<PlatformAdministrator[]>("/platform/administrators", { token });
}

export function createPlatformAdministrator(payload: PlatformAdministratorCreate, token?: string | null) {
  return apiClient<PlatformAdministrator>("/platform/administrators", { method: "POST", body: payload, token });
}

export function updatePlatformAdministrator(
  id: string,
  payload: Partial<Pick<PlatformAdministrator, "full_name" | "email" | "role" | "status">>,
  token?: string | null,
) {
  return apiClient<PlatformAdministrator>(`/platform/administrators/${id}`, { method: "PATCH", body: payload, token });
}

export function deactivatePlatformAdministrator(id: string, token?: string | null) {
  return apiClient<PlatformAdministrator>(`/platform/administrators/${id}`, { method: "DELETE", token });
}

/** SEC-002: the administrator receives a reset link and chooses their own password; nobody sets it for them. */
export function resetPlatformAdministratorPassword(id: string, token?: string | null) {
  return apiClient<{ message: string; email: string }>(`/platform/administrators/${id}/reset-password`, { method: "POST", body: {}, token });
}

/** SEC-002: the organization's root receives a reset link; the platform never sets a customer's password. */
export function resetOrganizationRootPassword(organizationId: string, token?: string | null) {
  return apiClient<ResetOrganizationRootPasswordResponse>(`/platform/organizations/${organizationId}/reset-root-password`,
    { method: "POST", body: {}, token });
}

export function getPlatformAccount(token?: string | null) {
  return apiClient<PlatformAccount>("/platform/me", { token });
}

export function changePlatformPassword(payload: ChangePlatformPasswordRequest, token?: string | null) {
  return apiClient<{ message: string }>("/platform/change-password", {
    method: "POST",
    body: payload,
    token,
  });
}

export function listPlatformOrganizations(token?: string | null) {
  return apiClient<PlatformOrganizationSummary[]>("/platform/organizations", { token });
}

export function getPlatformOrganization(organizationId: string, token?: string | null) {
  return apiClient<PlatformOrganizationDetail>(`/platform/organizations/${organizationId}`, { token });
}

export function createPlatformOrganization(payload: CreateOrganizationRequest, token?: string | null) {
  return apiClient<CreateOrganizationResponse>("/platform/organizations", {
    method: "POST",
    body: payload,
    token,
  });
}

export function changeOrganizationStatus(
  organizationId: string,
  action: "suspend" | "activate" | "deactivate" | "archive",
  reason: string | null,
  token?: string | null,
) {
  return apiClient<PlatformOrganizationSummary>(`/platform/organizations/${organizationId}/${action}`, {
    method: "POST",
    body: { reason: reason || null },
    token,
  });
}
