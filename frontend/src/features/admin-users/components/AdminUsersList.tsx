"use client";

import Link from "next/link";
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
  panel: { background: "#ffffff", border: "1px solid #d9dee7", borderRadius: "8px" },
  tableWrap: { overflowX: "auto" },
  table: { width: "100%", borderCollapse: "collapse" },
  th: { borderBottom: "1px solid #e4e7ec", color: "#52606d", fontSize: "13px", padding: "14px 16px", textAlign: "start" },
  td: { borderBottom: "1px solid #eef1f5", padding: "14px 16px" },
  actions: { display: "flex", flexWrap: "wrap", gap: "8px" },
  badge: { background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: "999px", color: "#1d4ed8", fontSize: "12px", padding: "2px 8px" },
  rootBadge: { background: "#eef2ff", border: "1px solid #a5b4fc", borderRadius: "999px", color: "#4338ca", display: "inline-block", fontSize: "12px", fontWeight: 700, marginInlineStart: "8px", padding: "2px 8px" },
  deleteButton: { ...sharedStyles.secondaryButton, borderColor: "#fecdd3", color: "#be123c", minHeight: "34px", padding: "6px 12px", fontSize: "13px" },
  backdrop: {
    position: "fixed",
    inset: 0,
    background: "rgba(15, 23, 42, 0.55)",
    backdropFilter: "blur(2px)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1000,
  },
  modal: {
    background: "#ffffff",
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
    background: "#fff1f2",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "22px",
    margin: "0 auto",
  },
  modalTitle: { fontSize: "18px", fontWeight: 700, color: "#0f172a", margin: 0, textAlign: "center" as const },
  modalBody: { fontSize: "14px", color: "#475569", margin: 0, lineHeight: "1.7", textAlign: "center" as const },
  modalWarning: { fontSize: "13px", fontWeight: 600, color: "#be123c", textAlign: "center" as const, margin: 0 },
  modalActions: { display: "flex", gap: "12px", justifyContent: "center", flexWrap: "wrap" as const },
  modalCancelButton: { ...sharedStyles.secondaryButton, minHeight: "40px", padding: "10px 24px", fontSize: "14px" },
  modalDeleteButton: {
    background: "#be123c",
    border: "none",
    borderRadius: "8px",
    color: "#ffffff",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: 600,
    minHeight: "40px",
    padding: "10px 24px",
  },
  success: {
    background: "#dcfce7",
    border: "1px solid #bbf7d0",
    borderRadius: "6px",
    color: "#166534",
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

  function statusBadge(status: AdminUserListItem["status"]): CSSProperties {
    if (status === "active") return { ...styles.badge, background: "#dcfce7", borderColor: "#86efac", color: "#166534" };
    if (status === "locked") return { ...styles.badge, background: "#fee2e2", borderColor: "#fca5a5", color: "#b91c1c" };
    return { ...styles.badge, background: "#f2f4f7", borderColor: "#d0d5dd", color: "#475467" };
  }

  useEffect(() => {
    isMountedRef.current = true;
    void loadUsers();
    return () => { isMountedRef.current = false; };
  }, [loadUsers]);

  return (
    <PageFrame
      section={t("section")}
      title={t("listTitle")}
      subtitle={t("subtitle")}
      action={canWrite ? <Link href="/admin/users/new" style={sharedStyles.button}>{t("newButton")}</Link> : null}
    >
      {isLoading ? <div style={{ ...sharedStyles.state, background: "#ffffff" }}>{t("loading")}</div> : null}
      {!isLoading && error ? <div style={sharedStyles.error} role="alert">{error}</div> : null}
      {!isLoading && !error && users.length === 0 ? (
        <section style={{ ...sharedStyles.state, background: "#ffffff" }}>{t("empty")}</section>
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
                  <th style={styles.th}>{t("fields.roles")}</th>
                  <th style={styles.th}>{t("fields.createdAt")}</th>
                  <th style={styles.th}>{t("fields.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td style={styles.td}>
                      <Link href={`/admin/users/${user.id}`}>{user.full_name}</Link>
                      {user.is_organization_root ? <span style={styles.rootBadge}>{t("rootBadge")}</span> : null}
                    </td>
                    <td style={styles.td}>{user.email}</td>
                    <td style={styles.td}><span style={statusBadge(user.status)}>{enumLabel("user", "status", user.status)}</span></td>
                    <td style={styles.td}>{user.roles.length ? user.roles.map((role) => <span key={role.id} style={styles.badge}>{role.name}</span>) : t("notAvailable")}</td>
                    <td style={styles.td}>{fmt.date(user.created_at)}</td>
                    <td style={styles.td}>
                      <div style={styles.actions}>
                        <Link href={`/admin/users/${user.id}`} style={sharedStyles.secondaryButton}>{common("actions.view")}</Link>
                        {canWrite && (user.status === "active" || user.is_organization_root) ? <Link href={`/admin/users/${user.id}/edit`} style={sharedStyles.secondaryButton}>{common("actions.edit")}</Link> : null}
                        {!user.is_organization_root && user.status === "active" && canLock ? <button style={sharedStyles.secondaryButton} onClick={() => void runAction(() => lockAdminUser(user.id))}>{t("actions.lock")}</button> : null}
                        {!user.is_organization_root && user.status === "locked" && canLock ? <button style={sharedStyles.secondaryButton} onClick={() => void runAction(() => unlockAdminUser(user.id))}>{t("actions.unlock")}</button> : null}
                        {!user.is_organization_root && user.status !== "inactive" && canDeactivate ? <Link style={styles.deleteButton} href={`/admin/users/${user.id}`}>{t("actions.deactivate")}</Link> : null}
                        {!user.is_organization_root && user.status === "inactive" && canActivate ? <button style={sharedStyles.secondaryButton} onClick={() => void runAction(() => activateAdminUser(user.id))}>{t("actions.reactivate")}</button> : null}
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
