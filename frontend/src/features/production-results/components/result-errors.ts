import { lifecycleErrorCode } from "@/features/production-demands/planning-lifecycle";

type Translate = { (key: string, values?: Record<string, string>): string; has: (key: string) => boolean };

// Server codes become messages under production.results.errors, with the server's figures filled in.
export function resultErrorMessage(error: unknown, t: Translate) {
  const code = lifecycleErrorCode(error);
  const detail = ((error as { details?: { detail?: Record<string, unknown> } } | null)?.details?.detail ?? {}) as Record<string, unknown>;
  const values = Object.fromEntries(Object.entries(detail).filter(([, v]) => typeof v === "string" || typeof v === "number").map(([k, v]) => [k, String(v)]));
  return t.has(`errors.${code}`) ? t(`errors.${code}`, values) : t("errors.request_failed");
}
