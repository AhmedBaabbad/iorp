"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import { deleteAdminRole, listAdminRoles } from "../api/admin-roles-api";
import type { AdminRoleListItem } from "../types";

export function AdminRolesList() {
  const t = useTranslations("administration.roles");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const canWrite = usePermission("foundation:roles:write");
  const [roles, setRoles] = useState<AdminRoleListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<AdminRoleListItem | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const loadRoles = useCallback(async () => {
    try {
      const data = await listAdminRoles();
      setRoles(data);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError, messages));
    }
  }, [messages]);

  useEffect(() => {
    void loadRoles();
  }, [loadRoles]);

  async function confirmDelete() {
    if (!pendingDelete) return;
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await deleteAdminRole(pendingDelete.id);
      setPendingDelete(null);
      await loadRoles();
    } catch (caughtError) {
      setDeleteError(getApiErrorMessage(caughtError, messages));
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <PageFrame
      section={t("section")}
      title={t("listTitle")}
      subtitle={t("subtitle")}
      action={canWrite ? <Link href="/admin/roles/new" style={sharedStyles.button}>{t("newButton")}</Link> : null}
    >
      {error ? <div style={sharedStyles.error}>{error}</div> : null}
      {roles.length === 0 && !error ? <div style={sharedStyles.state}>{t("empty")}</div> : null}
      {roles.length > 0 ? (
        <section style={{ background: "#ffffff", border: "1px solid #d9dee7", borderRadius: "8px", overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={{ padding: "14px", textAlign: "start" }}>{t("fields.name")}</th>
                <th style={{ padding: "14px", textAlign: "start" }}>{t("fields.code")}</th>
                <th style={{ padding: "14px", textAlign: "start" }}>{t("fields.permissionCount")}</th>
                <th style={{ padding: "14px", textAlign: "start" }}>{t("fields.userCount")}</th>
                <th style={{ padding: "14px", textAlign: "start" }}>{t("fields.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {roles.map((role) => (
                <tr key={role.id}>
                  <td style={{ padding: "14px" }}><Link href={`/admin/roles/${role.id}`}>{role.is_system && t.has(`systemRoleNames.${role.code}`) ? t(`systemRoleNames.${role.code}`) : role.name}</Link>{role.is_system ? <span style={{ marginInlineStart: 8, padding: "3px 7px", borderRadius: 10, background: "#e8eef8", fontSize: 12 }}>{t("systemBadge")}</span> : <span style={{ marginInlineStart: 8, padding: "3px 7px", borderRadius: 10, background: "#e9f7ef", fontSize: 12 }}>{t("customBadge")}</span>}{role.is_protected ? <span title={t("protectedHint")} style={{ marginInlineStart: 6 }}>🔒</span> : null}</td>
                  <td style={{ padding: "14px" }}>{role.code}</td>
                  <td style={{ padding: "14px" }}>{role.permissions_count}</td>
                  <td style={{ padding: "14px" }}>{role.users_count}</td>
                  <td style={{ padding: "14px" }}>
                    <div style={{ display: "flex", gap: "8px" }}>
                      <Link href={`/admin/roles/${role.id}`} style={sharedStyles.secondaryButton}>{common("actions.view")}</Link>
                      {canWrite && !role.is_system && !role.is_protected ? (
                        <button
                          type="button"
                          style={sharedStyles.dangerButton}
                          onClick={() => { setDeleteError(null); setPendingDelete(role); }}
                        >
                          {common("actions.delete")}
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}

      {pendingDelete ? (
        <div style={sharedStyles.modalOverlay}>
          <div style={sharedStyles.modal}>
            <h2 style={sharedStyles.modalTitle}>{t("deleteConfirmTitle")}</h2>
            <p>{t("deleteConfirmMessage", { name: pendingDelete.name })}</p>
            <p style={sharedStyles.modalWarning}>{t("deleteWarning")}</p>
            {deleteError ? <div style={sharedStyles.error}>{deleteError}</div> : null}
            <div style={sharedStyles.modalActions}>
              <button
                type="button"
                style={sharedStyles.secondaryButton}
                disabled={isDeleting}
                onClick={() => setPendingDelete(null)}
              >
                {t("deleteCancelButton")}
              </button>
              <button
                type="button"
                style={sharedStyles.dangerButton}
                disabled={isDeleting}
                onClick={() => void confirmDelete()}
              >
                {isDeleting ? "..." : t("deleteConfirmButton")}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </PageFrame>
  );
}
