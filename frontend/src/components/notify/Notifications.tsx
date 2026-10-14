"use client";
/**
 * One way to tell the user what happened (PROJECT-UX-NOTIFY): a short message at the top of the screen after every
 * save, change, sending or decision — green when it worked, red when it did not — in the screen's language.
 *
 * The API client announces every successful change by itself (lib/notify-store: "Approved.", "Changes saved.", …). A
 * screen with something more precise to say replaces that message:
 *
 *   const notify = useNotify();
 *   notify.done("delegationRequested");   // a standard message (common.notify.*)
 *   notify.success(t("requestSent"));     // a message of the screen's own
 *   notify.error(message);
 *
 * <Notifications /> is placed once in the root layout; a message outlives the screen that sent it (it shows after
 * navigating to the next page).
 */
import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import { dismiss, pushAction, pushNote, subscribe, type Note, type NoteKind } from "@/lib/notify-store";

export { dismiss, pushNote };

export function useNotify() {
  return useMemo(() => ({
    /** A done action by its name (save, create, approve, send, …): its standard message. */
    done: (action: string) => pushAction(action),
    success: (text: string) => pushNote("success", text),
    info: (text: string) => pushNote("info", text),
    error: (text: string) => pushNote("error", text),
  }), []);
}

const TONE: Record<NoteKind, { border: string; icon: string }> = {
  success: { border: "var(--success)", icon: "✓" },
  info: { border: "var(--accent-strong)", icon: "i" },
  error: { border: "var(--danger)", icon: "!" },
};

/** The messages, stacked at the top of the screen (once, in the root layout). */
export function Notifications() {
  const t = useTranslations("common.notify");
  const [shown, setShown] = useState<Note[]>([]);
  useEffect(() => subscribe(setShown), []);
  if (!shown.length) return null;
  const text = (n: Note) => n.text ?? (n.action && t.has(n.action) ? t(n.action) : t("done"));
  return <div aria-live="polite" style={{ position: "fixed", insetInline: 0, top: "calc(env(safe-area-inset-top, 0px) + 16px)", zIndex: 1000,
    display: "grid", justifyItems: "center", gap: 8, pointerEvents: "none", padding: "0 16px" }}>
    {shown.map((n) => <div key={n.id} role={n.kind === "error" ? "alert" : "status"} style={{ pointerEvents: "auto", display: "flex", gap: 12,
      alignItems: "center", maxWidth: 520, width: "100%", background: "var(--surface)", color: "var(--text)", border: "1px solid var(--border-strong)",
      borderInlineStart: `5px solid ${TONE[n.kind].border}`, borderRadius: 10, padding: "12px 14px", boxShadow: "var(--shadow-lg, 0 12px 32px rgba(0, 0, 0, 0.16))" }}>
      <span aria-hidden="true" style={{ display: "inline-grid", placeItems: "center", width: 24, height: 24, borderRadius: "50%", flex: "none",
        background: TONE[n.kind].border, color: "var(--on-accent)", fontWeight: 700, fontSize: 14 }}>{TONE[n.kind].icon}</span>
      <span style={{ flex: 1, lineHeight: 1.5 }}>{text(n)}</span>
      <button type="button" onClick={() => dismiss(n.id)} aria-label={t("dismiss")}
        style={{ border: 0, background: "transparent", color: "var(--text-muted)", fontSize: 18, cursor: "pointer", lineHeight: 1 }}>×</button>
    </div>)}
  </div>;
}
