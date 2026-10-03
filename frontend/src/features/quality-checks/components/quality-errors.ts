import { lifecycleErrorCode } from "@/features/production-demands/planning-lifecycle";

type Translate = { (key: string, values?: Record<string, string>): string; has: (key: string) => boolean };

// Server codes become messages under quality.errors; detail values (e.g. "available") fill the placeholders.
export function qualityErrorMessage(error: unknown, t: Translate) {
  const code = lifecycleErrorCode(error);
  const detail = (error as { details?: { detail?: Record<string, unknown> } } | null)?.details?.detail ?? {};
  const values = Object.fromEntries(Object.entries(detail).filter(([, v]) => ["string", "number"].includes(typeof v)).map(([k, v]) => [k, String(v)]));
  return t.has(code) ? t(code, values) : t("request_failed");
}

// "2026-10-03T08:30" for a datetime-local input, in the user's own clock.
export function localDateTime(value?: string | null) {
  const date = value ? new Date(value) : new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export const QUANTITY = /^\d+(\.\d{1,3})?$/;

// Today in the user's own calendar, for date inputs.
export const todayIso = () => localDateTime().slice(0, 10);
