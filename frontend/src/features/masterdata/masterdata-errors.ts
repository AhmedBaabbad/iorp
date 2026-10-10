import { lifecycleErrorCode } from "@/features/production-demands/planning-lifecycle";

type Translate = { (key: string, values?: Record<string, string>): string; has: (key: string) => boolean };

// Server codes become messages under masterdata.errors; detail values (e.g. "key") fill the placeholders.
export function masterdataErrorMessage(error: unknown, t: Translate) {
  const code = lifecycleErrorCode(error);
  const detail = (error as { details?: { detail?: Record<string, unknown> } } | null)?.details?.detail ?? {};
  const values = Object.fromEntries(Object.entries(detail).filter(([, v]) => ["string", "number"].includes(typeof v)).map(([k, v]) => [k, String(v)]));
  return t.has(code) ? t(code, values) : t("request_failed");
}
