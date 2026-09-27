"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { useAuth, usePermission } from "@/features/auth";
import { useFormatter } from "@/hooks/useFormatter";
import { ApiClientError } from "@/lib/api-client";
import { sharedStyles } from "@/styles/shared-styles";
import {
  assignAdminRoleToUser, getAdminUserRoles, getAssignableAdminRoles, removeAdminRoleFromUser,
} from "../api/admin-users-api";
import type { AdminUserRoleRef, AssignedRole, AssignableRole } from "../types";
import css from "./admin-user-detail.module.css";

type Props = {
  userId: string;
  userName: string;
  isOrganizationRoot: boolean;
  assignedRoles: AdminUserRoleRef[];
  onChanged: () => void;
};

export function AdminUserRolesManager({ userId, userName, isOrganizationRoot, assignedRoles, onChanged }: Props) {
  const t = useTranslations("administration.users.assignment");
  const rolesT = useTranslations("administration.roles");
  const common = useTranslations("common");
  const { user: currentUser } = useAuth();
  const canWrite = usePermission("foundation:user_roles:write");
  const fmt = useFormatter();
  const isSelf = currentUser?.id === userId;
  const [roles, setRoles] = useState<AssignedRole[]>(assignedRoles.map((role) => ({ ...role, is_system: false, is_protected: false, assigned_by: null, assigned_at: "" })));
  const [assignable, setAssignable] = useState<AssignableRole[]>([]);
  const [restrictedCount, setRestrictedCount] = useState(0);
  const [selectedRoleId, setSelectedRoleId] = useState("");
  const [showAssign, setShowAssign] = useState(false);
  const [removeRole, setRemoveRole] = useState<AssignedRole | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const result = await getAdminUserRoles(userId);
      setRoles(result.roles);
    } catch (caught) {
      setError(errorMessage(caught, t));
    }
  }, [t, userId]);

  useEffect(() => { void load(); }, [load]);

  async function openAssignment() {
    setError(null);
    try {
      const result = await getAssignableAdminRoles(userId);
      setAssignable(result.assignable_roles);
      setRestrictedCount(result.restricted_count);
      setSelectedRoleId(result.assignable_roles[0]?.id ?? "");
      setShowAssign(true);
    } catch (caught) {
      setError(errorMessage(caught, t));
    }
  }

  async function confirmAssignment() {
    if (!selectedRoleId) return;
    setBusy(true); setError(null);
    try {
      await assignAdminRoleToUser(userId, { role_id: selectedRoleId });
      setSuccess(t("assignSuccess")); setShowAssign(false);
      await load(); onChanged();
    } catch (caught) { setError(errorMessage(caught, t)); }
    finally { setBusy(false); }
  }

  async function confirmRemoval() {
    if (!removeRole) return;
    setBusy(true); setError(null);
    try {
      await removeAdminRoleFromUser(userId, removeRole.id);
      setSuccess(t("removeSuccess")); setRemoveRole(null);
      await load(); onChanged();
    } catch (caught) { setError(errorMessage(caught, t)); }
    finally { setBusy(false); }
  }

  const roleName = (role: { code: string; name: string; is_system: boolean }) =>
    role.is_system && rolesT.has(`systemRoleNames.${role.code}`) ? rolesT(`systemRoleNames.${role.code}`) : role.name;

  return (
    <section className={css.rolesCard}>
      <div className={css.rolesHeader}><h2>{t("rolesSection")}</h2>{canWrite && !isSelf && !isOrganizationRoot ? <button type="button" style={sharedStyles.button} onClick={() => void openAssignment()}>{t("assignRole")}</button> : null}</div>
      {isSelf ? <div role="note">{t("cannotModifyOwnRoles")}</div> : null}
      {isOrganizationRoot ? <div role="note">{t("rootRolesProtected")}</div> : null}
      {success ? <div role="status" style={{ color: "#166534" }}>{success}</div> : null}
      {error ? <div role="alert" style={sharedStyles.error}>{error}</div> : null}
      {roles.length === 0 ? <span>{t("noAssignedRoles")}</span> : roles.map((role) => (
        <div key={role.id} className={css.roleItem}>
          <div className={css.roleIdentity}><span className={css.roleName}>{roleName(role)}</span><code className={css.roleCode}>{role.code}</code><div className={css.roleTags}><span className={css.roleTag}>{role.is_system ? t("systemBadge") : t("customBadge")}</span>{role.is_protected ? <span className={css.roleTag}>{t("protectedBadge")}</span> : null}</div><div className={css.roleMeta}>{t("assignedBy")}: {role.assigned_by?.full_name ?? t("assignedBySystem")} · {t("assignedAt")}: {role.assigned_at ? fmt.dateTime(role.assigned_at) : t("assignedBySystem")}</div></div>
          {canWrite && !isSelf && !isOrganizationRoot ? <button type="button" style={sharedStyles.dangerButton} onClick={() => setRemoveRole(role)}>{t("removeRole")}</button> : null}
        </div>
      ))}

      {showAssign ? <div style={sharedStyles.modalOverlay}><div style={sharedStyles.modal}>
        <h3>{t("assignRole")}</h3>
        {assignable.length ? <select style={sharedStyles.input} value={selectedRoleId} onChange={(event) => setSelectedRoleId(event.target.value)} aria-label={t("selectRole")}>
          {assignable.map((role) => <option key={role.id} value={role.id}>{roleName(role)} · {role.code} · {t("permissionCount", { count: role.permission_count })}</option>)}
        </select> : <p>{t("noAssignableRoles")}</p>}
        {restrictedCount > 0 ? <p>{t("someRolesRestricted")}</p> : null}
        <div style={sharedStyles.modalActions}>
          <button type="button" style={sharedStyles.secondaryButton} onClick={() => setShowAssign(false)}>{common("actions.cancel")}</button>
          {assignable.length ? <button type="button" style={sharedStyles.button} disabled={busy} onClick={() => void confirmAssignment()}>{t("assignRole")}</button> : null}
        </div>
      </div></div> : null}

      {removeRole ? <div style={sharedStyles.modalOverlay}><div style={sharedStyles.modal}>
        <h3>{t("confirmRemove.title")}</h3>
        <p>{t("confirmRemove.message", { roleName: roleName(removeRole), userName })}</p>
        <p>{t("confirmRemove.warning")}</p>
        <div style={sharedStyles.modalActions}>
          <button type="button" style={sharedStyles.secondaryButton} onClick={() => setRemoveRole(null)}>{common("actions.cancel")}</button>
          <button type="button" style={sharedStyles.dangerButton} disabled={busy} onClick={() => void confirmRemoval()}>{t("confirmRemove.button")}</button>
        </div>
      </div></div> : null}
    </section>
  );
}

function errorMessage(error: unknown, t: (key: string) => string): string {
  if (error instanceof ApiClientError && error.details && typeof error.details === "object" && "code" in error.details) {
    const code = String((error.details as { code: unknown }).code);
    const keys: Record<string, string> = {
      CROSS_ORG_ROLE_ASSIGNMENT: "errors.crossOrg", CROSS_ORG_USER_ASSIGNMENT: "errors.crossOrg",
      CROSS_ORG_ROLE_REMOVAL: "errors.crossOrg", CROSS_ORG_USER_REMOVAL: "errors.crossOrg",
      SELF_ROLE_ASSIGNMENT: "errors.selfAssignment", SELF_ROLE_REMOVAL: "errors.selfRemoval",
      CANNOT_REMOVE_ROOT_ROLE: "errors.rootProtected", ROLE_ALREADY_ASSIGNED: "errors.alreadyAssigned",
      ROLE_NOT_ASSIGNED: "errors.notAssigned", PRIVILEGE_ESCALATION: "errors.escalation",
    };
    if (keys[code]) return t(keys[code]);
  }
  return t("errors.generic");
}
