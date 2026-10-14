"use client";
/* eslint-disable @next/next/no-img-element -- the logo is an authenticated blob URL. */

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useParams, useSearchParams } from "next/navigation";
import type { FormEvent, ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { API_BASE_URL, ApiClientError } from "@/lib/api-client";
import type { OrganizationLifecycleAction, OrganizationLifecycleStatus, PlatformOrganizationDetail } from "@/types/platform";
import { changeOrganizationStatus, getPlatformOrganization, resetOrganizationRootPassword } from "./platform-api";
import { usePlatformAuth } from "./platform-auth-context";
import { PlatformProtectedRoute } from "./platform-protected-route";
import css from "./platform-organization-detail-page.module.css";

const actionForTarget: Partial<Record<OrganizationLifecycleStatus, OrganizationLifecycleAction>> = {
  active: "activate", suspended: "suspend", inactive: "deactivate", archived: "archive",
};

function Icon({ children, size = 21 }: { children: ReactNode; size?: number }) {
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{children}</svg>;
}

const icons = {
  users: <Icon><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></Icon>,
  shield: <Icon><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/></Icon>,
  clock: <Icon><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></Icon>,
  status: <Icon><circle cx="12" cy="12" r="9"/><path d="m8 12 2.5 2.5L16 9"/></Icon>,
  alert: <Icon size={32}><path d="M10.3 3.7 2.4 18a2 2 0 0 0 1.8 3h15.6a2 2 0 0 0 1.8-3L13.7 3.7a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/></Icon>,
  search: <Icon size={32}><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4M8 8l6 6M14 8l-6 6"/></Icon>,
};

function initials(value: string) {
  return value.trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
}

function identityColor(value: string) {
  const colors = ["#2563eb", "#7c3aed", "#0891b2", "#059669", "#c2410c", "#be185d"]; // theme-exempt: logo fallback palette, white initials read on each
  return colors[[...value].reduce((sum, character) => sum + character.charCodeAt(0), 0) % colors.length];
}

function OrganizationLogo({ organization, token, alt }: { organization: PlatformOrganizationDetail; token?: string | null; alt: string }) {
  const [source, setSource] = useState("");
  useEffect(() => {
    if (!organization.has_logo || !organization.logo_url || !token) return;
    let objectUrl = "";
    fetch(`${API_BASE_URL.replace(/\/$/, "")}${organization.logo_url}`, { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => response.ok ? response.blob() : Promise.reject())
      .then((blob) => { objectUrl = URL.createObjectURL(blob); setSource(objectUrl); })
      .catch(() => setSource(""));
    return () => { if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [organization.has_logo, organization.logo_url, token]);
  return source
    ? <img className={css.logo} src={source} alt={alt} />
    : <span className={css.logoFallback} style={{ backgroundColor: identityColor(organization.name) }}>{initials(organization.name)}</span>;
}

function DetailSkeleton({ label }: { label: string }) {
  return <div className={css.skeleton} aria-label={label}>
    <div className={css.skeletonHeader}><i /><span><b /><b /></span></div>
    <div className={css.skeletonStats}>{Array.from({ length: 4 }, (_, index) => <i key={index} />)}</div>
    {Array.from({ length: 3 }, (_, section) => <div className={css.skeletonSection} key={section}>{Array.from({ length: 4 }, (_, row) => <i key={row} />)}</div>)}
  </div>;
}

function Content() {
  const t = useTranslations("platform.organizationDetail");
  const locale = useLocale();
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const { account, token } = usePlatformAuth();
  const isRtl = locale === "ar";
  const isRoot = account?.role === "root";
  const [organization, setOrganization] = useState<PlatformOrganizationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadState, setLoadState] = useState<"ok" | "error" | "notFound">("ok");
  const [notice, setNotice] = useState("");
  const [action, setAction] = useState<OrganizationLifecycleAction | null>(null);
  const [reason, setReason] = useState("");
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showReset, setShowReset] = useState(false);
  const [resetError, setResetError] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setLoadState("ok");
    try { setOrganization(await getPlatformOrganization(id, token)); }
    catch (error) { setLoadState(error instanceof ApiClientError && error.status === 404 ? "notFound" : "error"); }
    finally { setLoading(false); }
  }, [id, token]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (searchParams.get("created") !== "1") return;
    // SEC-003: the root chooses their own password through the e-mailed activation link
    setNotice(`${t("createdSuccess")} ${searchParams.get("invited") === "0" ? t("root.invitationNotSent") : t("root.invitationSent")}`);
  }, [searchParams, t]);

  const actions = useMemo(() => (organization?.allowed_transitions ?? [])
    .map((target) => actionForTarget[target])
    .filter((value): value is OrganizationLifecycleAction => Boolean(value)), [organization]);

  const formatDate = (value: string | null | undefined, withTime = true) => value
    ? new Intl.DateTimeFormat(locale, withTime ? { dateStyle: "medium", timeStyle: "short" } : { dateStyle: "medium" }).format(new Date(value))
    : t("notAvailable");

  const relativeTime = (value: string | null | undefined) => {
    if (!value) return t("stats.noActivity");
    const delta = new Date(value).getTime() - Date.now();
    const units: Array<[Intl.RelativeTimeFormatUnit, number]> = [["year", 31536000000], ["month", 2592000000], ["day", 86400000], ["hour", 3600000], ["minute", 60000]];
    const [unit, size] = units.find(([, milliseconds]) => Math.abs(delta) >= milliseconds) ?? ["minute", 60000];
    return new Intl.RelativeTimeFormat(locale, { numeric: "auto" }).format(Math.round(delta / size), unit);
  };

  async function applyStatus(event: FormEvent) {
    event.preventDefault();
    if (!action || !organization || !isRoot) return;
    if (action === "archive" && !reason.trim()) { setActionError(t("reasonRequired")); return; }
    setBusy(true); setActionError("");
    try { await changeOrganizationStatus(id, action, reason.trim() || null, token); setAction(null); setReason(""); setNotice(t("changeSuccess")); await load(); }
    catch { setActionError(t("changeError")); }
    finally { setBusy(false); }
  }

  async function applyReset(event: FormEvent) {
    event.preventDefault();
    if (!isRoot) return;
    setBusy(true); setResetError("");
    try {
      await resetOrganizationRootPassword(id, token);
      setShowReset(false); setNotice(t("root.resetSuccess", { email: organization?.root_user?.email ?? "" }));
    } catch { setResetError(t("resetError")); }
    finally { setBusy(false); }
  }

  const actionButtons = (compact = false) => isRoot && actions.length > 0 ? <div className={compact ? css.lifecycleActions : css.topActions}>
    {actions.map((item) => <button type="button" key={item} className={`${css.actionButton} ${css[`action_${item}`]}`} onClick={() => { setActionError(""); setAction(item); }}>{t(`actions.${item}`)}</button>)}
  </div> : null;

  return <main className={css.page} dir={isRtl ? "rtl" : "ltr"}>
    <div className={css.shell}>
      <nav className={css.topbar}>
        <Link href="/platform/organizations" className={css.backLink}><span>{isRtl ? "→" : "←"}</span>{t("backToList")}</Link>
        <div className={css.topbarEnd}><LanguageSwitcher label={t("languageLabel")} />{organization && actionButtons()}</div>
      </nav>

      {notice && <div className={css.toast} role="status"><span>{notice}</span><button type="button" onClick={() => setNotice("")} aria-label={t("dismiss")}>×</button></div>}

      {loading ? <DetailSkeleton label={t("loading")} />
      : loadState !== "ok" || !organization ? <section className={css.state}>
        <span>{loadState === "notFound" ? icons.search : icons.alert}</span>
        <h1>{t(loadState === "notFound" ? "notFoundTitle" : "errorTitle")}</h1>
        <p>{t(loadState === "notFound" ? "notFoundMessage" : "errorMessage")}</p>
        {loadState === "notFound" ? <Link className={css.primaryLink} href="/platform/organizations">{t("backToList")}</Link> : <button className={css.primaryButton} type="button" onClick={load}>{t("retryButton")}</button>}
      </section>
      : <>
        <header className={css.identityPanel}>
          <OrganizationLogo organization={organization} token={token} alt={t("logoAlt", { name: organization.name })} />
          <div className={css.identityText}><p>{t("pageTitle")}</p><h1>{organization.name}</h1><div className={css.identityMeta}><code>{organization.code}</code><span className={`${css.statusBadge} ${css[`status_${organization.status}`]}`}><i />{t(`statuses.${organization.status}`)}</span><span>{t("createdLabel", { date: formatDate(organization.created_at, false) })}</span></div></div>
        </header>

        <section className={css.stats} aria-label={t("sections.stats")}>
          <article><span className={css.statUsers}>{icons.users}</span><div><strong>{organization.user_count ?? "—"}</strong><small>{t("stats.users")}</small></div></article>
          <article><span className={css.statRoles}>{icons.shield}</span><div><strong>{organization.roles?.length ?? "—"}</strong><small>{t("stats.roles")}</small></div></article>
          <article><span className={`${css.statStatus} ${css[`stat_${organization.status}`]}`}>{icons.status}</span><div><strong>{t(`statuses.${organization.status}`)}</strong><small>{t("stats.status")}</small></div></article>
          <article><span className={css.statActivity}>{icons.clock}</span><div><strong>{relativeTime(organization.root_user?.last_login_at)}</strong><small>{t("stats.lastActivity")}</small></div></article>
        </section>

        <section className={css.panel}><div className={css.sectionHeading}><span>{icons.shield}</span><div><p>{t("sectionEyebrow")}</p><h2>{t("sections.orgInfo")}</h2></div></div><dl className={css.infoGrid}>
          <div><dt>{t("fields.name")}</dt><dd>{organization.name}</dd></div>
          <div><dt>{t("fields.code")}</dt><dd><code>{organization.code}</code></dd></div>
          <div><dt>{t("fields.industry")}</dt><dd>{organization.industry_type ?? t("notAvailable")}</dd></div>
          <div><dt>{t("fields.timezone")}</dt><dd>{organization.timezone}</dd></div>
          <div><dt>{t("fields.language")}</dt><dd>{t(`locales.${organization.default_locale}`)}</dd></div>
          <div><dt>{t("fields.createdAt")}</dt><dd>{formatDate(organization.created_at)}</dd></div>
          <div><dt>{t("fields.updatedAt")}</dt><dd>{formatDate(organization.updated_at)}</dd></div>
        </dl></section>

        <section className={css.panel}><div className={css.sectionHeading}><span>{icons.users}</span><div><p>{t("sectionEyebrow")}</p><h2>{t("sections.rootAccount")}</h2></div></div>
          {organization.root_user ? <div className={css.rootCard}><span className={css.avatar} style={{ backgroundColor: identityColor(organization.root_user.full_name) }}>{initials(organization.root_user.full_name)}</span><div className={css.rootIdentity}><h3>{organization.root_user.full_name}</h3><a href={`mailto:${organization.root_user.email}`}>{organization.root_user.email}</a></div><dl><div><dt>{t("root.status")}</dt><dd><span className={`${css.statusBadge} ${css.status_active}`}><i />{t(`userStatuses.${organization.root_user.status}`)}</span></dd></div><div><dt>{t("root.lastLogin")}</dt><dd>{organization.root_user.last_login_at ? formatDate(organization.root_user.last_login_at) : t("root.neverLoggedIn")}</dd></div></dl>{organization.root_user.activation_pending ? <p className={css.muted}>{t("root.activationPending")}</p> : null}{isRoot && <button className={css.secondaryButton} type="button" onClick={() => setShowReset(true)}>{organization.root_user.activation_pending ? t("root.resendActivation") : t("root.resetPassword")}</button>}</div> : <p className={css.muted}>{t("root.missing")}</p>}
          <p className={css.protectedNotice}>{icons.shield}<span>{t("root.protectedNotice")}</span></p>
        </section>

        <section className={css.panel}><div className={css.sectionHeading}><span>{icons.clock}</span><div><p>{t("sectionEyebrow")}</p><h2>{t("sections.lifecycle")}</h2></div></div>
          <div className={css.lifecycleCurrent}><span>{t("lifecycle.currentStatus")}</span><strong className={`${css.statusBadge} ${css[`status_${organization.status}`]}`}><i />{t(`statuses.${organization.status}`)}</strong></div>
          {organization.status_changed_at ? <div className={css.changeRecord}><p>{t("lifecycle.lastChange")}</p><strong>{t("lifecycle.changeSummary", { date: formatDate(organization.status_changed_at), who: organization.status_changed_by_name ?? organization.status_changed_by ?? t("lifecycle.unknownActor") })}</strong>{organization.status_change_reason && <blockquote>{t("lifecycle.reasonValue", { reason: organization.status_change_reason })}</blockquote>}</div> : <p className={css.muted}>{t("lifecycle.noChanges")}</p>}
          {organization.status === "archived" ? <p className={css.archivedNotice}>{t("lifecycle.archivedNotice")}</p> : isRoot ? <div className={css.availableActions}><h3>{t("lifecycle.availableActions")}</h3>{actions.length ? actionButtons(true) : <p>{t("lifecycle.noActions")}</p>}</div> : <p className={css.readOnly}>{t("lifecycle.readOnly")}</p>}
        </section>
      </>}
    </div>

    {action && organization && <div className={css.overlay}><form className={css.dialog} onSubmit={applyStatus}><span className={`${css.dialogIcon} ${css[`action_${action}`]}`}>{action === "activate" ? icons.status : icons.alert}</span><h2>{t(`confirm.${action}.title`)}</h2><p>{t(`confirm.${action}.message`, { name: organization.name })}</p>{(action === "suspend" || action === "archive") && <p className={css.dialogWarning}>{t(`confirm.${action}.warning`)}</p>}<label><span>{t("reasonLabel")}</span><textarea value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500} required={action === "archive"} rows={3} /></label>{actionError && <p className={css.formError}>{actionError}</p>}<div className={css.dialogActions}><button type="button" className={css.cancelButton} onClick={() => { setAction(null); setReason(""); }}>{t("cancel")}</button><button className={`${css.actionButton} ${css[`action_${action}`]}`} disabled={busy}>{busy ? t("processing") : t(`confirm.${action}.button`)}</button></div></form></div>}

    {showReset && organization && <div className={css.overlay}><form className={css.dialog} onSubmit={applyReset}><span className={css.dialogIcon}>{icons.shield}</span><h2>{t("root.resetPasswordTitle")}</h2><p>{t("root.resetPasswordMessage", { orgName: organization.name, email: organization.root_user?.email ?? "" })}</p><p className={css.dialogWarning}>{t("root.sessionsNotice")}</p>{resetError && <p className={css.formError}>{resetError}</p>}<div className={css.dialogActions}><button type="button" className={css.cancelButton} onClick={() => setShowReset(false)}>{t("cancel")}</button><button className={css.dangerButton} disabled={busy}>{busy ? t("root.resetting") : t("root.resetPassword")}</button></div></form></div>}
  </main>;
}

export function PlatformOrganizationDetailPage() {
  return <PlatformProtectedRoute><Content /></PlatformProtectedRoute>;
}
