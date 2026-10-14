"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { PermissionGuard } from "@/components/PermissionGuard";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import { assignPermissionToRole, getRole, listPermissions, removePermissionFromRole } from "../api/roles-api";
import type { PermissionGroup, RoleDetail as RoleDetailType } from "../types";

const styles: Record<string, CSSProperties> = {
  card: { background: "var(--surface)", border: "1px solid var(--border-strong)", borderRadius: "8px", padding: "28px", marginBottom: "24px" },
  field: { display: "grid", gap: "4px", marginBottom: "16px" },
  label: { fontSize: "13px", fontWeight: 600, color: "var(--text-muted)" },
  value: { fontSize: "15px", color: "var(--text)" },
  groupTitle: { fontSize: "14px", fontWeight: 700, color: "var(--text-muted)", margin: "0 0 8px", textTransform: "uppercase" as const, letterSpacing: "0.05em" },
  permBadge: {
    display: "inline-flex", alignItems: "center", gap: "4px",
    background: "var(--accent-soft)", border: "1px solid color-mix(in srgb, var(--accent) 35%, var(--surface))", borderRadius: "6px",
    color: "var(--accent-strong)", fontSize: "12px", padding: "3px 8px", margin: "3px",
  },
  removeBtn: { background: "none", border: "none", color: "var(--danger)", cursor: "pointer", fontWeight: 700, fontSize: "13px", padding: 0 },
  addRow: { display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" as const, marginTop: "12px" },
  actions: { display: "flex", gap: "12px", flexWrap: "wrap" as const },
};

export function RoleDetailPage({ id }: { id: string }) {
  const t = useTranslations("administration.roles");
  const pt = useTranslations("administration.permissions");
  const getModuleLabel = (module: string) =>
    ({ foundation: pt("modules.foundation"), commercial: pt("modules.commercial"), production: pt("modules.production"), quality: pt("modules.quality") }[module] ?? module);
  const messages = useTranslations("messages");
  const [role, setRole] = useState<RoleDetailType | null>(null);
  const [permGroups, setPermGroups] = useState<PermissionGroup[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [selectedPermId, setSelectedPermId] = useState("");
  const [isAssigning, setIsAssigning] = useState(false);
  const isMountedRef = useRef(true);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [roleData, permsData] = await Promise.all([getRole(id), listPermissions()]);
      if (isMountedRef.current) {
        setRole(roleData);
        setPermGroups(permsData);
      }
    } catch (caughtError) {
      if (isMountedRef.current) setError(getApiErrorMessage(caughtError, messages));
    } finally {
      if (isMountedRef.current) setIsLoading(false);
    }
  }, [id, messages]);

  useEffect(() => {
    isMountedRef.current = true;
    void load();
    return () => { isMountedRef.current = false; };
  }, [load]);

  async function handleAssignPermission() {
    if (!selectedPermId || !role) return;
    setIsAssigning(true);
    try {
      await assignPermissionToRole(role.id, { permission_id: selectedPermId });
      if (isMountedRef.current) {
        setSuccessMessage(t("permissionAssignSuccess"));
        setSelectedPermId("");
        await load();
      }
    } catch (caughtError) {
      if (isMountedRef.current) setError(getApiErrorMessage(caughtError, messages));
    } finally {
      if (isMountedRef.current) setIsAssigning(false);
    }
  }

  async function handleRemovePermission(permId: string) {
    if (!role) return;
    try {
      await removePermissionFromRole(role.id, permId);
      if (isMountedRef.current) {
        setSuccessMessage(t("permissionRemoveSuccess"));
        await load();
      }
    } catch (caughtError) {
      if (isMountedRef.current) setError(getApiErrorMessage(caughtError, messages));
    }
  }

  const assignedPermIds = new Set(role?.permissions.map((p) => p.id) ?? []);
  const allPerms = permGroups.flatMap((g) => g.permissions);
  const availablePerms = allPerms.filter((p) => !assignedPermIds.has(p.id));

  const assignedByModule: Record<string, typeof allPerms> = {};
  for (const perm of role?.permissions ?? []) {
    if (!assignedByModule[perm.module_name]) assignedByModule[perm.module_name] = [];
    assignedByModule[perm.module_name].push(perm);
  }

  return (
    <PageFrame section="Administration" title={t("detailTitle")}>
      {isLoading ? <div style={{ ...sharedStyles.state, background: "var(--surface)" }}>{t("loadingDetail")}</div> : null}
      {!isLoading && error ? <div style={sharedStyles.error} role="alert">{error}</div> : null}
      {!isLoading && successMessage ? (
        <div style={{ background: "var(--success-soft)", border: "1px solid color-mix(in srgb, var(--success) 35%, var(--surface))", borderRadius: "6px", color: "var(--success)", fontSize: "14px", padding: "12px 14px", marginBottom: "16px" }} role="status">
          {successMessage}
        </div>
      ) : null}

      {!isLoading && role ? (
        <>
          <div style={styles.card}>
            <div style={styles.field}>
              <span style={styles.label}>{t("fields.name")}</span>
              <span style={styles.value}>{role.name}</span>
            </div>
            <div style={styles.field}>
              <span style={styles.label}>{t("fields.code")}</span>
              <code style={{ fontSize: "14px", background: "var(--surface-muted)", padding: "2px 8px", borderRadius: "4px" }}>{role.code}</code>
            </div>
            {role.description ? (
              <div style={styles.field}>
                <span style={styles.label}>{t("fields.description")}</span>
                <span style={styles.value}>{role.description}</span>
              </div>
            ) : null}
          </div>

          <div style={styles.card}>
            <h2 style={{ margin: "0 0 16px", fontSize: "16px" }}>{t("permissionsTitle")}</h2>
            {Object.keys(assignedByModule).length === 0 ? (
              <p style={{ color: "var(--text-subtle)", margin: "0 0 12px" }}>{pt("noPermissions")}</p>
            ) : (
              Object.entries(assignedByModule).map(([module, perms]) => (
                <div key={module} style={{ marginBottom: "16px" }}>
                  <p style={styles.groupTitle}>{getModuleLabel(module)}</p>
                  <div>
                    {perms.map((perm) => (
                      <span key={perm.id} style={styles.permBadge}>
                        {perm.name}
                        <PermissionGuard code="foundation:roles:write">
                          <button type="button" style={styles.removeBtn} onClick={() => void handleRemovePermission(perm.id)} title={t("removePermission")} aria-label={t("removePermission")}>×</button>
                        </PermissionGuard>
                      </span>
                    ))}
                  </div>
                </div>
              ))
            )}

            <PermissionGuard code="foundation:roles:write">
              {availablePerms.length > 0 ? (
                <div style={styles.addRow}>
                  <select style={sharedStyles.input} value={selectedPermId} onChange={(e) => setSelectedPermId(e.target.value)}>
                    <option value="">{t("permissionsTitle")}</option>
                    {permGroups.map((group) =>
                      group.permissions.filter((p) => !assignedPermIds.has(p.id)).length > 0 ? (
                        <optgroup key={group.module_name} label={getModuleLabel(group.module_name)}>
                          {group.permissions.filter((p) => !assignedPermIds.has(p.id)).map((p) => (
                            <option key={p.id} value={p.id}>{p.name}</option>
                          ))}
                        </optgroup>
                      ) : null
                    )}
                  </select>
                  <button type="button" style={sharedStyles.button} onClick={() => void handleAssignPermission()} disabled={!selectedPermId || isAssigning}>
                    {t("permissionsTitle")}
                  </button>
                </div>
              ) : null}
            </PermissionGuard>
          </div>

          <div style={styles.actions}>
            <PermissionGuard code="foundation:roles:write">
              <Link href={`/roles/${role.id}/edit`} style={sharedStyles.button}>{t("editTitle")}</Link>
            </PermissionGuard>
            <Link href="/roles" style={sharedStyles.secondaryButton}>{t("backToList")}</Link>
          </div>
        </>
      ) : null}
    </PageFrame>
  );
}
