import { apiClient } from "@/lib/api-client";
import type { EffectiveAccessReport } from "@/features/admin-users/types";
import { storeAccessToken } from "@/lib/auth";
import type { CurrentUser, LoginRequest, LoginResponse, UserProfileUpdate } from "@/types/auth";

export async function login(payload: LoginRequest) {
  const response = await apiClient<LoginResponse>("/auth/login", {
    method: "POST",
    body: payload,
    token: null,
  });

  storeAccessToken(response.access_token);

  return response;
}

export function getCurrentUser(token?: string | null) {
  return apiClient<CurrentUser>("/auth/me", { token });
}

export function updateMyProfile(payload: UserProfileUpdate) {
  return apiClient<CurrentUser>("/auth/me", { method: "PATCH", body: payload });
}

export function getMyEffectiveAccess(locale?: string) {
  return apiClient<EffectiveAccessReport>("/auth/me/effective-access", { headers: locale ? { "Accept-Language": locale } : undefined });
}

export function changePassword(payload: {
  current_password: string;
  new_password: string;
  new_password_confirmation: string;
}) {
  return apiClient<{ message: string; session_invalidated: boolean }>("/auth/change-password", {
    method: "POST",
    body: payload,
  });
}

export function logoutSession() {
  return apiClient<void>("/auth/logout", { method: "POST", token: null, skipRefresh: true });
}
