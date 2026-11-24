"use client";
import {useClientListPage} from "@/hooks/useClientListPage";
import {Pagination,ListToolbar} from "@/components/pagination";

import { useEnumLabel } from "@/i18n/enum-helpers";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import { getAdminPermissionCatalog } from "../api/admin-permissions-api";
import type { AdminPermissionGroup } from "../types";

import styles from "@/features/admin-roles/components/roles.module.css";

export function AdminPermissionsList() {
  const permissionName = useEnumLabel("foundation", "permissionName");
  const permissionDescription = useEnumLabel("foundation", "permissionDescription");
  const t = useTranslations("administration.permissions");
  const messages = useTranslations("messages");
  const locale = useLocale();
  const [groups, setGroups] = useState<AdminPermissionGroup[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    getAdminPermissionCatalog()
      .then((catalog) => setGroups(catalog.modules))
      .catch((caughtError) => setError(getApiErrorMessage(caughtError, messages)))
      .finally(() => setIsLoading(false));
  }, [messages]);
  const flat=useMemo(()=>groups.flatMap(group=>group.permissions.map(permission=>({module:group.module,permission}))),[groups]);
  const page=useClientListPage(flat,row=>`${row.permission.code} ${permissionName(row.permission.code)}`,!isLoading,{search:"",module:"all"},(row,filters)=>filters.module==="all"||row.module===filters.module);
  const moduleFilter=page.filters.module;
  const filtered=groups.map(group=>({...group,permissions:page.items.filter(row=>row.module===group.module).map(row=>row.permission)})).filter(group=>group.permissions.length>0);
  const total = groups.reduce((count, group) => count + group.permissions.length, 0);

  return (
    <PageFrame section={t("section")} title={t("title")} subtitle={t("subtitle")}>
      <div style={{ ...sharedStyles.state, alignItems: "start", textAlign: "start", marginBottom: 16 }}>{t("codeManaged")}</div>
      <ListToolbar search={page.filters.search} onSearch={value=>page.set("search",value)} searchHint={t("searchPlaceholder")} onClear={page.clear} hasFilters={Boolean(page.filters.search||moduleFilter!=="all")}/>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>

        <select aria-label={t("filterByModule")} style={sharedStyles.input} value={moduleFilter} onChange={(event) => page.set("module",event.target.value)}>
          <option value="all">{t("allModules")}</option>
          {groups.map((group) => <option key={group.module} value={group.module}>{locale === "ar" ? group.module_name_ar : group.module_name_en}</option>)}
        </select>
      </div>
      <p>{t("totalPermissions", { count: total })}</p>
      {isLoading ? <div style={sharedStyles.state}>{t("loading")}</div> : null}
      {error ? <div style={sharedStyles.error}>{error}</div> : null}
      {!isLoading && !error && filtered.length === 0 ? <div style={sharedStyles.state}>{t("noPermissions")}</div> : null}
      <div style={{ display: "grid", gap: "16px" }}>
        {filtered.map((group) => (
          <section key={group.module} className={styles.panel}>
            <h2 style={{ margin: "0 0 12px", fontSize: "18px" }}>{locale === "ar" ? group.module_name_ar : group.module_name_en} ({group.permissions.length})</h2>
            <div className={styles.permissionGrid}>
              {group.permissions.map((permission) => (
                <div key={permission.code} className={styles.permission}>
                  <code dir="ltr" style={{ display: "inline-block", background: "var(--surface-muted)", padding: "4px 7px", borderRadius: 4 }}>{permission.code}</code>
                  <strong style={{ display: "block", marginTop: 8 }}>{permissionName(permission.code)}</strong>
                  <span>{permissionDescription(permission.code)}</span>
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
      <Pagination {...page.pagination} disabled={isLoading}/>
    </PageFrame>
  );
}
