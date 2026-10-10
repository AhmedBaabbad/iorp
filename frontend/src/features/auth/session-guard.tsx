"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { refreshSession, isSessionRejected } from "@/lib/api-client";
import { ACCESS_TOKEN_KEY, getStoredAccessToken, removeStoredAccessToken } from "@/lib/auth";
import { IDLE_TIMEOUT_MS, markActivity, nextSessionAction, readLastActivity, tokenExpiry } from "@/lib/session-policy";
import { logoutSession } from "./auth-client";

const ACTIVITY_EVENTS = ["pointerdown", "pointermove", "keydown", "wheel", "touchstart", "scroll"] as const;
const WRITE_THROTTLE_MS = 5_000;

const goTo = (url: string) => window.location.replace(url);

/**
 * Ends the session without waiting for a click: after inactivity (with a one-minute
 * countdown), when the session cannot be renewed, or when another tab signs out.
 */
export function SessionGuard({ onSignedOut, redirect = goTo }: { onSignedOut?: () => void; redirect?: (url: string) => void }) {
  const t = useTranslations("auth.session");
  const lastActivity = useRef(Date.now());
  const lastWrite = useRef(0);
  const refreshing = useRef(false);
  const nextRefreshAt = useRef(0);
  const ended = useRef(false);
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);

  const end = useCallback((reason: "idle" | "expired") => {
    if (ended.current) return;
    ended.current = true;
    // Revoke the server session too, so the refresh cookie cannot silently sign back in.
    void logoutSession().catch(() => undefined);
    removeStoredAccessToken();
    onSignedOut?.();
    redirect(`/login?session=${reason}`);
  }, [onSignedOut, redirect]);

  const touch = useCallback((force = false) => {
    const now = Date.now();
    lastActivity.current = now;
    if (force || now - lastWrite.current >= WRITE_THROTTLE_MS) {
      lastWrite.current = now;
      markActivity(now);
    }
  }, []);

  const check = useCallback(() => {
    if (ended.current) return;
    const now = Date.now();
    const last = Math.max(lastActivity.current, readLastActivity() ?? 0);
    const action = nextSessionAction(now, last, tokenExpiry(getStoredAccessToken()));
    if (action.type === "logout") return end("idle");
    setSecondsLeft(action.type === "warn" ? action.secondsLeft : null);
    if (action.type === "refresh" && !refreshing.current && now >= nextRefreshAt.current) {
      refreshing.current = true;
      refreshSession().catch(error => {
        if (isSessionRejected(error)) end("expired");
        else nextRefreshAt.current = Date.now() + 15_000;
      }).finally(() => { refreshing.current = false; });
    }
  }, [end]);

  useEffect(() => {
    // Reopening the app after the idle limit (closed tab, sleeping laptop) still signs out.
    const recorded = readLastActivity();
    if (recorded !== null && Date.now() - recorded >= IDLE_TIMEOUT_MS) end("idle");
    else touch(true);
    const onActivity = () => touch();
    ACTIVITY_EVENTS.forEach((name) => window.addEventListener(name, onActivity, { passive: true, capture: true }));
    // Browsers slow timers in background tabs; re-check the moment the page is seen again.
    const onVisible = () => { if (document.visibilityState === "visible") check(); };
    document.addEventListener("visibilitychange", onVisible);
    // Signing out (or the session ending) in another tab signs this one out immediately.
    const onStorage = (event: StorageEvent) => {
      if (event.key === ACCESS_TOKEN_KEY && event.newValue === null && !ended.current) {
        ended.current = true;
        onSignedOut?.();
        redirect("/login?session=expired");
      }
    };
    window.addEventListener("storage", onStorage);
    const timer = window.setInterval(check, 1_000);
    return () => {
      ACTIVITY_EVENTS.forEach((name) => window.removeEventListener(name, onActivity, { capture: true }));
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("storage", onStorage);
      window.clearInterval(timer);
    };
  }, [check, end, onSignedOut, redirect, touch]);

  if (secondsLeft === null) return null;
  return (
    <div className="iorp-session-overlay">
      <div role="alertdialog" aria-modal="true" aria-labelledby="session-warning-title" aria-describedby="session-warning-text" className="iorp-session-dialog">
        <h2 id="session-warning-title">{t("warningTitle")}</h2>
        <p id="session-warning-text">{t("warningText", { seconds: secondsLeft, minutes: Math.round(IDLE_TIMEOUT_MS / 60_000) })}</p>
        <p className="iorp-session-countdown" aria-live="polite">{secondsLeft}</p>
        <div className="iorp-session-actions">
          <button type="button" className="iorp-session-secondary" onClick={() => end("idle")}>{t("signOutNow")}</button>
          <button type="button" className="iorp-session-primary" autoFocus onClick={() => { touch(true); setSecondsLeft(null); }}>{t("staySignedIn")}</button>
        </div>
      </div>
    </div>
  );
}
