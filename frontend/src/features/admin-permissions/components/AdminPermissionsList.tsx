"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import { getAdminPermissionCatalog } from "../api/admin-permissions-api";
import type { AdminPermissionGroup } from "../types";

export function AdminPermissionsList() {
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
  const [search, setSearch] = useState("");
  const [moduleFilter, setModuleFilter] = useState("all");
  const filtered = useMemo(() => groups
    .filter((group) => moduleFilter === "all" || group.module === moduleFilter)
    .map((group) => ({ ...group, permissions: group.permissions.filter((permission) => {
      const name = locale === "ar" ? permission.name_ar : permission.name_en;
      return `${permission.code} ${name}`.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase());
    }) }))
    .filter((group) => group.permissions.length > 0), [groups, locale, moduleFilter, search]);
  const total = groups.reduce((count, group) => count + group.permissions.length, 0);

  return (
    <PageFrame section={t("section")} title={t("title")} subtitle={t("subtitle")}>
      <div style={{ ...sharedStyles.state, alignItems: "start", textAlign: "start", marginBottom: 16 }}>{t("codeManaged")}</div>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
        <input aria-label={t("searchPlaceholder")} style={{ ...sharedStyles.input, flex: "1 1 280px" }} value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t("searchPlaceholder")} />
        <select aria-label={t("filterByModule")} style={sharedStyles.input} value={moduleFilter} onChange={(event) => setModuleFilter(event.target.value)}>
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
          <section key={group.module} style={{ background: "#ffffff", border: "1px solid #d9dee7", borderRadius: "8px", padding: "20px" }}>
            <h2 style={{ margin: "0 0 12px", fontSize: "18px" }}>{locale === "ar" ? group.module_name_ar : group.module_name_en} ({group.permissions.length})</h2>
            <div style={{ display: "grid", gap: "8px" }}>
              {group.permissions.map((permission) => (
                <div key={permission.code} style={{ border: "1px solid #e3e7ee", borderRadius: 6, padding: 12 }}>
                  <code style={{ display: "inline-block", background: "#f3f5f8", padding: "4px 7px", borderRadius: 4 }}>{permission.code}</code>
                  <strong style={{ display: "block", marginTop: 8 }}>{locale === "ar" ? permission.name_ar : permission.name_en}</strong>
                  <span>{locale === "ar" ? permission.description_ar : permission.description_en}</span>
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
    </PageFrame>
  );
}
