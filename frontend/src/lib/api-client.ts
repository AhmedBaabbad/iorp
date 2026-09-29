import { getStoredAccessToken, removeStoredAccessToken, storeAccessToken } from "./auth";
import { getStoredPlatformToken, removeStoredPlatformToken, storePlatformToken } from "./platform-auth";

type ApiClientOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  token?: string | null;
  headers?: HeadersInit;
  skipRefresh?: boolean;
};

export class ApiClientError extends Error {
  status: number;
  details: unknown;

  constructor(message: string, status: number, details?: unknown) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.details = details;
  }
}

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8080";

const ORGANIZATION_STATUS_BY_CODE = {
  ORGANIZATION_SUSPENDED: "suspended",
  ORGANIZATION_INACTIVE: "inactive",
  ORGANIZATION_ARCHIVED: "archived",
} as const;

type OrganizationStatus = (typeof ORGANIZATION_STATUS_BY_CODE)[keyof typeof ORGANIZATION_STATUS_BY_CODE];

function buildUrl(path: string) {
  const baseUrl = API_BASE_URL.replace(/\/$/, "");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;

  return `${baseUrl}/api/v1${normalizedPath}`;
}

function extractDetailMessage(detail: unknown): string | null {
  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (item && typeof item === "object" && "msg" in item ? String(item.msg) : null))
      .filter((msg): msg is string => Boolean(msg));
    return messages.length > 0 ? messages.join("; ") : null;
  }

  return null;
}

async function readResponse(response: Response) {
  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get("content-type") ?? "";

  if (!contentType.includes("application/json")) {
    return null;
  }

  const text = await response.text();
  if (!text) {
    return null;
  }

  return JSON.parse(text);
}

function getOrganizationStatus(data: unknown): OrganizationStatus | null {
  if (!data || typeof data !== "object" || !("code" in data)) {
    return null;
  }

  const code = String(data.code) as keyof typeof ORGANIZATION_STATUS_BY_CODE;
  return ORGANIZATION_STATUS_BY_CODE[code] ?? null;
}

function redirectForOrganizationStatus(
  path: string,
  response: Response,
  data: unknown,
  sentTenantToken: boolean,
): Promise<never> | null {
  const status = getOrganizationStatus(data);
  const shouldSkip =
    path.includes("/auth/login") ||
    path.includes("/platform/") ||
    path.includes("/system/bootstrap/") ||
    !sentTenantToken;

  if (response.status !== 403 || !status || shouldSkip || typeof window === "undefined") {
    return null;
  }

  removeStoredAccessToken();
  window.location.href = `/org-suspended?status=${status}`;
  return new Promise<never>(() => undefined);
}

function redirectForAccountStatus(path: string, response: Response, data: unknown, sentTenantToken: boolean): Promise<never> | null {
  if (!data || typeof data !== "object" || !("code" in data)) return null;
  const code = String(data.code);
  const account = code === "ACCOUNT_LOCKED" ? "locked" : code === "ACCOUNT_INACTIVE" ? "inactive" : null;
  if (response.status !== 403 || !account || !sentTenantToken || path.includes("/auth/login") || typeof window === "undefined") return null;
  removeStoredAccessToken();
  window.location.href = `/login?account=${account}`;
  return new Promise<never>(() => undefined);
}

let sessionRedirectInProgress = false;
let tenantRefreshPromise: Promise<string> | null = null;
let platformRefreshPromise: Promise<string> | null = null;

async function refreshAccessToken(isPlatform: boolean): Promise<string> {
  const current = isPlatform ? platformRefreshPromise : tenantRefreshPromise;
  if (current) return current;
  const promise = (async () => {
    const response = await fetch(buildUrl(isPlatform ? "/platform/refresh" : "/auth/refresh"), {
      method: "POST",
      credentials: "include",
      cache: "no-store",
    });
    const data = await readResponse(response);
    if (!response.ok || !data || typeof data !== "object" || !("access_token" in data)) {
      throw new ApiClientError("Session refresh failed.", response.status, data);
    }
    const token = String(data.access_token);
    if (isPlatform) storePlatformToken(token); else storeAccessToken(token);
    return token;
  })();
  if (isPlatform) platformRefreshPromise = promise; else tenantRefreshPromise = promise;
  try { return await promise; }
  finally {
    if (isPlatform) platformRefreshPromise = null; else tenantRefreshPromise = null;
  }
}

/** Renew the tenant access token now (used by the session guard for active users). */
export function refreshSession(): Promise<string> {
  return refreshAccessToken(false);
}

function redirectForInvalidSession(path: string, response: Response, sentToken: boolean): Promise<never> | null {
  if (response.status !== 401 || !sentToken || typeof window === "undefined" || path.includes("/login") || sessionRedirectInProgress) return null;
  sessionRedirectInProgress = true;
  const isPlatform = path.startsWith("/platform/");
  if (isPlatform) removeStoredPlatformToken();
  else removeStoredAccessToken();
  window.location.replace(isPlatform ? "/platform/login?session=expired" : "/login?session=expired");
  return new Promise<never>(() => undefined);
}

export async function apiClient<TResponse>(
  path: string,
  options: ApiClientOptions = {},
): Promise<TResponse> {
  const isPlatform = path.startsWith("/platform/");
  const token = options.token !== undefined ? options.token : isPlatform ? getStoredPlatformToken() : getStoredAccessToken();
  const headers = new Headers(options.headers);

  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(buildUrl(path), {
    method: options.method ?? "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    cache: "no-store",
    credentials: "include",
  });

  const data = await readResponse(response);

  if (!response.ok) {
    const canRefresh = response.status === 401 && Boolean(token) && !options.skipRefresh && !path.endsWith("/login") && !path.endsWith("/refresh") && !path.endsWith("/logout");
    if (canRefresh) {
      try {
        const refreshedToken = await refreshAccessToken(isPlatform);
        return apiClient<TResponse>(path, { ...options, token: refreshedToken, skipRefresh: true });
      } catch {
        // Continue into the centralized cleanup and redirect below.
      }
    }
    const redirect = redirectForOrganizationStatus(path, response, data, Boolean(token));
    if (redirect) {
      return redirect;
    }
    const accountRedirect = redirectForAccountStatus(path, response, data, Boolean(token));
    if (accountRedirect) return accountRedirect;
    const sessionRedirect = redirectForInvalidSession(path, response, Boolean(token));
    if (sessionRedirect) return sessionRedirect;
    const detail =
      data && typeof data === "object" && "detail" in data ? extractDetailMessage(data.detail) : null;
    const message =
      data && typeof data === "object" && "message" in data ? String(data.message) : null;
    throw new ApiClientError(detail ?? message ?? "Request failed.", response.status, data);
  }

  // A previous expired-session redirect must not leak into a newly
  // authenticated session and suppress later session handling.
  sessionRedirectInProgress = false;
  return data as TResponse;
}
