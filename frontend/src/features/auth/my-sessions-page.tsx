"use client";
/**
 * My sessions (SEC-001): where I am signed in — device, address, since when, last activity — with this device marked.
 * I end any other one, or all of them but this one (a lost phone, a shared computer). Every signed-in user sees their
 * own, nobody else's; an administrator ends a user's sessions from the user's page.
 */
import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { useTranslations } from "next-intl";

import { PageFrame } from "@/components/layout/page-frame";
import { useNotify } from "@/components/notify/Notifications";
import { useFormatter } from "@/hooks/useFormatter";
import { apiClient } from "@/lib/api-client";
import { sharedStyles } from "@/styles/shared-styles";

type MySession = { id: string; device: string; ip_address: string | null; started_at: string; last_active_at: string; current: boolean };
const CARD: CSSProperties = { background: "var(--surface)", border: "1px solid var(--border-strong)", borderRadius: 12, padding: 18 };

export function MySessionsPage() {
  const t = useTranslations("auth.sessions");
  const notify = useNotify();
  const fmt = useFormatter();
  const [sessions, setSessions] = useState<MySession[] | null>(null);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => {
    apiClient<MySession[]>("/auth/sessions").then(s => { setSessions(s); setError(false); }).catch(() => setError(true));
  }, []);
  useEffect(load, [load]);

  async function end(body: { session_ids?: string[]; all_others?: boolean }) {
    setBusy(true);
    try {
      const done = await apiClient<{ ended: number }>("/auth/sessions/end", { method: "POST", body, notify: false });
      notify.success(t("ended", { count: done.ended }));
      load();
    } catch { notify.error(t("error")); } finally { setBusy(false); }
  }

  const others = (sessions ?? []).filter(s => !s.current);
  return <PageFrame title={t("title")} subtitle={t("subtitle")}
    action={others.length > 0 ? <button type="button" style={sharedStyles.secondaryButton} disabled={busy}
      onClick={() => { if (window.confirm(t("confirmOthers"))) void end({ all_others: true }); }}>{t("endOthers")}</button> : undefined}>
    {error ? <div role="alert" style={sharedStyles.error}>{t("error")}</div> : !sessions ? <p>{t("loading")}</p> :
      <div style={{ display: "grid", gap: 12 }}>
        {sessions.map(s => <section key={s.id} style={{ ...CARD, display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center",
          borderColor: s.current ? "var(--accent)" : "var(--border-strong)" }}>
          <div style={{ flex: "1 1 260px" }}>
            <strong style={{ fontSize: 16 }}>{s.device}</strong>
            {s.current && <span style={{ ...sharedStyles.badge, marginInlineStart: 8, background: "var(--accent-soft)", color: "var(--accent-strong)" }}>{t("thisDevice")}</span>}
            <div style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 4 }}>
              {t("address")}: <bdi dir="ltr">{s.ip_address ?? "—"}</bdi> · {t("since", { date: fmt.dateTime(s.started_at) })} · {t("lastActive", { date: fmt.dateTime(s.last_active_at) })}
            </div>
          </div>
          {!s.current && <button type="button" style={sharedStyles.secondaryButton} disabled={busy} onClick={() => void end({ session_ids: [s.id] })}>{t("end")}</button>}
        </section>)}
        <p style={{ color: "var(--text-muted)", fontSize: 13 }}>{t("hint")}</p>
      </div>}
  </PageFrame>;
}
