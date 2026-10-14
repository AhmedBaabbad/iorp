"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { type FormEvent, type ReactNode, useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { useFormatter } from "@/hooks/useFormatter";
import { LOCALE_COOKIE_NAME } from "@/i18n/config";
import { updateMyProfile } from "./auth-client";
import { useAuth } from "./auth-context";
import { EffectiveAccessPanel } from "@/features/admin-users/components/EffectiveAccessPanel";
import { EmailChangeForm } from "./email-change-form";
import css from "./my-profile-page.module.css";

function Icon({ children }: { children: ReactNode }) {
  return <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{children}</svg>;
}

const icons = {
  user: <Icon><path d="M20 21a8 8 0 0 0-16 0"/><circle cx="12" cy="7" r="4"/></Icon>,
  building: <Icon><rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 7h2m4 0h2M8 11h2m4 0h2M9 21v-5h6v5"/></Icon>,
  shield: <Icon><path d="M12 3 20 6v5c0 5-3.4 8.5-8 10-4.6-1.5-8-5-8-10V6l8-3Z"/><path d="m9 12 2 2 4-4"/></Icon>,
  calendar: <Icon><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></Icon>,
  clock: <Icon><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></Icon>,
  edit: <Icon><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z"/></Icon>,
  lock: <Icon><rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></Icon>,
  globe: <Icon><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></Icon>,
  key: <Icon><circle cx="8" cy="15" r="4"/><path d="m11 12 8-8m-3 1 3 3"/></Icon>,
};

function initials(name: string) {
  return name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
}

export function MyProfilePage() {
  const t = useTranslations("profile");
  const currentLocale = useLocale();
  const { user, refreshCurrentUser } = useAuth();
  const format = useFormatter();
  const [fullName, setFullName] = useState("");
  const [timezone, setTimezone] = useState("");
  const [phone, setPhone] = useState("");
  const [preferredLocale, setPreferredLocale] = useState<"" | "ar" | "en">("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (!user) return;
    setFullName(user.full_name);
    setTimezone(user.timezone ?? "");
    setPhone(user.phone ?? "");
    setPreferredLocale(user.preferred_locale ?? "");
  }, [user]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true); setError(false); setSuccess(false);
    try {
      const updated = await updateMyProfile({
        full_name: user?.is_organization_root ? undefined : fullName,
        phone: phone || null,
        timezone: timezone || null,
        preferred_locale: preferredLocale || null,
      });
      setSuccess(true);
      if (updated.effective_locale && updated.effective_locale !== currentLocale) {
        document.cookie = `${LOCALE_COOKIE_NAME}=${updated.effective_locale}; path=/; max-age=31536000; SameSite=Lax`;
        document.documentElement.lang = updated.effective_locale;
        document.documentElement.dir = updated.effective_locale === "ar" ? "rtl" : "ltr";
        await refreshCurrentUser(); window.location.reload(); return;
      }
      await refreshCurrentUser();
    } catch { setError(true); }
    finally { setSaving(false); }
  }

  if (!user) return null;
  const role = user.is_organization_root ? t("rootRole") : user.roles[0] ?? t("noRole");
  const statusClass = user.status === "active" ? css.active : user.status === "locked" ? css.locked : css.inactive;

  return (
    <PageFrame section={t("myProfile")} title={t("title")} subtitle={t("subtitle")}>
      <div className={css.profilePage}>
        <section className={css.hero}>
          <div className={css.heroGlow} />
          <div className={css.avatarWrap}><div className={css.avatar}>{initials(user.full_name)}</div><span className={`${css.presence} ${statusClass}`} /></div>
          <div className={css.heroIdentity}>
            <div className={css.nameRow}><h2>{user.full_name}</h2><span className={`${css.statusBadge} ${statusClass}`}>{t(`statuses.${user.status}`)}</span></div>
            <p className={css.email}>{user.email}</p>
            <div className={css.heroTags}><span>{icons.shield}{role}</span><span>{icons.building}{user.organization.name}</span></div>
          </div>
          <div className={css.heroAside}><span>{t("profileCompletion")}</span><strong>{t("profileReady")}</strong><div className={css.progress}><i /></div></div>
        </section>

        <div className={css.contentGrid}>
          <div className={css.mainColumn}>
            <section className={css.card}>
              <div className={css.cardHeader}><span className={css.cardIcon}>{icons.user}</span><div><h2>{t("identitySection")}</h2><p>{t("identityReadOnlyNote")}</p></div></div>
              <dl className={css.infoGrid}>
                <div><span className={css.infoIcon}>{icons.building}</span><dt>{t("fields.organization")}</dt><dd>{user.organization.name}<small>{user.organization.code}</small></dd></div>
                <div><span className={css.infoIcon}>{icons.shield}</span><dt>{t("fields.role")}</dt><dd>{role}</dd></div>
                <div><span className={css.infoIcon}>{icons.calendar}</span><dt>{t("fields.memberSince")}</dt><dd>{format.date(user.created_at)}</dd></div>
                <div><span className={css.infoIcon}>{icons.clock}</span><dt>{t("fields.lastLogin")}</dt><dd>{user.last_login_at ? format.dateTime(user.last_login_at) : t("notAvailable")}</dd></div>
              </dl>
            </section>

            <section className={css.card}>
              <div className={css.cardHeader}><span className={css.cardIcon}>{icons.edit}</span><div><h2>{t("profileSection")}</h2><p>{t("personalDetailsNote")}</p></div></div>
              <form onSubmit={(event) => void submit(event)} className={css.form}>
                <div className={css.formGrid}>
                  <label><span>{t("fields.fullName")}</span><input value={fullName} onChange={(event) => setFullName(event.target.value)} disabled={user.is_organization_root} required />{user.is_organization_root ? <small>{t("rootNameLocked")}</small> : null}</label>
                  <label><span>{t("fields.email")}</span><input value={user.email} disabled /><small>{t("emailReadOnly")}</small></label>
                  <label><span>{t("timezone")}</span><input value={timezone} onChange={event => setTimezone(event.target.value)} placeholder="Asia/Riyadh" maxLength={64}/></label>
                  <label><span>{t("fields.phone")}</span><input type="tel" value={phone} onChange={(event) => setPhone(event.target.value)} placeholder={t("phonePlaceholder")} /></label>
                  <label><span>{t("fields.preferredLocale")}</span><select value={preferredLocale} onChange={(event) => setPreferredLocale(event.target.value as "" | "ar" | "en")}><option value="">{t("localeOptions.default")}</option><option value="ar">{t("localeOptions.ar")}</option><option value="en">{t("localeOptions.en")}</option></select><small>{t("localeChangeNote")}</small></label>
                </div>
                {error ? <div className={`${css.alert} ${css.alertError}`}>{t("updateError")}</div> : null}
                {success ? <div className={`${css.alert} ${css.alertSuccess}`}>{t("updateSuccess")}</div> : null}
                <div className={css.formFooter}><p>{t("saveHint")}</p><button disabled={saving}>{saving ? <span className={css.spinner} /> : null}{t(saving ? "saving" : "saveButton")}</button></div>
              </form>
            </section>
            {!user.is_organization_root ? <EmailChangeForm/> : <section className={css.card}><h2>{t("emailChange.title")}</h2><p role="note">{t("emailChange.rootProtected")}</p></section>}
          </div>

          <aside className={css.sideColumn}>
            <section className={`${css.card} ${css.securityCard}`}>
              <div className={css.securityShield}>{icons.lock}</div>
              <p className={css.kicker}>{t("securitySection")}</p><h2>{t("securityTitle")}</h2><p>{t("securityDescription")}</p>
              <div className={css.session}><span className={css.sessionDot} /><div><strong>{t("activeSession")}</strong><small>{t("sessionProtected")}</small></div></div>
              <Link href="/admin/change-password" className={css.securityLink}>{icons.key}<span>{t("changePassword")}</span><b aria-hidden="true">{currentLocale === "ar" ? "←" : "→"}</b></Link>
            </section>
            <section className={`${css.card} ${css.preferenceCard}`}><span className={css.cardIcon}>{icons.globe}</span><div><h3>{t("languagePreference")}</h3><p>{preferredLocale ? t(`localeOptions.${preferredLocale}`) : t("localeOptions.default")}</p></div></section>
          </aside>
        </div>
        <EffectiveAccessPanel self />
      </div>
    </PageFrame>
  );
}
