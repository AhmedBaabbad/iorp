import { lifecycleErrorCode } from "@/features/production-demands/planning-lifecycle";

type Translate = { (key: string, values?: Record<string, string>): string; has: (key: string) => boolean };

// Server codes become messages under procurement.errors; detail values (e.g. "line") fill the placeholders.
export function procurementErrorMessage(error: unknown, t: Translate) {
  const code = lifecycleErrorCode(error);
  const detail = (error as { details?: { detail?: Record<string, unknown> } } | null)?.details?.detail ?? {};
  const values = Object.fromEntries(Object.entries(detail).filter(([, v]) => ["string", "number"].includes(typeof v)).map(([k, v]) => [k, String(v)]));
  return t.has(code) ? t(code, values) : t("request_failed");
}

export const DECIMAL = /^\d+(\.\d{1,3})?$/;

export function todayIso(now = new Date()) {
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}
