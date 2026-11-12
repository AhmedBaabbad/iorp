"use client";

import Link from "next/link";
import { UserPresence } from "./UserPresence";
import { PermanentUserDelete } from "./PermanentUserDelete";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth";
import { useFormatter } from "@/hooks/useFormatter";
import { useEnumLabel } from "@/i18n/enum-helpers";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import { activateAdminUser, listAdminUsers, lockAdminUser, unlockAdminUser } from "../api/admin-users-api";
import type { AdminUserListItem } from "../types";

const styles: Record<string, CSSProperties> = {
  panel: { background: "var(--surface)", border: "1px solid var(--border-strong)", borderRadius: "8px" },
  tableWrap: { overflowX: "auto" },
  table: { width: "100%", borderCollapse: "collapse" },
  th: { borderBottom: "1px solid var(--border)", color: "var(--text-muted)", fontSize: "13px", padding: "14px 16px", textAlign: "start" },
  td: { borderBottom: "1px solid var(--border)", padding: "14px 16px" },
  actions: { display: "flex", flexWrap: "wrap", gap: "8px" },
  badge: { background: "var(--accent-soft)", border: "1px solid color-mix(in srgb, var(--accent) 35%, var(--surface))", borderRadius: "999px", color: "var(--accent-strong)", fontSize: "12px", padding: "2px 8px" },
  rootBadge: { background: "var(--accent-soft)", border: "1px solid color-mix(in srgb, var(--accent) 35%, var(--surface))", borderRadius: "999px", color: "var(--accent-strong)", display: "inline-block", fontSize: "12px", fontWeight: 700, marginInlineStart: "8px", padding: "2px 8px" },
  deleteButton: { ...sharedStyles.secondaryButton, borderColor: "color-mix(in srgb, var(--danger) 35%, var(--surface))", color: "var(--danger)", minHeight: "34px", padding: "6px 12px", fontSize: "13px" },
  backdrop: {
    position: "fixed",
    inset: 0,
    background: "var(--overlay)",
    backdropFilter: "blur(2px)",
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "center",
    zIndex: 1000,
    overflowY: "auto", overscrollBehavior: "contain",
  },
  modal: {
    maxHeight: "calc(100dvh - 32px)", overflowY: "auto", margin: "auto", flexShrink: 0,
    background: "var(--surface)",
    borderRadius: "14px",
    boxShadow: "0 24px 64px rgba(15, 23, 42, 0.28), 0 4px 16px rgba(15, 23, 42, 0.12)",
    padding: "32px",
    maxWidth: "460px",
    width: "90%",
    display: "grid",
    gap: "20px",
  },
  modalIcon: {
    width: "48px",
    height: "48px",
    borderRadius: "50%",
    background: "var(--surface-muted)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "22px",
    margin: "0 auto",
  },
  modalTitle: { fontSize: "18px", fontWeight: 700, color: "var(--text)", margin: 0, textAlign: "center" as const },
  modalBody: { fontSize: "14px", color: "var(--text-muted)", margin: 0, lineHeight: "1.7", textAlign: "center" as const },
  modalWarning: { fontSize: "13px", fontWeight: 600, color: "var(--danger)", textAlign: "center" as const, margin: 0 },
  modalActions: { display: "flex", gap: "12px", justifyContent: "center", flexWrap: "wrap" as const },
  modalCancelButton: { ...sharedStyles.secondaryButton, minHeight: "40px", padding: "10px 24px", fontSize: "14px" },
  modalDeleteButton: {
    background: "var(--danger)",
    border: "none",
    borderRadius: "8px",
    color: "var(--on-accent)",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: 600,
    minHeight: "40px",
    padding: "10px 24px",
  },
  success: {
    background: "var(--success-soft)",
    border: "1px solid color-mix(in srgb, var(--success) 35%, var(--surface))",
    borderRadius: "6px",
    color: "var(--success)",
    fontSize: "14px",
    padding: "12px 14px",
  },
};

export function AdminUsersList() {
  const t = useTranslations("administration.users");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const enumLabel = useEnumLabel();
  const canWrite = usePermission("foundation:users:write");
  const canActivate = usePermission("foundation:users:activate");
  const canDeactivate = usePermission("foundation:users:deactivate");
  const canLock = usePermission("foundation:users:lock");
  const [showArchived, setShowArchived] = useState(false);
  const [users, setUsers] = useState<AdminUserListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  const loadUsers = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await listAdminUsers();
      if (isMountedRef.current) setUsers(response);
    } catch (caughtError) {
      if (isMountedRef.current) setError(getApiErrorMessage(caughtError, messages));
    } finally {
      if (isMountedRef.current) setIsLoading(false);
    }
  }, [messages]);

  async function runAction(action: () => Promise<unknown>) {
    setError(null);
    try { await action(); await loadUsers(); }
    catch (caughtError) { setError(getApiErrorMessage(caughtError, messages)); }
  }

  function handleDeleted(id: string) {
    setUsers(rows => rows.filter(row => row.id !== id));
    void listAdminUsers().then(rows => {
      if (isMountedRef.current) setUsers(rows);
    }).catch(caught => {
      if (isMountedRef.current) setError(getApiErrorMessage(caught, messages));
    });
  }

  function statusBadge(status: AdminUserListItem["status"]): CSSProperties {
    if (status === "active") return { ...styles.badge, background: "var(--success-soft)", borderColor: "var(--success)", color: "var(--success)" };
    if (status === "locked") return { ...styles.badge, background: "var(--danger-soft)", borderColor: "color-mix(in srgb, var(--danger) 35%, var(--surface))", color: "var(--danger)" };
    return { ...styles.badge, background: "var(--surface-muted)", borderColor: "var(--border-strong)", color: "var(--text-muted)" };
  }

  useEffect(() => {
    isMountedRef.current = true;
    void loadUsers();
    let timer: ReturnType<typeof setInterval> | undefined;
    const refresh = () => { void listAdminUsers().then(rows=>{if(isMountedRef.current)setUsers(rows);}).catch(()=>{}); };
    const visibility = () => {
      if(timer)clearInterval(timer);
      timer=undefined;
      if(!document.hidden){timer=setInterval(refresh,60000);}
    };
    visibility();
    const resume=()=>{visibility();if(!document.hidden)refresh();};
    document.addEventListener("visibilitychange",resume);
    return () => { isMountedRef.current = false;if(timer)clearInterval(timer);document.removeEventListener("visibilitychange",resume); };
  }, [loadUsers]);

  return (
    <PageFrame
      section={t("section")}
      title={t("listTitle")}
      subtitle={t("subtitle")}
      action={canWrite ? <Link href="/admin/users/new" style={sharedStyles.button}>{t("newButton")}</Link> : null}
    >
      <label><input type="checkbox" checked={showArchived} onChange={event => setShowArchived(event.target.checked)} />{t("accountPolicy.showArchived")}</label>
      {isLoading ? <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>{t("loading")}</div> : null}
      {!isLoading && error ? <div style={sharedStyles.error} role="alert">{error}</div> : null}
      {!isLoading && !error && users.length === 0 ? (
        <section style={{ ...sharedStyles.state, background: "var(--surface)" }}>{t("empty")}</section>
      ) : null}
      {!isLoading && !error && users.length > 0 ? (
        <section style={styles.panel}>
          <div style={styles.tableWrap}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>{t("fields.fullName")}</th>
                  <th style={styles.th}>{t("fields.email")}</th>
                  <th style={styles.th}>{t("fields.status")}</th>
                  <th style={styles.th}>{t("presence.title")}</th>
                  <th style={styles.th}>{t("fields.roles")}</th>
                  <th style={styles.th}>{t("fields.createdAt")}</th>
                  <th style={styles.th}>{t("fields.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {users.filter(user => showArchived || !user.archived_at).map((user) => (
                  <tr key={user.id}>
                    <td style={styles.td}>
                      <Link href={`/admin/users/${user.id}`}>{user.full_name}</Link>
                      {user.is_organization_root ? <span style={styles.rootBadge}>{t("rootBadge")}</span> : null}
                    </td>
                    <td style={styles.td}>{user.email}</td>
                    <td style={styles.td}><span style={statusBadge(user.status)}>{user.archived_at ? t("accountPolicy.archived") : enumLabel("user", "status", user.status)}</span>{user.activation_pending ? <span style={{ ...styles.badge, marginInlineStart: 6, background: "var(--warning-soft, var(--surface-muted))", color: "var(--warning, var(--text-muted))" }}>{t("invitation.pending")}</span> : null}</td>
                    <td style={styles.td}><UserPresence user={user}/></td>
                    <td style={styles.td}>{user.roles.length ? user.roles.map((role) => <span key={role.id} style={styles.badge}>{role.name}</span>) : t("notAvailable")}</td>
                    <td style={styles.td}>{fmt.date(user.created_at)}</td>
                    <td style={styles.td}>
                      <div style={styles.actions}>
                        <Link href={`/admin/users/${user.id}`} style={sharedStyles.secondaryButton}>{common("actions.view")}</Link>
                        <PermanentUserDelete user={user} onDeleted={()=>handleDeleted(user.id)} onDeactivate={canDeactivate?()=>{window.location.assign(`/admin/users/${user.id}?deactivate=1`);}:undefined}/>
                        {!user.is_organization_root && user.status === "active" && canLock ? <button style={sharedStyles.secondaryButton} onClick={() => void runAction(async () => { const reason = window.prompt(t("accountPolicy.reason")); if (reason && reason.trim().length >= 3) await lockAdminUser(user.id, reason); })}>{t("actions.lock")}</button> : null}
                        {!user.is_organization_root && user.status === "locked" && canLock ? <button style={sharedStyles.secondaryButton} onClick={() => void runAction(async () => { const reason = window.prompt(t("accountPolicy.reason")); if (reason && reason.trim().length >= 3) await unlockAdminUser(user.id, reason); })}>{t("actions.unlock")}</button> : null}
                        {!user.is_organization_root && user.status !== "inactive" && canDeactivate ? <Link style={styles.deleteButton} href={`/admin/users/${user.id}`}>{t("actions.deactivate")}</Link> : null}
                        {!user.is_organization_root && user.status === "inactive" && !user.archived_at && canActivate ? <button style={sharedStyles.secondaryButton} onClick={() => void runAction(async () => { const reason = window.prompt(t("accountPolicy.reason")); if (reason && reason.trim().length >= 3) await activateAdminUser(user.id, reason); })}>{t("actions.reactivate")}</button> : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </PageFrame>
  );
}
