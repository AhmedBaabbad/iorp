"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";

import { usePermission } from "@/features/auth";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import { listAdminPermissions } from "@/features/admin-permissions/api/admin-permissions-api";
import type { AdminPermissionGroup as CatalogPermissionGroup } from "@/features/admin-permissions/types";
import {
  assignAdminPermissionToRole,
  getAdminRole,
  removeAdminPermissionFromRole,
  updateAdminRolePermissionScope,
} from "../api/admin-roles-api";
import type { AccessScope, AdminRoleDetail } from "../types";

const SCOPE_OPTIONS: AccessScope[] = ["own", "team", "organization"];

export function AdminRolePermissionsManager({ roleId, readOnly = false }: { roleId: string; readOnly?: boolean }) {
  const t = useTranslations("administration.roles");
  const tp = useTranslations("administration.permissions");
  const ts = useTranslations("administration.scope");
  const messages = useTranslations("messages");
  const moduleLabels: Record<string, string> = {
    foundation: tp("modules.foundation"),
    commercial: tp("modules.commercial"),
    production: tp("modules.production"),
    quality: tp("modules.quality"),
  };
  const canWrite = usePermission("foundation:role_permissions:write");
  const [role, setRole] = useState<AdminRoleDetail | null>(null);
  const [groups, setGroups] = useState<CatalogPermissionGroup[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [roleData, permissionGroups] = await Promise.all([
        getAdminRole(roleId),
        listAdminPermissions(),
      ]);
      setRole(roleData);
      setGroups(permissionGroups);
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError, messages));
    }
  }, [messages, roleId]);

  useEffect(() => {
    void load();
  }, [load]);

  const assignedScope = useMemo(
    () => new Map(role?.permissions.flatMap((group) => group.permissions.map((p) => [p.code, p.scope] as const)) ?? []),
    [role],
  );

  const editable = canWrite && !readOnly;

  async function togglePermission(code: string, checked: boolean) {
    if (!editable) return;
    if (checked) {
      await assignAdminPermissionToRole(roleId, { permission_code: code });
    } else {
      await removeAdminPermissionFromRole(roleId, code);
    }
    await load();
  }

  async function changeScope(code: string, scope: AccessScope) {
    if (!editable) return;
    await updateAdminRolePermissionScope(roleId, code, scope);
    await load();
  }

  return (
    <section style={{ background: "#ffffff", border: "1px solid #d9dee7", borderRadius: "8px", padding: "20px" }}>
      <h2 style={{ margin: "0 0 16px", fontSize: "16px" }}>{t("permissionsTitle")}</h2>
      {error ? <div style={sharedStyles.error}>{error}</div> : null}
      <div style={{ display: "grid", gap: "18px" }}>
        {groups.map((group) => (
          <div key={group.module}>
            <h3 style={{ margin: "0 0 8px", fontSize: "14px" }}>
              {moduleLabels[group.module] ?? group.module} ({group.permissions.filter((p) => assignedScope.has(p.code)).length}/{group.permissions.length})
            </h3>
            <div style={{ display: "grid", gap: "8px" }}>
              {group.permissions.map((permission) => {
                const isAssigned = assignedScope.has(permission.code);
                const currentScope = assignedScope.get(permission.code) ?? "organization";
                return (
                  <div key={permission.code} style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                    <label style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                      <input
                        type="checkbox"
                        checked={isAssigned}
                        disabled={!editable}
                        onChange={(event) => void togglePermission(permission.code, event.target.checked)}
                      />
                      <span>{permission.code} - {permission.name}</span>
                    </label>
                    {isAssigned ? (
                      permission.scopable ? (
                        <div style={{ marginInlineStart: "26px", display: "flex", alignItems: "center", gap: "8px" }}>
                          <span style={{ fontSize: "12px", color: "#5b6472" }}>{ts("scopeLabel")}:</span>
                          <select
                            value={currentScope}
                            disabled={!editable}
                            onChange={(event) => void changeScope(permission.code, event.target.value as AccessScope)}
                            style={{ fontSize: "12px", padding: "3px 6px" }}
                          >
                            {SCOPE_OPTIONS.map((option) => (
                              <option key={option} value={option} disabled={option === "team"}>
                                {ts(option)}
                              </option>
                            ))}
                          </select>
                        </div>
                      ) : (
                        <span style={{ marginInlineStart: "26px", fontSize: "12px", color: "#8a93a3" }}>
                          {ts("notSupported")}
                        </span>
                      )
                    ) : null}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
