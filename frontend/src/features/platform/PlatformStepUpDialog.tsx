"use client";
import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { apiClient } from "@/lib/api-client";
import type { Pending } from "./platform-step-up";

export function PlatformStepUpDialog() {
  const t = useTranslations("platform.security");
  const [pending, setPending] = useState<Pending | null>(null);
  const current = useRef<Pending | null>(null);
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  useEffect(() => {
    const receive = (event: Event) => {
      const next = (event as CustomEvent<Pending>).detail;
      if (current.current) { next.reject(new Error("Verification already pending")); return; }
      current.current = next; setPending(next); setError(false);
    };
    window.addEventListener("iorp-platform-step-up", receive);
    return () => { window.removeEventListener("iorp-platform-step-up", receive); current.current?.reject(new Error("Verification cancelled")); };
  }, []);
  const close = () => { setPending(null); current.current = null; setPassword(""); setCode(""); };
  if (!pending) return null;
  return <div role="dialog" aria-modal="true" aria-labelledby="step-title" style={{ position: "fixed", inset: 0, zIndex: 10000, background: "var(--overlay)", display: "flex", alignItems: "flex-start", justifyContent: "center", padding: 16, overflowY: "auto", overscrollBehavior: "contain" }}>
    <form style={{ margin: "auto", flexShrink: 0, maxHeight: "calc(100dvh - 32px)", overflowY: "auto", background: "var(--surface)", color: "var(--text)", padding: 24, borderRadius: 12, display: "grid", gap: 16, maxWidth: 480 }} onSubmit={async e => {
      e.preventDefault(); setBusy(true); setError(false);
      try {
        const response = await apiClient<{ authorization: string }>("/platform/mfa/step-up", { method: "POST", token: pending.action.token, notify: false,
          body: { password, code, method: pending.action.method, path: pending.action.path, body: pending.action.body ?? null } });
        pending.resolve(response.authorization); close();
      } catch { setError(true); } finally { setBusy(false); }
    }}>
      <h2 id="step-title">{t("verifyTitle")}</h2><p>{t("verifyHint")}</p><code dir="ltr">{pending.action.path}</code>
      <label>{t("password")}<input autoFocus type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required /></label>
      <label>{t("code")}<input dir="ltr" autoComplete="one-time-code" value={code} onChange={e => setCode(e.target.value)} /></label>
      {error && <p role="alert">{t("failed")}</p>}<button disabled={busy} type="submit">{t("verify")}</button>
      <button disabled={busy} type="button" onClick={() => { pending.reject(new Error(t("cancelled"))); close(); }}>{t("cancel")}</button>
    </form>
  </div>;
}
