"use client";
/* eslint-disable @next/next/no-img-element -- authenticated blob URLs cannot use next/image. */

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import type { FormEvent, ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { PasswordInput } from "@/components/PasswordInput";
import { API_BASE_URL, ApiClientError } from "@/lib/api-client";
import type { PlatformAdministrator, PlatformOrganizationSummary } from "@/types/platform";
import { changePlatformPassword, listPlatformAdministrators, listPlatformOrganizations } from "./platform-api";
import { usePlatformAuth } from "./platform-auth-context";
import { PlatformProtectedRoute } from "./platform-protected-route";
import css from "./platform-dashboard-page.module.css";

const STATUS_BAR_KEYS = ["active", "suspended", "inactive", "archived"] as const;
const STATUS_COLOR: Record<(typeof STATUS_BAR_KEYS)[number], string> = {
  active: "#55d99a",
  suspended: "#f6bd53",
  inactive: "#fb8998",
  archived: "#9cabc1",
};

function Icon({ children, size = 20 }: { children: ReactNode; size?: number }) {
  return (
    <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      {children}
    </svg>
  );
}

const icons = {
  building: <Icon><rect x="4" y="3" width="16" height="18" rx="2" /><path d="M8 7h2M14 7h2M8 11h2M14 11h2M9 21v-5h6v5" /></Icon>,
  check: <Icon><circle cx="12" cy="12" r="9" /><path d="m8 12 2.5 2.5L16 9" /></Icon>,
  pause: <Icon><circle cx="12" cy="12" r="9" /><path d="M10 9v6M14 9v6" /></Icon>,
  shield: <Icon><path d="M12 3l8 3.5v5c0 5-3.4 8.5-8 9.5-4.6-1-8-4.5-8-9.5v-5L12 3Z" /><path d="m9 12 2 2 4-4" /></Icon>,
  plus: <Icon size={18}><path d="M12 5v14M5 12h14" /></Icon>,
  list: <Icon size={18}><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" /></Icon>,
  key: <Icon size={18}><circle cx="8" cy="15" r="4" /><path d="m10.5 12.5 8-8M16 5l2 2M13 8l2 2" /></Icon>,
  clock: <Icon size={18}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3.5 2" /></Icon>,
};

function initials(name: string) {
  return name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
}

function colorFor(name: string) {
  const colors = ["#2563eb", "#7c3aed", "#0891b2", "#059669", "#c2410c", "#be185d"];
  return colors[[...name].reduce((sum, char) => sum + char.charCodeAt(0), 0) % colors.length];
}

function relativeTime(value: string, locale: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const diffSeconds = Math.round((date.getTime() - Date.now()) / 1000);
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 60 * 60 * 24 * 365],
    ["month", 60 * 60 * 24 * 30],
    ["day", 60 * 60 * 24],
    ["hour", 60 * 60],
    ["minute", 60],
  ];
  const formatter = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  for (const [unit, seconds] of units) {
    if (Math.abs(diffSeconds) >= seconds) {
      return formatter.format(Math.round(diffSeconds / seconds), unit);
    }
  }
  return formatter.format(0, "minute");
}

function OrgLogo({ organization, token }: { organization: PlatformOrganizationSummary; token?: string | null }) {
  const [source, setSource] = useState("");
  useEffect(() => {
    if (!organization.has_logo || !organization.logo_url || !token) return;
    let objectUrl = "";
    const url = `${API_BASE_URL.replace(/\/$/, "")}${organization.logo_url}`;
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => (response.ok ? response.blob() : Promise.reject()))
      .then((blob) => { objectUrl = URL.createObjectURL(blob); setSource(objectUrl); })
      .catch(() => setSource(""));
    return () => { if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [organization.has_logo, organization.logo_url, token]);

  if (source) return <img className={css.orgLogo} src={source} alt="" />;
  return <span className={css.orgLogoFallback} style={{ background: colorFor(organization.name) }}>{initials(organization.name)}</span>;
}

function PlatformDashboardContent() {
  const t = useTranslations("platform.dashboard");
  const locale = useLocale();
  const isRtl = locale === "ar";
  const { account, token } = usePlatformAuth();

  const permissions = useMemo(() => account?.permissions ?? [], [account]);
  const isRoot = account?.role === "root";
  const canCreateOrg = permissions.includes("platform:organizations:create");
  const canReadOrgs = permissions.includes("platform:organizations:read");
  const canReadAdmins = permissions.includes("platform:administrators:read");
  const canReadAudit = permissions.includes("platform:audit:read");
  const canReadSecurityLog = permissions.includes("platform:security_log:read");
  const canReadActivityLog = permissions.includes("platform:activity_log:read");

  const [orgs, setOrgs] = useState<PlatformOrganizationSummary[] | null>(null);
  const [orgsError, setOrgsError] = useState(false);
  const [admins, setAdmins] = useState<PlatformAdministrator[] | null>(null);
  const [adminsError, setAdminsError] = useState(false);

  const loadOrgs = useCallback(() => {
    if (!canReadOrgs) return;
    setOrgsError(false);
    setOrgs(null);
    listPlatformOrganizations(token).then(setOrgs).catch(() => setOrgsError(true));
  }, [token, canReadOrgs]);

  const loadAdmins = useCallback(() => {
    if (!canReadAdmins) return;
    setAdminsError(false);
    setAdmins(null);
    listPlatformAdministrators(token).then(setAdmins).catch(() => setAdminsError(true));
  }, [token, canReadAdmins]);

  useEffect(() => { loadOrgs(); }, [loadOrgs]);
  useEffect(() => { loadAdmins(); }, [loadAdmins]);

  const totalOrgs = orgs?.length ?? null;
  const activeOrgs = orgs ? orgs.filter((org) => org.status === "active").length : null;
  const suspendedOrgs = orgs ? orgs.filter((org) => org.status === "suspended").length : null;
  const totalAdmins = admins?.length ?? null;
  const activeAdmins = admins ? admins.filter((item) => item.status === "active").length : null;

  const recentOrgs = useMemo(() => {
    if (!orgs) return null;
    return [...orgs].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()).slice(0, 5);
  }, [orgs]);

  const statusSummary = useMemo(() => {
    if (!orgs) return null;
    const counts: Record<(typeof STATUS_BAR_KEYS)[number], number> = { active: 0, suspended: 0, inactive: 0, archived: 0 };
    for (const org of orgs) {
      if (org.status in counts) counts[org.status as (typeof STATUS_BAR_KEYS)[number]] += 1;
    }
    return { counts, total: orgs.length };
  }, [orgs]);

  const fullError = orgsError && (!canReadAdmins || adminsError);

  const [passwordDialogOpen, setPasswordDialogOpen] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState(false);
  const [isSubmittingPassword, setIsSubmittingPassword] = useState(false);

  function closePasswordDialog() {
    setPasswordDialogOpen(false);
    setCurrentPassword(""); setNewPassword(""); setConfirmPassword("");
    setPasswordError(null); setPasswordSuccess(false);
  }

  async function handleChangePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPasswordError(null);
    if (newPassword !== confirmPassword) {
      setPasswordError(t("changePassword.errorMismatch"));
      return;
    }
    setIsSubmittingPassword(true);
    try {
      await changePlatformPassword(
        { current_password: currentPassword, new_password: newPassword, password_confirmation: confirmPassword },
        token,
      );
      setPasswordSuccess(true);
    } catch (caughtError) {
      const message = caughtError instanceof ApiClientError ? caughtError.message : t("changePassword.errorGeneric");
      setPasswordError(message || t("changePassword.errorGeneric"));
    } finally {
      setIsSubmittingPassword(false);
    }
  }

  const quickActions = [
    canCreateOrg && { key: "newOrg", href: "/platform/organizations", icon: icons.plus, label: t("quickActions.newOrg") },
    canReadAdmins && { key: "manageAdmins", href: "/platform/administrators", icon: icons.shield, label: t("quickActions.manageAdmins") },
    canReadOrgs && { key: "viewOrgs", href: "/platform/organizations", icon: icons.list, label: t("quickActions.viewOrgs") },
    canReadAudit && { key: "auditLog", href: "/platform/audit-logs", icon: icons.clock, label: t("quickActions.auditLog") },
    canReadSecurityLog && { key: "securityLog", href: "/platform/security-log", icon: icons.key, label: t("quickActions.securityLog") },
    canReadActivityLog && { key: "activityLog", href: "/platform/activity-log", icon: icons.clock, label: t("quickActions.activityLog") },
    { key: "changePassword", onClick: () => setPasswordDialogOpen(true), icon: icons.key, label: t("quickActions.changePassword") },
  ].filter(Boolean) as Array<{ key: string; href?: string; onClick?: () => void; icon: ReactNode; label: string }>;

  const today = new Intl.DateTimeFormat(locale, { weekday: "long", year: "numeric", month: "long", day: "numeric" }).format(new Date());

  if (fullError) {
    return (
      <main className={css.page} dir={isRtl ? "rtl" : "ltr"}>
        <div className={css.shell}>
          <div className={css.fullError}>
            {icons.building}
            <h2>{t("errorTitle")}</h2>
            <p>{t("errorMessage")}</p>
            <button type="button" className={css.secondaryLink} onClick={() => { loadOrgs(); loadAdmins(); }}>{t("retryButton")}</button>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className={css.page} dir={isRtl ? "rtl" : "ltr"} aria-busy={orgs === null && admins === null} aria-label={orgs === null && admins === null ? t("loading") : undefined}>
      <div className={css.shell}>
        <header className={css.header}>
          <div>
            <p className={css.eyebrow}>{t("subtitle")}</p>
            <h1 className={css.title}>
              {t("welcome", { name: account?.full_name ?? "" })}
              <span className={`${css.roleBadge} ${isRoot ? css.roleBadge_root : css.roleBadge_admin}`}>
                {isRoot ? t("roleBadge.root") : t("roleBadge.admin")}
              </span>
            </h1>
            <p className={css.today}>{t("today")}: {today}</p>
          </div>
          <div className={css.headerActions}>
            <LanguageSwitcher label={t("languageSwitcher")} />
          </div>
        </header>

        <section className={css.kpis} aria-label={t("subtitle")}>
          <Link href="/platform/organizations" className={css.kpi}>
            <span className={`${css.kpiIcon} ${css.kpiIcon_total}`}>{icons.building}</span>
            <span>{orgsError ? <strong>—</strong> : totalOrgs === null ? <span className={`${css.skeleton} ${css.kpiSkeleton}`} style={{ display: "block", width: 40, height: 24 }} /> : <strong>{totalOrgs}</strong>}<small>{t("kpi.totalOrgs")}</small></span>
          </Link>
          <Link href="/platform/organizations?status=active" className={css.kpi}>
            <span className={`${css.kpiIcon} ${css.kpiIcon_active}`}>{icons.check}</span>
            <span>{orgsError ? <strong>—</strong> : activeOrgs === null ? <span className={`${css.skeleton} ${css.kpiSkeleton}`} style={{ display: "block", width: 40, height: 24 }} /> : <strong>{activeOrgs}</strong>}<small>{t("kpi.activeOrgs")}</small></span>
          </Link>
          <Link href="/platform/organizations?status=suspended" className={`${css.kpi} ${suspendedOrgs && suspendedOrgs > 0 ? css.kpi_attention : ""}`}>
            <span className={`${css.kpiIcon} ${css.kpiIcon_suspended}`}>{icons.pause}</span>
            <span>{orgsError ? <strong>—</strong> : suspendedOrgs === null ? <span className={`${css.skeleton} ${css.kpiSkeleton}`} style={{ display: "block", width: 40, height: 24 }} /> : <strong>{suspendedOrgs}</strong>}<small>{t("kpi.suspendedOrgs")}</small></span>
          </Link>
          {canReadAdmins ? (
            <Link href="/platform/administrators" className={css.kpi}>
              <span className={`${css.kpiIcon} ${css.kpiIcon_admins}`}>{icons.shield}</span>
              <span>
                {adminsError ? <strong>—</strong> : totalAdmins === null ? <span className={`${css.skeleton} ${css.kpiSkeleton}`} style={{ display: "block", width: 40, height: 24 }} /> : <strong>{totalAdmins}</strong>}
                <small>{t("kpi.platformAdmins")}</small>
                {!adminsError && activeAdmins !== null && <em>{t("kpi.activeAdmins", { count: activeAdmins })}</em>}
              </span>
            </Link>
          ) : null}
        </section>

        <div className={css.grid2}>
          {quickActions.length > 0 && (
            <section className={css.panel}>
              <div className={css.panelHeading}><span>{icons.list}</span><h2>{t("quickActions.title")}</h2></div>
              <div className={css.quickActions}>
                {quickActions.map((action) =>
                  action.href ? (
                    <Link key={action.key} href={action.href} className={css.actionButton}><span>{action.icon}</span>{action.label}</Link>
                  ) : (
                    <button key={action.key} type="button" className={css.actionButton} onClick={action.onClick}><span>{action.icon}</span>{action.label}</button>
                  ),
                )}
              </div>
            </section>
          )}

          <section className={css.panel}>
            <div className={css.panelHeading}><span>{icons.building}</span><h2>{t("recentOrgs.title")}</h2></div>
            {orgsError ? (
              <div className={css.panelError}>{t("errorMessage")}<button type="button" onClick={loadOrgs}>{t("retryButton")}</button></div>
            ) : recentOrgs === null ? (
              <div>{[0, 1, 2, 3, 4].map((key) => <div key={key} className={css.skeletonRow} />)}</div>
            ) : recentOrgs.length === 0 ? (
              <div className={css.emptyState}>
                <p>{t("recentOrgs.empty")}</p>
                {canCreateOrg && <Link href="/platform/organizations" className={css.secondaryLink}>{t("recentOrgs.createFirst")}</Link>}
              </div>
            ) : (
              <>
                <div className={css.orgList}>
                  {recentOrgs.map((org) => (
                    <Link key={org.id} href={`/platform/organizations/${org.id}`} className={css.orgRow}>
                      <OrgLogo organization={org} token={token} />
                      <span className={css.orgName}>{org.name}</span>
                      <span className={css.orgMeta}>
                        <span className={`${css.status} ${css[`status_${org.status}`]}`}><i />{t(`statusSummary.${org.status}`)}</span>
                        <span className={css.orgTime}>{t("recentOrgs.createdAgo", { time: relativeTime(org.created_at, locale) })}</span>
                      </span>
                    </Link>
                  ))}
                </div>
                <div className={css.panelFooter}><Link href="/platform/organizations">{t("recentOrgs.viewAll")}</Link></div>
              </>
            )}
          </section>
        </div>

        <div className={css.grid2}>
          <section className={css.panel}>
            <div className={css.panelHeading}><span>{icons.check}</span><h2>{t("statusSummary.title")}</h2></div>
            {orgsError ? (
              <div className={css.panelError}>{t("errorMessage")}<button type="button" onClick={loadOrgs}>{t("retryButton")}</button></div>
            ) : statusSummary === null ? (
              <div>{[0, 1, 2, 3].map((key) => <div key={key} className={css.skeletonRow} />)}</div>
            ) : statusSummary.total > 0 && statusSummary.counts.suspended === 0 && statusSummary.counts.inactive === 0 && statusSummary.counts.archived === 0 ? (
              <div className={css.allActive}>{icons.check}{t("statusSummary.allActive")}</div>
            ) : (
              <div className={css.statusBars}>
                {STATUS_BAR_KEYS.map((key) => {
                  const count = statusSummary.counts[key];
                  const percent = statusSummary.total > 0 ? Math.round((count / statusSummary.total) * 100) : 0;
                  return (
                    <div key={key} className={css.statusBarRow}>
                      <div className={css.statusBarLabel}><span>{t(`statusSummary.${key}`)}</span><span>{count} ({percent}%)</span></div>
                      <div className={css.statusBarTrack}><div className={css.statusBarFill} style={{ width: `${percent}%`, background: STATUS_COLOR[key] }} /></div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          {canReadAdmins && (
            <section className={css.panel}>
              <div className={css.panelHeading}><span>{icons.shield}</span><h2>{t("accounts.title")}</h2></div>
              {adminsError ? (
                <div className={css.panelError}>{t("errorMessage")}<button type="button" onClick={loadAdmins}>{t("retryButton")}</button></div>
              ) : admins === null ? (
                <div>{[0, 1, 2].map((key) => <div key={key} className={css.skeletonRow} />)}</div>
              ) : (
                <>
                  <div className={css.accountsList}>
                    {admins.map((item) => (
                      <div key={item.id} className={css.accountRow}>
                        <span className={css.avatar}>{initials(item.full_name)}</span>
                        <span className={css.accountName}>{item.full_name}</span>
                        <span className={css.accountMeta}>
                          <span className={`${css.roleBadge} ${item.role === "root" ? css.roleBadge_root : css.roleBadge_admin}`}>{t(`accounts.${item.role}`)}</span>
                          <span className={`${css.statusDot} ${item.status === "active" ? css.statusDot_active : css.statusDot_inactive}`}><i />{t(`accounts.${item.status}`)}</span>
                        </span>
                      </div>
                    ))}
                  </div>
                  <div className={css.panelFooter}><Link href="/platform/administrators">{t("accounts.manage")}</Link></div>
                </>
              )}
            </section>
          )}
        </div>

        <section className={css.panel}>
          <div className={css.panelHeading}><span>{icons.clock}</span><h2>{t("systemInfo.title")}</h2></div>
          <div className={css.infoGrid}>
            <div><dt>{t("systemInfo.platform")}</dt><dd>IORP</dd></div>
            <div><dt>{t("systemInfo.version")}</dt><dd>v0.1</dd></div>
            <div><dt>{t("systemInfo.initialized")}</dt><dd>—</dd></div>
            <div><dt>{t("systemInfo.totalOrgs")}</dt><dd>{totalOrgs ?? "—"}</dd></div>
            {canReadAdmins && <div><dt>{t("systemInfo.totalAdmins")}</dt><dd>{totalAdmins ?? "—"}</dd></div>}
          </div>
        </section>
      </div>

      {passwordDialogOpen && (
        <div className={css.dialogOverlay} role="dialog" aria-modal="true">
          <div className={css.dialog}>
            <h2>{t("quickActions.changePassword")}</h2>
            {passwordSuccess ? (
              <>
                <div className={css.formSuccess}>{t("changePassword.success")}</div>
                <div className={css.dialogActions}><button type="button" className={css.cancelButton} onClick={closePasswordDialog}>{t("changePassword.close")}</button></div>
              </>
            ) : (
              <form onSubmit={handleChangePassword}>
                <div className={css.dialogField}>
                  <label>{t("changePassword.currentPasswordLabel")}</label>
                  <PasswordInput autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} disabled={isSubmittingPassword} required />
                </div>
                <div className={css.dialogField}>
                  <label>{t("changePassword.newPasswordLabel")}</label>
                  <PasswordInput autoComplete="new-password" minLength={12} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} disabled={isSubmittingPassword} required />
                </div>
                <div className={css.dialogField}>
                  <label>{t("changePassword.confirmPasswordLabel")}</label>
                  <PasswordInput autoComplete="new-password" minLength={12} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} disabled={isSubmittingPassword} required />
                </div>
                {passwordError ? <div className={css.formError} role="alert">{passwordError}</div> : null}
                <div className={css.dialogActions}>
                  <button type="button" className={css.cancelButton} onClick={closePasswordDialog} disabled={isSubmittingPassword}>{t("changePassword.cancel")}</button>
                  <button type="submit" className={css.primaryButton} disabled={isSubmittingPassword}>{isSubmittingPassword ? t("changePassword.submitting") : t("changePassword.submitButton")}</button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </main>
  );
}

export function PlatformDashboardPage() {
  return (
    <PlatformProtectedRoute>
      <PlatformDashboardContent />
    </PlatformProtectedRoute>
  );
}
