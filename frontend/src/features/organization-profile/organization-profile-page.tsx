"use client";

import type { CSSProperties, FormEvent } from "react";
import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { PageFrame } from "@/components/layout/page-frame";
import { BrandingEditor } from './BrandingEditor';
import { useAuth } from "@/features/auth";
import { TIMEZONES, timezoneLabel } from "@/lib/timezones";
import { API_BASE_URL, ApiClientError } from "@/lib/api-client";
import { getOrganizationProfile, removeOrganizationLogo, updateOrganizationProfile, uploadOrganizationLogo, type OrganizationProfile } from "./organization-profile-api";
import { FilePicker } from "@/components/forms/FilePicker";
import { StorageUsage } from "./StorageUsage";

const field: CSSProperties = { display: "grid", gap: 7 };
const input: CSSProperties = { border: "1px solid var(--border-strong)", borderRadius: 8, padding: "11px 12px", background: "var(--surface)", color: "var(--text)" };
const panel: CSSProperties = { background: "var(--surface)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 12, padding: 24, marginBottom: 18 };
const badge: Record<string, CSSProperties> = { provisioning: { background: "var(--surface-muted)", color: "var(--text-muted)" }, active: { background: "var(--success)", color: "var(--on-accent)" }, suspended: { background: "var(--warning)", color: "var(--on-accent)" }, inactive: { background: "var(--danger)", color: "var(--on-accent)" }, archived: { background: "var(--surface-muted)", color: "var(--text-muted)" } };

export function OrganizationProfilePage() {
  const t = useTranslations("organization"); const { token, hasPermission, refreshCurrentUser } = useAuth();
  const [profile, setProfile] = useState<OrganizationProfile | null>(null); const [error, setError] = useState(""); const [success, setSuccess] = useState(""); const [busy, setBusy] = useState(false); const [logoSrc, setLogoSrc] = useState<string | null>(null);
  const canUpdate = hasPermission("foundation:organization:update"); const canBrand = hasPermission("foundation:organization:branding") || hasPermission("organization:branding:update");
  const load = useCallback(() => getOrganizationProfile(token).then(setProfile).catch(() => setError(t("loadError"))), [t, token]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { if (!profile?.logo_url || !token) return setLogoSrc(null); let url=""; fetch(`${API_BASE_URL}${profile.logo_url}`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r.ok ? r.blob() : null).then(b => { if(b){url=URL.createObjectURL(b); setLogoSrc(url);} }); return () => { if(url) URL.revokeObjectURL(url); }; }, [profile?.logo_url, profile?.updated_at, token]);
  const set = (key: keyof OrganizationProfile, value: string) => setProfile(current => current ? { ...current, [key]: value } : current);
  async function save(event: FormEvent) { event.preventDefault(); if(!profile) return; setBusy(true); setError(""); try { setProfile(await updateOrganizationProfile({ name: profile.name, industry_type: profile.industry_type, timezone: profile.timezone, default_locale: profile.default_locale, max_sessions_per_user: profile.max_sessions_per_user }, token)); setSuccess(t("updateSuccess")); await refreshCurrentUser(); } catch(e){ setError(e instanceof ApiClientError ? e.message : t("updateError")); } finally { setBusy(false); } }
  async function upload(file?: File) { if(!file) return; setBusy(true); setError(""); try { const existed=profile?.has_logo; await uploadOrganizationLogo(file, token); await load(); await refreshCurrentUser(); setSuccess(t(existed ? "logoReplaced" : "logoUploaded")); } catch { setError(t("logoUploadError")); } finally { setBusy(false); } }
  async function remove() { if(!confirm(t("confirmRemoveLogo"))) return; setBusy(true); try { await removeOrganizationLogo(token); await load(); await refreshCurrentUser(); setSuccess(t("logoRemoved")); } catch { setError(t("logoUploadError")); } finally { setBusy(false); } }
  return <PageFrame title={t("profileTitle")} subtitle={t("profileSubtitle")} section={t("section")}>
    {error && <div style={{ color: "var(--danger)", marginBottom: 12 }}>{error}</div>}{success && <div style={{ color: "var(--success)", marginBottom: 12 }}>{success}</div>}
    {!profile ? <p>{t("loading")}</p> : <>
      <section style={panel}><h2>{t("logoSection")}</h2><div style={{ display: "flex", alignItems: "center", gap: 18, flexWrap: "wrap" }}>
        <div style={{ width: 120, height: 120, borderRadius: 18, background: "var(--border)", display: "grid", placeItems: "center", fontSize: 36, overflow: "hidden" }}>{logoSrc ? <>{/* eslint-disable-next-line @next/next/no-img-element */}<img src={logoSrc} alt={profile.name} style={{ width: "100%", height: "100%", objectFit: "contain" }} /></> : profile.name.slice(0,1).toUpperCase()}</div>
        <div><StorageUsage /><p>{t("logoRequirements")}</p>{canBrand ? <><FilePicker kind="logo" label={t(profile.has_logo ? "replaceLogo" : "uploadLogo")} busy={busy} disabled={busy} onFile={file => upload(file)} onError={setError} />{profile.has_logo && <button type="button" onClick={remove} style={{ ...input, marginInlineStart: 8, color: "var(--danger)" }}>{t("removeLogo")}</button>}</> : <p>{t("brandingReadOnly")}</p>}</div>
      </div></section>
      <form onSubmit={save} style={panel}><h2>{t("infoSection")}</h2>{!canUpdate && <p>{t("readOnlyNotice")}</p>}<div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))", gap: 16 }}>
        <label style={field}><span>{t("fields.name")}</span><input style={input} value={profile.name} onChange={e=>set("name",e.target.value)} disabled={!canUpdate} /></label>
        <div style={field}><span>{t("fields.code")}</span><strong style={{ ...input, background: "var(--surface-muted)" }}>{profile.code}</strong><small>{t("codeImmutable")}</small></div>
        <label style={field}><span>{t("fields.industryType")}</span><input style={input} value={profile.industry_type ?? ""} onChange={e=>set("industry_type",e.target.value)} disabled={!canUpdate} /></label>
        <label style={field}><span>{t("fields.timezone")}</span><select style={input} value={profile.timezone} onChange={e=>set("timezone",e.target.value)} disabled={!canUpdate}>{TIMEZONES.map(z=><option key={z} value={z}>{timezoneLabel(z)}</option>)}</select></label>
        <label style={field}><span>{t("fields.defaultLocale")}</span><select style={input} value={profile.default_locale} onChange={e=>set("default_locale",e.target.value)} disabled={!canUpdate}><option value="ar">{t("localeOptions.ar")}</option><option value="en">{t("localeOptions.en")}</option></select></label>
        <label style={field}><span>{t("fields.maxSessions")}</span>
          <select style={input} value={profile.max_sessions_per_user ?? 2} disabled={!canUpdate}
            onChange={e=>setProfile({ ...profile, max_sessions_per_user: Number(e.target.value) })}>{[1, 2, 3, 4, 5].map(n=><option key={n} value={n}>{n}</option>)}</select>
          <small style={{ color: "var(--text-muted)" }}>{t("fields.maxSessionsHint")}</small></label>
        <div style={field}><span>{t("fields.status")}</span><span style={{ ...input, ...badge[profile.status] }}>{t(`statuses.${profile.status}`)}</span><small>{t("statusManagedByPlatform")}</small></div>
      </div>{canUpdate && <button disabled={busy} style={{ ...input, marginTop: 20, background: "var(--text)", color: "var(--on-accent)" }}>{busy ? t("saving") : t("saveButton")}</button>}</form>
      <BrandingEditor revision={profile.updated_at}/>
    </>}
  </PageFrame>;
}
