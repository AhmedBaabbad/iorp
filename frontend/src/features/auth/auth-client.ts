import { apiClient } from "@/lib/api-client";
import { storeAccessToken } from "@/lib/auth";
import type { CurrentUser, LoginRequest, LoginResponse } from "@/types/auth";

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
