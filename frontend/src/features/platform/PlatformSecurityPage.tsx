"use client";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { apiClient } from "@/lib/api-client";
import { usePlatformAuth } from "./platform-auth-context";
import { PlatformProtectedRoute } from "./platform-protected-route";
import { requestStepUp } from "./platform-step-up";

export function PlatformSecurityPage() {
  const t = useTranslations("platform.security");
  const { token, logout } = usePlatformAuth();
  const [enabled, setEnabled] = useState(false);
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [secret, setSecret] = useState("");
  const [codes, setCodes] = useState<string[]>([]);
  const [saved, setSaved] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (token) void apiClient<{ enabled: boolean }>("/platform/mfa", { token }).then(r => setEnabled(r.enabled)).catch(() => setError(true)); }, [token]);
  const run = async (action: () => Promise<void>) => { setError(false); setBusy(true); try { await action(); } catch { setError(true); } finally { setBusy(false); } };
  return <PlatformProtectedRoute><main style={{ maxWidth: 760, margin: "32px auto", padding: 24, color: "var(--text)", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 16 }}>
    <h1>{t("title")}</h1><p>{t("timeout")}</p>
    {error && <p role="alert">{t("failed")}</p>}
    {!enabled && !secret && !done && <form onSubmit={e => { e.preventDefault(); void run(async () => {
      const r = await apiClient<{ secret: string; recovery_codes: string[] }>("/platform/mfa/enroll", { method: "POST", token, body: { password }, notify: false });
      setSecret(r.secret); setCodes(r.recovery_codes); setPassword("");
    }); }}><label>{t("password")}<input required type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} /></label><button disabled={busy}>{t("enroll")}</button></form>}
    {secret && <><p>{t("secretHint")}</p><code dir="ltr" style={{ overflowWrap: "anywhere" }}>{secret}</code></>}
    {!!codes.length && <><h2>{t("recovery")}</h2><p>{t("saveHint")}</p><ul dir="ltr">{codes.map(c => <li key={c}><code>{c}</code></li>)}</ul><label><input type="checkbox" checked={saved} onChange={e => setSaved(e.target.checked)} />{t("saved")}</label></>}
    {secret && <form onSubmit={e => { e.preventDefault(); void run(async () => {
      await apiClient("/platform/mfa/confirm", { method: "POST", token, body: { code, saved_recovery_codes: saved }, notify: false });
      setSecret(""); setCodes([]); setCode(""); setDone(true);
    }); }}><label>{t("code")}<input required autoComplete="one-time-code" dir="ltr" value={code} onChange={e => setCode(e.target.value)} /></label><button disabled={!saved || busy}>{t("verify")}</button></form>}
    {enabled && !done && <div style={{ display: "flex", gap: 16 }}>
      {(["recovery", "disable"] as const).map(action => <button key={action} disabled={busy} onClick={() => void run(async () => {
        const path = `/platform/mfa/${action}`;
        const proof = await requestStepUp({ method: "POST", path, token });
        const r = await apiClient<{ recovery_codes?: string[] }>(path, { method: "POST", token, headers: { "X-Platform-Step-Up": proof }, notify: false });
        setCodes(r.recovery_codes ?? []); setSaved(false); setDone(true);
      })}>{t(action)}</button>)}
    </div>}
    {done && <><p role="status">{t("loginAgain")}</p><button disabled={codes.length > 0 && !saved} onClick={() => { setCodes([]); logout(); window.location.assign("/platform/login"); }}>{t("login")}</button></>}
  </main></PlatformProtectedRoute>;
}
