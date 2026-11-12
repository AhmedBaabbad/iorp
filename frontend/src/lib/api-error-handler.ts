import { ApiClientError } from "./api-client";

type ApiError = {
  status?: number;
  error_code?: string;
  detail?: string;
};

export function getApiErrorMessage(error: unknown, t: (key: string) => string): string {
  const apiError = normalizeApiError(error);

  if (apiError.error_code) {
    const mapped = mapErrorCode(apiError.error_code, t);
    if (mapped) {
      return mapped;
    }
  }

  if (apiError.status) {
    if ((apiError.status === 400 || apiError.status === 409) && apiError.detail) {
      return apiError.detail;
    }
    return mapHttpStatus(apiError.status, t);
  }

  return t("error.unexpected");
}

function normalizeApiError(error: unknown): ApiError {
  if (error instanceof ApiClientError) {
    const details = error.details;
    const errorCode = readErrorCode(details);

    return {
      status: error.status,
      error_code: errorCode,
      detail: error.message,
    };
  }

  if (error && typeof error === "object") {
    return error as ApiError;
  }

  return {};
}

export function apiErrorCode(error: unknown): string | undefined {
  return readErrorCode(error instanceof ApiClientError ? error.details : error);
}

function readErrorCode(details: unknown): string | undefined {
  if (!details || typeof details !== "object") {
    return undefined;
  }

  if (Array.isArray(details)) {
    for (const entry of details) {
      const code = readErrorCode(entry);
      if (code) return code;
    }
    return undefined;
  }
  const record = details as { error_code?: unknown; code?: unknown; detail?: unknown; type?: unknown };
  const value = record.error_code ?? record.code;
  if (typeof value === "string") return value;
  const codes = ["CITY_OTHER_REQUIRED", "CITY_COUNTRY_MISMATCH", "LOCATION_URL_INVALID", "CONTACT_NAME_REQUIRED"];
  if (typeof record.type === "string" && codes.includes(record.type)) return record.type;
  if (typeof record.detail === "string" && codes.includes(record.detail)) return record.detail;
  return readErrorCode(record.detail);
}

function mapErrorCode(code: string, t: (key: string) => string): string | null {
  const map: Record<string, string> = {
    CITY_OTHER_REQUIRED: t("validation.cityOtherRequired"),
    CITY_COUNTRY_MISMATCH: t("validation.cityCountryMismatch"),
    LOCATION_URL_INVALID: t("validation.locationUrlInvalid"),
    CONTACT_NAME_REQUIRED: t("validation.contactNameRequired"),
    NOT_FOUND: t("error.notFound"),
    FORBIDDEN: t("error.forbidden"),
    CONFLICT: t("error.conflict"),
    VALIDATION_ERROR: t("error.validationFailed"),
    SESSION_EXPIRED: t("error.sessionExpired"),
  };

  return map[code] ?? null;
}

function mapHttpStatus(status: number, t: (key: string) => string): string {
  if (status === 404) return t("error.notFound");
  if (status === 403) return t("error.forbidden");
  if (status === 409) return t("error.conflict");
  if (status === 422) return t("error.validationFailed");
  if (status === 401) return t("error.sessionExpired");
  if (status >= 500) return t("error.unexpected");
  return t("error.tryAgain");
}
