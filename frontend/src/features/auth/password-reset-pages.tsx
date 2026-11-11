"use client";
import { PasswordRequirements, PASSWORD_MIN_LENGTH, passwordIsValid, usePasswordErrorMessage } from "@/components/forms/PasswordRequirements";


import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { type FormEvent, useState } from "react";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { PasswordInput } from "@/components/PasswordInput";
import { apiClient, ApiClientError } from "@/lib/api-client";
import css from "./password-reset-pages.module.css";

export function ForgotPasswordPage({ platform = false }: { platform?: boolean }) {
  const t = useTranslations("passwordReset.forgot"); const locale = useLocale(); const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState(""); const [busy, setBusy] = useState(false); const [done, setDone] = useState(false);
  const login = platform ? "/platform/login" : "/login";
  async function submit(event: FormEvent) { event.preventDefault(); setError(null); setBusy(true); try { await apiClient(platform ? "/platform/auth/forgot-password" : "/auth/forgot-password", { method: "POST", body: { email, locale }, token: null, skipRefresh: true }); setDone(true); } catch (caught) { setError(t(caught instanceof ApiClientError && caught.status === 429 ? "rateLimit" : "sendError")); } finally { setBusy(false); } }
  return <main className={css.page}><section className={css.card}><LanguageSwitcher label={t("language")} /><div className={css.logo}>IORP</div>{done ? <div className={css.state}><span>✓</span><h1>{t("checkEmail")}</h1><p>{t("checkEmailDetail")}</p><Link href={login}>{t("backToLogin")}</Link></div> : <><h1>{t(platform ? "platformTitle" : "title")}</h1><p>{t("subtitle")}</p><form onSubmit={submit}><label><span>{t("email")}</span><input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label><p role="alert" className={css.error}>{error}</p><button disabled={busy}>{t(busy ? "submitting" : "submit")}</button></form><Link className={css.back} href={login}>{t("backToLogin")}</Link></>}</section></main>;
}

export function ResetPasswordPage({ platform = false }: { platform?: boolean }) {
  const passwordError = usePasswordErrorMessage();
  const t = useTranslations("passwordReset.reset"); const params = useSearchParams(); const token = params.get("token");
  const invite = params.get("invite") === "1";  // SEC-003: a new account's activation link: the same form, its own words
  const [password, setPassword] = useState(""); const [confirmation, setConfirmation] = useState(""); const [busy, setBusy] = useState(false); const [status, setStatus] = useState<"form"|"success"|"invalid">(token ? "form" : "invalid"); const [error, setError] = useState<string | null>(token ? null : t("missingToken"));
  const login = platform ? "/platform/login" : "/login"; const forgot = platform ? "/platform/forgot-password" : "/forgot-password";
  async function submit(event: FormEvent) { event.preventDefault(); setError(null); if (password !== confirmation) { setError(t("mismatch")); return; } if (!passwordIsValid(password, confirmation)) { setError(t("weak")); return; } setBusy(true); try { await apiClient(platform ? "/platform/auth/reset-password" : "/auth/reset-password", { method: "POST", body: { token, new_password: password, new_password_confirmation: confirmation }, token: null, skipRefresh: true }); setStatus("success"); } catch (caught) { const details = caught instanceof ApiClientError && caught.details && typeof caught.details === "object" ? caught.details as { code?: string } : null; if (details?.code === "PASSWORD_TOO_WEAK") setError(t("weak")); else if (details?.code === "INVALID_RESET_TOKEN" || details?.code === "RESET_TOKEN_EXPIRED") { setStatus("invalid"); setError(t("invalidToken")); } else { setError(passwordError(caught, t(caught instanceof ApiClientError && caught.status === 429 ? "rateLimit" : "requestError"))); } } finally { setBusy(false); } }
  return <main className={css.page}><section className={css.card}><LanguageSwitcher label={t("language")} /><div className={css.logo}>IORP</div>{status === "success" ? <div className={css.state}><span>✓</span><h1>{t(invite ? "activated" : "success")}</h1><Link href={login}>{t("login")}</Link></div> : status === "invalid" ? <div className={css.state}><span>×</span><h1>{t(invite ? "invalidInvite" : "invalidToken")}</h1>{error ? <p>{error}</p> : null}<Link href={forgot}>{t("requestNew")}</Link></div> : <><h1>{invite ? t("activateTitle") : t(platform ? "platformTitle" : "title")}</h1><p>{t(invite ? "activateSubtitle" : "subtitle")}</p><form onSubmit={submit}><label><span>{t("newPassword")}</span><PasswordInput autoComplete="new-password" minLength={PASSWORD_MIN_LENGTH} value={password} onChange={(e) => setPassword(e.target.value)} required /></label><label><span>{t("confirmation")}</span><PasswordInput autoComplete="new-password" minLength={PASSWORD_MIN_LENGTH} value={confirmation} onChange={(e) => setConfirmation(e.target.value)} required /></label><PasswordRequirements password={password} confirmation={confirmation} />{error ? <p className={css.error}>{error}</p> : null}<button disabled={busy || !passwordIsValid(password, confirmation)}>{t(busy ? "submitting" : "submit")}</button></form></>}</section></main>;
}
