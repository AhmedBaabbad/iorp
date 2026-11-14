"use client";

import Link from "next/link";
import { UserPresence } from "./UserPresence";
import { UserOffboarding } from "./UserOffboarding";
import { PermanentUserDelete } from "./PermanentUserDelete";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { useAuth, usePermission } from "@/features/auth";
import { useFormatter } from "@/hooks/useFormatter";
import { useNotify } from "@/components/notify/Notifications";
import { useEnumLabel } from "@/i18n/enum-helpers";
import { getApiErrorMessage } from "@/lib/api-error-handler";
import { sharedStyles } from "@/styles/shared-styles";
import {
  activateAdminUser,
  lockAdminUser,
  unlockAdminUser,
  getAdminUser,
  getAdminUserPresence,
  resetAdminUserPassword,
  getAdminUserSessions,
  endAdminUserSessions,
  type PasswordResetResult,
  type UserSession,
} from "../api/admin-users-api";
import type {
  AdminUserDetail as AdminUserDetailType,
} from "../types";
import { AdminUserRolesManager } from "./AdminUserRolesManager";
import { EffectiveAccessPanel } from "./EffectiveAccessPanel";
import css from "./admin-user-detail.module.css";

function initials(name: string): string {
  return name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]?.toUpperCase()).join("") || "?";
}

export function AdminUserDetail() {
  const params = useParams<{ id: string }>();
  const t = useTranslations("administration.users");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const notify = useNotify();
  const enumLabel = useEnumLabel();
  const {user:currentUser}=useAuth();
  const canActivate = usePermission("foundation:users:activate");
  const canDeactivate = usePermission("foundation:users:deactivate");
  const canLock = usePermission("foundation:users:lock");
  const canResetPassword = usePermission("foundation:users:reset_password");
  const [user, setUser] = useState<AdminUserDetailType | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const [resetResult, setResetResult] = useState<PasswordResetResult | null>(null);
  const [resetEmailFailed, setResetEmailFailed] = useState(false);
  const [sessions, setSessions] = useState<UserSession[] | null>(null);

  const load = useCallback(() => {
    getAdminUser(params.id).then(setUser).catch((caught) => setError(getApiErrorMessage(caught, messages)));
  }, [messages, params.id]);

  useEffect(() => {
    let live=true;
    const refresh=()=>{void getAdminUserPresence(params.id).then(next=>{
      if(live)setUser(current=>current?.id===params.id?{...current,last_seen_at:next.last_seen_at,is_online:next.is_online}:current);
    }).catch(()=>{});};
    load();
    let timer:ReturnType<typeof setInterval>|undefined;
    const visibility=()=>{if(timer)clearInterval(timer);timer=undefined;if(!document.hidden)timer=setInterval(refresh,60000);};
    const resume=()=>{visibility();if(!document.hidden)refresh();};
    visibility();document.addEventListener("visibilitychange",resume);
    return()=>{live=false;if(timer)clearInterval(timer);document.removeEventListener("visibilitychange",resume);};
  }, [load,params.id]);

  const showOffboarding=!!user&&!!currentUser&&canDeactivate&&!user.is_organization_root&&user.id!==currentUser.id&&user.delete_block?.code!=="USER_DELETE_SELF";
  function openOffboarding(){document.getElementById("user-offboarding")?.scrollIntoView({behavior:"smooth",block:"start"});}
  useEffect(()=>{if(showOffboarding&&new URLSearchParams(window.location.search).get("deactivate")==="1"){
    window.history.replaceState(null,"",window.location.pathname);document.getElementById("user-offboarding")?.scrollIntoView({behavior:"smooth",block:"start"});
  }},[showOffboarding]);

  async function handlePasswordReset() {
    if (!user) return;
    setIsSubmitting(true); setError(null); setResetEmailFailed(false);
    try {
      const result = await resetAdminUserPassword(user.id);
      setResetResult(result);
      notify.success(t("passwordReset.linkSent", { email: result.email }));
    } catch (caught) {
      const code = (caught as { details?: { detail?: { code?: string } } })?.details?.detail?.code;
      if (code === "RESET_EMAIL_NOT_SENT") setResetEmailFailed(true);
      else setError(getApiErrorMessage(caught, messages));
    } finally { setIsSubmitting(false); }
  }

  function closeReset() { setResetOpen(false); setResetResult(null); setResetEmailFailed(false); }

  async function endSessions() {
    if (!user || !window.confirm(t("sessions.confirmEnd", { name: user.full_name }))) return;
    try {
      const done = await endAdminUserSessions(user.id);
      notify.success(t("sessions.ended", { count: done.ended }));
      setSessions(await getAdminUserSessions(user.id));
    } catch (caught) { setError(getApiErrorMessage(caught, messages)); }
  }

  async function handleStatusAction(kind: "lock" | "unlock" | "activate") {
    const reason = window.prompt(t("accountPolicy.reason"));
    if (!reason || reason.trim().length < 3) return;
    const translationGroup = kind === "activate" ? "reactivation" : kind;
    if (!user || !window.confirm(t(`${translationGroup}.confirmMessage`, { name: user.full_name }))) return;
    setIsSubmitting(true);
    try {
      if (kind === "lock") await lockAdminUser(user.id, reason);
      else if (kind === "unlock") await unlockAdminUser(user.id, reason);
      else await activateAdminUser(user.id, reason);
      await load();
    } catch (caught) { setError(getApiErrorMessage(caught, messages)); }
    finally { setIsSubmitting(false); }
  }


  return (
    <PageFrame
      section={t("section")}
      title={t("detailTitle")}
    >
      {resetOpen && user ? <div style={sharedStyles.modalOverlay}><section style={sharedStyles.modal} role="dialog" aria-modal="true" aria-labelledby="reset-password-title">
        <h2 id="reset-password-title" style={sharedStyles.modalTitle}>{t("passwordReset.title")}</h2>
        {resetResult ? <>
          <p>{t("passwordReset.linkSent", { email: resetResult.email })}</p>
          <div style={sharedStyles.modalActions}><button type="button" style={sharedStyles.button} onClick={closeReset}>{t("passwordReset.done")}</button></div>
        </> : <>
          <p>{user.activation_pending ? t("invitation.resendDescription", { name: user.full_name }) : t("passwordReset.description", { name: user.full_name })}</p>
          {resetEmailFailed && <p role="alert" style={{ color: "var(--danger)" }}>{t("passwordReset.emailFailed")}</p>}
          <div style={sharedStyles.modalActions}>
            <button type="button" style={sharedStyles.secondaryButton} onClick={closeReset}>{t("passwordReset.cancel")}</button>
            <button type="button" style={sharedStyles.button} disabled={isSubmitting} onClick={() => void handlePasswordReset()}>{isSubmitting ? t("passwordReset.submitting") : t("passwordReset.sendLink")}</button></div>
        </>}
      </section></div> : null}
      {error ? <div style={sharedStyles.error} role="alert">{error}</div> : null}
      {!user ? <div className={css.loading}>{t("loadingDetail")}</div> : (
        <div className={css.page}>
          <section className={css.hero}>
            <div className={css.heroContent}>
              <div className={css.identity}>
                <div className={css.avatar} aria-hidden="true">{initials(user.full_name)}</div>
                <div className={css.identityText}>
                  <p className={css.eyebrow}>{user.is_organization_root ? t("organizationRoot") : t("detailTitle")}</p>
                  <h1 className={css.name}>{user.full_name}</h1>
                  <a className={css.email} href={`mailto:${user.email}`}>{user.email}</a>
                  <div className={css.badges}>
                    <span className={css.badge}><UserPresence user={user}/></span>
                    <span className={`${css.badge} ${user.status === "active" ? css.badgeActive : user.status === "locked" ? css.badgeLocked : css.badgeInactive}`}>{enumLabel("user", "status", user.status)}</span>
                    {user.is_organization_root ? <span className={css.badge}>{t("rootBadge")}</span> : null}
                    {user.activation_pending ? <span className={`${css.badge} ${css.badgeLocked}`}>{t("invitation.pending")}</span> : null}
                  </div>
                </div>
              </div>
              <div className={css.heroActions}>
                {canResetPassword && !user.is_organization_root ? <button type="button" className={css.heroButton} onClick={() => setResetOpen(true)}>{user.activation_pending ? t("invitation.resend") : t("passwordReset.open")}</button> : null}
                {user.status === "active" && !user.is_organization_root && canLock ? <button className={css.heroButton} onClick={() => void handleStatusAction("lock")}>{t("actions.lock")}</button> : null}
                {user.status === "locked" && !user.is_organization_root && canLock ? <button className={css.heroButton} onClick={() => void handleStatusAction("unlock")}>{t("actions.unlock")}</button> : null}
                {user.status === "inactive" && !user.archived_at && !user.is_organization_root && canActivate ? <button className={css.heroButton} onClick={() => void handleStatusAction("activate")}>{t("actions.reactivate")}</button> : null}
                <PermanentUserDelete user={user} showBlock className={css.heroButtonDanger} onDeactivate={showOffboarding?openOffboarding:undefined}/>
                {showOffboarding?<button type="button" className={css.heroButtonDanger} onClick={openOffboarding}>{t("offboarding.title")}</button>:null}
              </div>
            </div>
          </section>

          {user.is_organization_root ? <section className={css.rootNotice} role="note"><div className={css.rootIcon}>R</div><div><strong>{t("rootProtectionNotice")}</strong><p>{t("rootFieldsLocked")}</p></div></section> : null}

          <section className={css.metrics} aria-label={t("overview.title")}>
            <div className={css.metric}><span className={css.metricLabel}>{t("fields.status")}</span><strong className={css.metricValue}>{enumLabel("user", "status", user.status)}</strong></div>
            <div className={css.metric}><span className={css.metricLabel}>{t("fields.roles")}</span><strong className={css.metricValue}>{user.roles.length}</strong></div>
            <div className={css.metric}><span className={css.metricLabel}>{t("fields.permissions")}</span><strong className={css.metricValue}>{user.permissions.length}</strong></div>
            <div className={css.metric}><span className={css.metricLabel}>{t("fields.createdAt")}</span><strong className={css.metricValue}>{fmt.date(user.created_at)}</strong></div>
          </section>

          {showOffboarding&&<UserOffboarding user={user} onChanged={setUser} onReload={load}/>}

          <div className={css.layout}>
            <div className={css.mainColumn}>
              <section className={css.card}>
                <header className={css.cardHeader}><div><h2 className={css.cardTitle}>{t("overview.title")}</h2><p className={css.cardSubtitle}>{t("overview.subtitle")}</p></div></header>
                <dl className={css.detailsGrid}>
                  <div className={css.detail}><dt>{t("fields.email")}</dt><dd>{user.email}</dd></div>
                  <div className={css.detail}><dt>{t("fields.phone")}</dt><dd>{user.phone ?? t("notAvailable")}</dd></div>
                  <div className={css.detail}><dt>{t("overview.preferredLanguage")}</dt><dd>{user.preferred_locale ? t(`overview.locales.${user.preferred_locale}`) : t("overview.organizationDefault")}</dd></div>
                  <div className={css.detail}><dt>{t("presence.lastSeenAt")}</dt><dd>{user.last_seen_at?fmt.dateTime(user.last_seen_at):t("presence.never")}</dd></div>
                  <div className={css.detail}><dt>{t("fields.lastLoginAt")}</dt><dd>{user.last_login_at ? fmt.dateTime(user.last_login_at) : t("overview.neverLoggedIn")}</dd></div>
                  <div className={css.detail}><dt>{t("fields.createdAt")}</dt><dd>{fmt.dateTime(user.created_at)}</dd></div>
                  <div className={css.detail}><dt>{t("overview.updatedAt")}</dt><dd>{fmt.dateTime(user.updated_at)}</dd></div>
                </dl>
              </section>

              <section className={css.card}><h2>{t("accountPolicy.title")}</h2><p>{t("accountPolicy.ownerOnly")}</p><p>{t("accountPolicy.timezone")}: {user.timezone ?? "—"}</p>{user.archived_at ? <p>{t("accountPolicy.archived")}: {fmt.dateTime(user.archived_at)}</p> : null}{user.account_change_reason ? <p>{t("accountPolicy.reason")}: {user.account_change_reason}</p> : null}</section>
              <AdminUserRolesManager userId={user.id} userName={user.full_name} isOrganizationRoot={user.is_organization_root} assignedRoles={user.roles} onChanged={load} />

              <EffectiveAccessPanel userId={user.id} />


            </div>

            <aside className={css.sideColumn}>
              <section className={css.card}>
                <header className={css.cardHeader}><div><h2 className={css.cardTitle}>{t("loginProtection.title")}</h2><p className={css.cardSubtitle}>{t("overview.securitySubtitle")}</p></div></header>
                <div className={`${css.securityState} ${user.auto_locked_until ? css.securityStateWarn : ""}`}><span className={css.securityDot} />{user.is_organization_root ? t("loginProtection.rootExempt") : user.auto_locked_until ? t("loginProtection.currentlyLocked") : t("loginProtection.noIssues")}</div>
                <div className={css.securityStats}>
                  <div className={css.securityStat}><span>{t("loginProtection.failedAttempts")}</span><strong>{user.failed_login_attempts}</strong></div>
                  <div className={css.securityStat}><span>{t("loginProtection.autoLockedUntil")}</span><strong>{user.auto_locked_until ? fmt.dateTime(user.auto_locked_until) : t("loginProtection.notLocked")}</strong></div>
                  <div className={css.securityStat}><span>{t("loginProtection.lastFailedAt")}</span><strong>{user.last_failed_login_at ? fmt.dateTime(user.last_failed_login_at) : t("loginProtection.none")}</strong></div>
                </div>
                {user.auto_locked_until && canLock && !user.is_organization_root ? <button style={{ ...sharedStyles.secondaryButton, marginTop: 18, width: "100%" }} onClick={() => void handleStatusAction("unlock")}>{t("loginProtection.clearLock")}</button> : null}
              </section>
              {canLock && !user.is_organization_root ? <section className={css.card}>
                <header className={css.cardHeader}><div><h2 className={css.cardTitle}>{t("sessions.title")}</h2><p className={css.cardSubtitle}>{t("sessions.subtitle")}</p></div></header>
                {sessions === null ? <button type="button" style={{ ...sharedStyles.secondaryButton, width: "100%" }}
                  onClick={() => void getAdminUserSessions(user.id).then(setSessions).catch(caught => setError(getApiErrorMessage(caught, messages)))}>{t("sessions.show")}</button>
                  : sessions.length === 0 ? <p className={css.cardSubtitle}>{t("sessions.none")}</p>
                  : <>{sessions.map(x => <div key={x.id} style={{ padding: "8px 0", borderTop: "1px solid var(--border)" }}>
                      <strong>{x.device}</strong><div style={{ color: "var(--text-muted)", fontSize: 12 }}>{x.ip_address ?? "—"} · {t("sessions.since", { date: fmt.dateTime(x.started_at) })} · {t("sessions.lastActive", { date: fmt.dateTime(x.last_active_at) })}</div></div>)}
                    <button type="button" style={{ ...sharedStyles.secondaryButton, marginTop: 12, width: "100%" }} onClick={() => void endSessions()}>{t("sessions.endAll")}</button></>}
              </section> : null}
            </aside>
          </div>
          <Link href="/admin/users" className={css.back}>← {t("backToList")}</Link>
        </div>
      )}
    </PageFrame>
  );
}
