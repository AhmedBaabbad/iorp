import { lifecycleErrorCode } from "@/features/production-demands/planning-lifecycle";

type Translate = { (key: string, values?: Record<string, string>): string; has: (key: string) => boolean };

// Server codes become messages under shipping.errors; detail values (e.g. "fields") fill the placeholders.
export function shippingErrorMessage(error: unknown, t: Translate, field?: (name: string) => string) {
  const code = lifecycleErrorCode(error);
  const detail = (error as { details?: { detail?: Record<string, unknown> } } | null)?.details?.detail ?? {};
  const values = Object.fromEntries(Object.entries(detail).filter(([, v]) => ["string", "number"].includes(typeof v)).map(([k, v]) => [k, String(v)]));
  if (values.fields && field) values.fields = values.fields.split(",").map(field).join("، ");
  return t.has(code) ? t(code, values) : t("request_failed");
}

// Today in the user's own calendar, for date inputs.
export function todayIso(now = new Date()) {
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

export const DECIMAL = /^\d+(\.\d{1,3})?$/;
