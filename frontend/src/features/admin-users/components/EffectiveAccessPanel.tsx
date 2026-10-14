"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";

import { getMyEffectiveAccess } from "@/features/auth/auth-client";
import { getAdminUserEffectiveAccess } from "../api/admin-users-api";
import type { EffectiveAccessReport } from "../types";
import css from "./effective-access-panel.module.css";

type Props = { userId?: string; self?: boolean };
type Visibility = "all" | "granted" | "missing";

export function EffectiveAccessPanel({ userId, self = false }: Props) {
  const locale = useLocale();
  const labels = useTranslations("administration.permissions");
  const rolesT = useTranslations("administration.roles");
  const moduleLabel = (module: string) => t.has(`modules.${module}`) ? t(`modules.${module}`) : module;
  const t = useTranslations("effectiveAccess");
  const [report, setReport] = useState<EffectiveAccessReport | null>(null);
  const [failed, setFailed] = useState(false);
  const [query, setQuery] = useState("");
  const [moduleFilter, setModuleFilter] = useState("all");
  const [visibility, setVisibility] = useState<Visibility>("all");
  const [missingOpen, setMissingOpen] = useState(false);

  useEffect(() => {
    let active = true;
    setReport(null);
    setFailed(false);
    const request = self ? getMyEffectiveAccess(locale) : getAdminUserEffectiveAccess(userId!, locale);
    request.then(data => { if (active) setReport(data); }).catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [self, userId, locale]);

  const normalized = query.trim().toLocaleLowerCase();
  const modules = useMemo(() => report ? Array.from(new Set([
    ...Object.keys(report.permissions_by_module),
    ...report.missing_permissions.map((item) => item.module),
  ])).sort() : [], [report]);
  const matches = (item: { code: string; name: string; module: string }) =>
    (moduleFilter === "all" || item.module === moduleFilter)
    && (!normalized || `${item.code} ${item.name}`.toLocaleLowerCase().includes(normalized));

  if (failed) return <section className={css.panel}><div className={css.error} role="alert">{t("error")}</div></section>;
  if (!report) return <section className={css.panel}><p>{t("loading")}</p></section>;

  const grantedModules = Object.entries(report.permissions_by_module)
    .map(([module, permissions]) => [module, permissions.filter(matches)] as const)
    .filter(([, permissions]) => permissions.length);
  const missing = report.missing_permissions.filter(matches);

  return <section className={css.panel} dir={locale === "ar" ? "rtl" : "ltr"} aria-labelledby={`effective-access-${report.user_id}`}>
    <header className={css.header}>
      <div><h2 id={`effective-access-${report.user_id}`}>{t(self ? "myAccessTitle" : "title")}</h2>
        <p>{t(self ? "myAccessSubtitle" : "subtitle", { name: report.user_full_name })}</p></div>
      <time dateTime={report.generated_at}>{t("generatedAt")}: {new Date(report.generated_at).toLocaleString(locale)}</time>
    </header>
    {report.is_organization_root ? <div className={css.rootNotice} role="note">🔑 {t("rootNotice")}</div> : null}
    <div className={css.metrics}>
      <div><span>{t("totalRoles")}</span><strong>{report.total_roles}</strong></div>
      <div><span>{t("totalPermissions")}</span><strong>{report.total_permissions}</strong></div>
      <div><span>{t("totalMissing")}</span><strong>{report.missing_permissions_count}</strong></div>
    </div>
    <div className={css.roles}>
      <h3>{t("totalRoles")}</h3>
      {report.roles.length ? report.roles.map((role) => <span key={role.id}>{role.is_system && rolesT.has(`systemRoleNames.${role.code}`) ? rolesT(`systemRoleNames.${role.code}`) : role.name} · {t(role.is_system ? "systemRole" : "customRole")}</span>) : <p>{t("noRoles")}</p>}
    </div>
    <div className={css.filters}>
      <input aria-label={t("searchPlaceholder")} placeholder={t("searchPlaceholder")} value={query} onChange={(event) => setQuery(event.target.value)} />
      <select aria-label={t("moduleFilter")} value={moduleFilter} onChange={(event) => setModuleFilter(event.target.value)}>
        <option value="all">{t("filterAll")}</option>
        {modules.map((module) => <option key={module} value={module}>{moduleLabel(module)}</option>)}
      </select>
      <select aria-label={t("showFilter")} value={visibility} onChange={(event) => setVisibility(event.target.value as Visibility)}>
        <option value="all">{t("filterAll")}</option><option value="granted">{t("filterGranted")}</option><option value="missing">{t("filterMissing")}</option>
      </select>
    </div>
    {visibility !== "missing" ? <div className={css.moduleList}>
      {grantedModules.length ? grantedModules.map(([module, permissions]) => <details className={css.module} key={module} open={normalized ? true : undefined}>
        <summary>{moduleLabel(module)} <span>{t("modulePermissionCount", { count: permissions.length })}</span></summary><div className={css.permissionGrid}>
        {permissions.map((permission) => <article className={css.permission} key={permission.code}>
          <div><strong>{permission.name}</strong><p>{permission.description}</p><details className={css.code}><summary>{labels("permissionCode")}</summary><code dir="ltr">{permission.code}</code></details></div>
          <span className={`${css.scope} ${css[permission.effective_scope]}`}>{permission.scopable ? permission.scope_label : t("scopeNotApplicable")}</span>
          <div className={css.sources}>{permission.is_root_bypass ? <span>{t("rootBadge")}</span> : permission.granted_by_roles.map((source) => <span key={`${permission.code}-${source.role_id}`}>{t("grantedBy")}: {source.role_name} · {t(`scope${source.scope[0].toUpperCase()}${source.scope.slice(1)}`)}</span>)}</div>
        </article>)}
      </div></details>) : <p>{t("noPermissions")}</p>}
    </div> : null}
    {visibility !== "granted" ? <section className={css.missing}>
      <button type="button" aria-expanded={visibility === "missing" || missingOpen} onClick={() => setMissingOpen((value) => !value)}>{visibility === "missing" || missingOpen ? t("hideMissing") : t("showMissing", { count: missing.length })}</button>
      {visibility === "missing" || missingOpen ? <div>{missing.map((item) => <p key={item.code}><span>{item.name}</span><code dir="ltr">{item.code}</code></p>)}</div> : null}
    </section> : null}
  </section>;
}
