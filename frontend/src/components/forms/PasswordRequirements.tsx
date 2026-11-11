"use client";

import { useTranslations } from "next-intl";
import { ApiClientError } from "@/lib/api-client";

export const PASSWORD_MIN_LENGTH = 8;
export function passwordChecks(password: string, confirmation?: string, email?: string) {
  return {
    PASSWORD_TOO_SHORT: [...password].length >= PASSWORD_MIN_LENGTH,
    PASSWORD_NEEDS_UPPER: /\p{Lu}/u.test(password),
    PASSWORD_NEEDS_LOWER: /\p{Ll}/u.test(password),
    PASSWORD_NEEDS_DIGIT: /\p{N}/u.test(password),
    PASSWORD_NEEDS_SYMBOL: /[^\p{L}\p{N}\s]/u.test(password),
    ...(confirmation === undefined ? {} : { PASSWORD_MISMATCH: Boolean(password) && password === confirmation }),
    ...(email ? { PASSWORD_EQUALS_EMAIL: password.toLocaleLowerCase() !== email.toLocaleLowerCase() } : {}),
  };
}
export function passwordIsValid(password: string, confirmation?: string, email?: string) {
  return Object.values(passwordChecks(password, confirmation, email)).every(Boolean);
}
export function usePasswordErrorMessage() {
  const t = useTranslations("passwordReset.policy");
  return (error: unknown, fallback: string) => {
    if (!(error instanceof ApiClientError)) return fallback;
    const body = error.details as { code?: string; detail?: { code?: string } | { type?: string }[] } | undefined;
    const code = body?.code ?? (Array.isArray(body?.detail) ? body.detail[0]?.type : body?.detail?.code) ?? error.message;
    return t.has(code) ? t(code) : fallback;
  };
}

export function PasswordRequirements({ password, confirmation, email }: { password: string; confirmation?: string; email?: string }) {
  const t = useTranslations("passwordReset.policy");
  return <ul aria-live="polite" aria-atomic="true" aria-label={t("title")} style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "var(--field-gap)", fontSize: "var(--label-size)", fontWeight: 400 }}>
    {Object.entries(passwordChecks(password, confirmation, email)).map(([code, met]) => <li key={code} data-met={met} style={{ color: met ? "var(--success)" : "var(--text-muted)" }}>
      <span aria-hidden="true">{met ? "✓" : "•"}</span>{" "}{t(`checks.${code}`)}
    </li>)}
  </ul>;
}
