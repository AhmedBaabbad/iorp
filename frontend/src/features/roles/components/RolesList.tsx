"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { PermissionGuard } from "@/components/PermissionGuard";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import { deleteRole, listRoles } from "../api/roles-api";
import type { RoleListItem } from "../types";

const styles: Record<string, CSSProperties> = {
  panel: {
    background: "var(--surface)",
    border: "1px solid var(--border-strong)",
    borderRadius: "8px",
    boxShadow: "0 16px 40px rgba(31, 41, 51, 0.06)",
  },
  tableWrap: { overflowX: "auto" },
  table: { width: "100%", borderCollapse: "collapse" },
  th: {
    borderBottom: "1px solid var(--border)",
    color: "var(--text-muted)",
    fontSize: "13px",
    padding: "14px 16px",
    textAlign: "start",
    whiteSpace: "nowrap",
  },
  td: { borderBottom: "1px solid var(--border)", padding: "14px 16px", verticalAlign: "middle" },
  actions: { display: "flex", gap: "8px" },
  actionButton: { ...sharedStyles.secondaryButton, minHeight: "34px", padding: "6px 12px", fontSize: "13px" },
  deleteButton: {
    ...sharedStyles.secondaryButton,
    borderColor: "color-mix(in srgb, var(--danger) 35%, var(--surface))",
    color: "var(--danger)",
    minHeight: "34px",
    padding: "6px 12px",
    fontSize: "13px",
  },
  success: {
    background: "var(--success-soft)",
    border: "1px solid color-mix(in srgb, var(--success) 35%, var(--surface))",
    borderRadius: "6px",
    color: "var(--success)",
    fontSize: "14px",
    padding: "12px 14px",
    marginBottom: "16px",
  },
  backdrop: {
    position: "fixed", inset: 0, background: "var(--overlay)",
    backdropFilter: "blur(2px)", display: "flex", alignItems: "flex-start", justifyContent: "center", zIndex: 1000,
    overflowY: "auto", overscrollBehavior: "contain",
  },
  modal: {
    maxHeight: "calc(100dvh - 32px)", overflowY: "auto", margin: "auto", flexShrink: 0,
    background: "var(--surface)", borderRadius: "14px",
    boxShadow: "0 24px 64px rgba(15, 23, 42, 0.28)",
    padding: "32px", maxWidth: "460px", width: "90%", display: "grid", gap: "20px",
  },
  modalIcon: {
    width: "48px", height: "48px", borderRadius: "50%", background: "var(--surface-muted)",
    display: "flex", alignItems: "center", justifyContent: "center", fontSize: "22px", margin: "0 auto",
  },
  modalTitle: { fontSize: "18px", fontWeight: 700, color: "var(--text)", margin: 0, textAlign: "center" as const },
  modalBody: { fontSize: "14px", color: "var(--text-muted)", margin: 0, lineHeight: "1.7", textAlign: "center" as const },
  modalWarning: { fontSize: "13px", fontWeight: 600, color: "var(--danger)", textAlign: "center" as const, margin: 0 },
  modalActions: { display: "flex", flexWrap: "wrap", gap: "12px", justifyContent: "center" },
  modalCancelButton: { ...sharedStyles.secondaryButton, minHeight: "40px", padding: "10px 24px", fontSize: "14px" },
  modalDeleteButton: {
    background: "var(--danger)", border: "none", borderRadius: "8px", color: "var(--on-accent)",
    cursor: "pointer", fontSize: "14px", fontWeight: 600, minHeight: "40px", padding: "10px 24px",
  },
};

export function RolesList() {
  const t = useTranslations("administration.roles");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const [roles, setRoles] = useState<RoleListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [roleToDelete, setRoleToDelete] = useState<RoleListItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  const loadRoles = useCallback(async () => {
    if (!isMountedRef.current) return;
    setIsLoading(true);
    setError(null);
    try {
      const result = await listRoles();
      if (isMountedRef.current) setRoles(result);
    } catch (caughtError) {
      if (isMountedRef.current) setError(getApiErrorMessage(caughtError, messages));
    } finally {
      if (isMountedRef.current) setIsLoading(false);
    }
  }, [messages]);

  useEffect(() => {
    isMountedRef.current = true;
    void loadRoles();
    return () => { isMountedRef.current = false; };
  }, [loadRoles]);

  async function handleConfirmDelete() {
    if (!roleToDelete) return;
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await deleteRole(roleToDelete.id);
      if (isMountedRef.current) {
        setRoleToDelete(null);
        setSuccessMessage(t("deleteSuccess"));
        await loadRoles();
      }
    } catch {
      if (isMountedRef.current) setDeleteError(t("deleteError"));
    } finally {
      if (isMountedRef.current) setIsDeleting(false);
    }
  }

  function handleCancelDelete() {
    if (isDeleting) return;
    setRoleToDelete(null);
    setDeleteError(null);
  }

  return (
    <>
      {roleToDelete ? (
        <div style={styles.backdrop} onClick={!isDeleting ? handleCancelDelete : undefined}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalIcon}>!</div>
            <h2 style={styles.modalTitle}>{t("deleteConfirmTitle")}</h2>
            <p style={styles.modalBody}>{t("deleteConfirmMessage", { name: roleToDelete.name })}</p>
            <p style={styles.modalWarning}>{t("deleteWarning")}</p>
            {deleteError ? <div style={sharedStyles.error} role="alert">{deleteError}</div> : null}
            <div style={styles.modalActions}>
              <button type="button" style={styles.modalCancelButton} onClick={handleCancelDelete} disabled={isDeleting}>
                {t("deleteCancelButton")}
              </button>
              <button type="button" style={styles.modalDeleteButton} onClick={() => void handleConfirmDelete()} disabled={isDeleting}>
                {isDeleting ? messages("loading.deleting") : t("deleteConfirmButton")}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <PageFrame
        section="Administration"
        title={t("listTitle")}
        subtitle={t("subtitle")}
        action={
          <PermissionGuard code="foundation:roles:write">
            <Link href="/roles/new" style={sharedStyles.button}>{t("newButton")}</Link>
          </PermissionGuard>
        }
      >
        {isLoading ? <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>{t("loading")}</div> : null}

        {!isLoading && successMessage ? (
          <div style={styles.success} role="status">{successMessage}</div>
        ) : null}

        {!isLoading && error ? (
          <div style={{ display: "grid", gap: "12px" }}>
            <div style={sharedStyles.error} role="alert">{error}</div>
            <button style={{ ...sharedStyles.secondaryButton, width: "fit-content" }} type="button" onClick={() => void loadRoles()}>
              {common("actions.retry")}
            </button>
          </div>
        ) : null}

        {!isLoading && !error && roles.length === 0 ? (
          <section style={{ ...sharedStyles.state, background: "var(--surface)" }}>
            <h2 style={{ margin: "0 0 8px", fontSize: "20px" }}>{t("empty")}</h2>
            <p style={{ margin: "0 0 18px" }}>{t("createFirst")}</p>
            <PermissionGuard code="foundation:roles:write">
              <Link href="/roles/new" style={sharedStyles.button}>{t("newButton")}</Link>
            </PermissionGuard>
          </section>
        ) : null}

        {!isLoading && !error && roles.length > 0 ? (
          <section style={styles.panel}>
            <div style={styles.tableWrap}>
              <table style={styles.table}>
                <thead>
                  <tr>
                    <th style={styles.th}>{t("fields.name")}</th>
                    <th style={styles.th}>{t("fields.code")}</th>
                    <th style={styles.th}>{t("fields.description")}</th>
                    <th style={styles.th}>{t("fields.permissionCount")}</th>
                    <th style={styles.th}>{t("fields.userCount")}</th>
                    <th style={styles.th}>{t("fields.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {roles.map((role) => (
                    <tr key={role.id}>
                      <td style={styles.td}>
                        <Link href={`/roles/${role.id}`} style={{ color: "var(--accent-strong)", fontWeight: 700, textDecoration: "none" }}>
                          {role.name}
                        </Link>
                      </td>
                      <td style={styles.td}><code style={{ fontSize: "13px", background: "var(--surface-muted)", padding: "2px 6px", borderRadius: "4px" }}>{role.code}</code></td>
                      <td style={styles.td}>{role.description ?? "—"}</td>
                      <td style={styles.td}>{role.permission_count}</td>
                      <td style={styles.td}>{role.user_count}</td>
                      <td style={styles.td}>
                        <div style={styles.actions}>
                          <PermissionGuard code="foundation:roles:write">
                            <Link href={`/roles/${role.id}/edit`} style={styles.actionButton}>{common("actions.edit")}</Link>
                            <button
                              type="button"
                              style={styles.deleteButton}
                              onClick={() => { setRoleToDelete(role); setDeleteError(null); setSuccessMessage(null); }}
                              disabled={isDeleting && roleToDelete?.id === role.id}
                            >
                              {common("actions.delete")}
                            </button>
                          </PermissionGuard>
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
    </>
  );
}
