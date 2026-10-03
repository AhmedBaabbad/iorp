import { lifecycleErrorCode } from "@/features/production-demands/planning-lifecycle";

type Translate = { (key: string, values?: Record<string, string>): string; has: (key: string) => boolean };

// Server codes become messages under production.wasteRecords.errors.
export function wasteErrorMessage(error: unknown, t: Translate) {
  const code = lifecycleErrorCode(error);
  return t.has(`errors.${code}`) ? t(`errors.${code}`) : t("errors.request_failed");
}
