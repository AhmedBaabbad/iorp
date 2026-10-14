"use client";

import { useLocale, useTranslations } from "next-intl";
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

import styles from "./roles.module.css";

const SCOPE_OPTIONS: AccessScope[] = ["own", "team", "organization"];

export function AdminRolePermissionsManager({ roleId, readOnly = false }: { roleId: string; readOnly?: boolean }) {
  const t = useTranslations("administration.roles");
  const tp = useTranslations("administration.permissions");
  const ts = useTranslations("administration.scope");
  const messages = useTranslations("messages");
  const locale = useLocale();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [busy, setBusy] = useState(false);
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

  const editable = canWrite && !readOnly && Boolean(role?.is_editable) && !busy;

  async function mutate(action: () => Promise<unknown>) {
    if (!editable) return;
    setBusy(true);
    setError(null);
    try { await action(); await load(); }
    catch (caughtError) { setError(getApiErrorMessage(caughtError, messages)); }
    finally { setBusy(false); }
  }
  const filtered = groups.map(group => ({...group, permissions: group.permissions.filter(p => {
    const matches = [p.code, p.name_ar, p.name_en, p.description_ar, p.description_en].join(" ").toLocaleLowerCase().includes(search.trim().toLocaleLowerCase());
    return matches && (filter === "all" || assignedScope.has(p.code) === (filter === "assigned"));
  })})).filter(group => group.permissions.length);
  return (
    <section className={styles.panel} aria-busy={busy} dir={locale === "ar" ? "rtl" : "ltr"}>
      <div className={styles.heading}><div><h2>{t("permissionsTitle")}</h2><p>{t("permissionsSubtitle")}</p></div><span className={styles.badge}>{t("explorer.granted", {count: assignedScope.size})}</span></div>
      <div className={styles.toolbar}>
        <input className={styles.input} aria-label={tp("searchPlaceholder")} placeholder={tp("searchPlaceholder")} value={search} onChange={e => setSearch(e.target.value)} />
        <select className={styles.input} aria-label={t("explorer.filter")} value={filter} onChange={e => setFilter(e.target.value)}>
          {["all", "assigned", "unassigned"].map(value => <option key={value} value={value}>{t(`explorer.${value}`)}</option>)}
        </select>
      </div>
      {error ? <div role="alert" style={sharedStyles.error}>{error}</div> : null}
      {!role && !error ? <p role="status">{tp("loading")}</p> : null}
      {role && !filtered.length ? <p role="status">{t("explorer.noMatches")}</p> : null}
      <div className={styles.groups}>
        {filtered.map(group => <details key={group.module} className={styles.group} open={search.trim() ? true : undefined}>
          <summary><strong>{locale === "ar" ? group.module_name_ar : group.module_name_en}</strong><span className={styles.badge}>{group.permissions.filter(p => assignedScope.has(p.code)).length} / {group.permissions.length}</span></summary>
          <div className={styles.permissionGrid}>{group.permissions.map(permission => {
            const assigned = assignedScope.has(permission.code);
            const name = locale === "ar" ? permission.name_ar : permission.name_en;
            return <article className={styles.permission} data-assigned={assigned} key={permission.code}>
              <label className={styles.permissionLabel}><input type="checkbox" checked={assigned} disabled={!editable} onChange={e => { const checked = e.target.checked; void mutate(() => checked ? assignAdminPermissionToRole(roleId, {permission_code: permission.code}) : removeAdminPermissionFromRole(roleId, permission.code)); }} /><strong>{name}</strong></label>
              <p>{locale === "ar" ? permission.description_ar : permission.description_en}</p>
              <details className={styles.technical}><summary>{tp("permissionCode")}</summary><code dir="ltr">{permission.code}</code></details>
              {assigned && permission.scopable ? <label className={styles.scope}>{ts("scopeLabel")}<select aria-label={`${ts("scopeLabel")}: ${name}`} disabled={!editable} value={assignedScope.get(permission.code) ?? "organization"} onChange={e => { const scope = e.target.value as AccessScope; void mutate(() => updateAdminRolePermissionScope(roleId, permission.code, scope)); }}>{SCOPE_OPTIONS.map(option => <option key={option} value={option} disabled={option === "team"}>{ts(option)}</option>)}</select></label> : null}
            </article>;
          })}</div>
        </details>)}
      </div>
    </section>
  );
}
