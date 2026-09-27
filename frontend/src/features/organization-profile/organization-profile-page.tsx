"use client";

import type { CSSProperties, FormEvent } from "react";
import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { PageFrame } from "@/components/layout/page-frame";
import { useAuth } from "@/features/auth";
import { TIMEZONES, timezoneLabel } from "@/lib/timezones";
import { API_BASE_URL, ApiClientError } from "@/lib/api-client";
import { getOrganizationProfile, removeOrganizationLogo, updateOrganizationProfile, uploadOrganizationLogo, type OrganizationProfile } from "./organization-profile-api";

const field: CSSProperties = { display: "grid", gap: 7 };
const input: CSSProperties = { border: "1px solid #cbd5e1", borderRadius: 8, padding: "11px 12px", background: "#fff" };
const panel: CSSProperties = { background: "#fff", border: "1px solid #e2e8f0", borderRadius: 12, padding: 24, marginBottom: 18 };
const badge: Record<string, CSSProperties> = { provisioning: { background: "#475569", color: "#fff" }, active: { background: "#166534", color: "#fff" }, suspended: { background: "#92400e", color: "#fff" }, inactive: { background: "#991b1b", color: "#fff" }, archived: { background: "#475569", color: "#cbd5e1" } };

export function OrganizationProfilePage() {
  const t = useTranslations("organization"); const { token, hasPermission, refreshCurrentUser } = useAuth();
  const [profile, setProfile] = useState<OrganizationProfile | null>(null); const [error, setError] = useState(""); const [success, setSuccess] = useState(""); const [busy, setBusy] = useState(false); const [logoSrc, setLogoSrc] = useState<string | null>(null);
  const canUpdate = hasPermission("foundation:organization:update"); const canBrand = hasPermission("foundation:organization:branding");
  const load = useCallback(() => getOrganizationProfile(token).then(setProfile).catch(() => setError(t("loadError"))), [t, token]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { if (!profile?.logo_url || !token) return setLogoSrc(null); let url=""; fetch(`${API_BASE_URL}${profile.logo_url}`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r.ok ? r.blob() : null).then(b => { if(b){url=URL.createObjectURL(b); setLogoSrc(url);} }); return () => { if(url) URL.revokeObjectURL(url); }; }, [profile?.logo_url, profile?.updated_at, token]);
  const set = (key: keyof OrganizationProfile, value: string) => setProfile(current => current ? { ...current, [key]: value } : current);
  async function save(event: FormEvent) { event.preventDefault(); if(!profile) return; setBusy(true); setError(""); try { setProfile(await updateOrganizationProfile({ name: profile.name, industry_type: profile.industry_type, timezone: profile.timezone, default_locale: profile.default_locale }, token)); setSuccess(t("updateSuccess")); await refreshCurrentUser(); } catch(e){ setError(e instanceof ApiClientError ? e.message : t("updateError")); } finally { setBusy(false); } }
  async function upload(file?: File) { if(!file) return; if(file.size > 2*1024*1024) return setError(t("logoTooLarge")); if(!["image/png","image/jpeg","image/webp"].includes(file.type)) return setError(t("logoInvalidType")); setBusy(true); try { const existed=profile?.has_logo; await uploadOrganizationLogo(file, token); await load(); await refreshCurrentUser(); setSuccess(t(existed ? "logoReplaced" : "logoUploaded")); } catch { setError(t("logoUploadError")); } finally { setBusy(false); } }
  async function remove() { if(!confirm(t("confirmRemoveLogo"))) return; setBusy(true); try { await removeOrganizationLogo(token); await load(); await refreshCurrentUser(); setSuccess(t("logoRemoved")); } catch { setError(t("logoUploadError")); } finally { setBusy(false); } }
  return <PageFrame title={t("profileTitle")} subtitle={t("profileSubtitle")} section={t("section")}>
    {error && <div style={{ color: "#b91c1c", marginBottom: 12 }}>{error}</div>}{success && <div style={{ color: "#166534", marginBottom: 12 }}>{success}</div>}
    {!profile ? <p>{t("loading")}</p> : <>
      <section style={panel}><h2>{t("logoSection")}</h2><div style={{ display: "flex", alignItems: "center", gap: 18, flexWrap: "wrap" }}>
        <div style={{ width: 120, height: 120, borderRadius: 18, background: "#e2e8f0", display: "grid", placeItems: "center", fontSize: 36, overflow: "hidden" }}>{logoSrc ? <>{/* eslint-disable-next-line @next/next/no-img-element */}<img src={logoSrc} alt={profile.name} style={{ width: "100%", height: "100%", objectFit: "contain" }} /></> : profile.name.slice(0,1).toUpperCase()}</div>
        <div><p>{t("logoRequirements")}</p>{canBrand ? <><label style={{ ...input, display: "inline-block", cursor: "pointer" }}>{t(profile.has_logo ? "replaceLogo" : "uploadLogo")}<input hidden type="file" accept="image/png,image/jpeg,image/webp" onChange={e => upload(e.target.files?.[0])} /></label>{profile.has_logo && <button type="button" onClick={remove} style={{ ...input, marginInlineStart: 8, color: "#b91c1c" }}>{t("removeLogo")}</button>}</> : <p>{t("brandingReadOnly")}</p>}</div>
      </div></section>
      <form onSubmit={save} style={panel}><h2>{t("infoSection")}</h2>{!canUpdate && <p>{t("readOnlyNotice")}</p>}<div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))", gap: 16 }}>
        <label style={field}><span>{t("fields.name")}</span><input style={input} value={profile.name} onChange={e=>set("name",e.target.value)} disabled={!canUpdate} /></label>
        <div style={field}><span>{t("fields.code")}</span><strong style={{ ...input, background: "#f1f5f9" }}>{profile.code}</strong><small>{t("codeImmutable")}</small></div>
        <label style={field}><span>{t("fields.industryType")}</span><input style={input} value={profile.industry_type ?? ""} onChange={e=>set("industry_type",e.target.value)} disabled={!canUpdate} /></label>
        <label style={field}><span>{t("fields.timezone")}</span><select style={input} value={profile.timezone} onChange={e=>set("timezone",e.target.value)} disabled={!canUpdate}>{TIMEZONES.map(z=><option key={z} value={z}>{timezoneLabel(z)}</option>)}</select></label>
        <label style={field}><span>{t("fields.defaultLocale")}</span><select style={input} value={profile.default_locale} onChange={e=>set("default_locale",e.target.value)} disabled={!canUpdate}><option value="ar">{t("localeOptions.ar")}</option><option value="en">{t("localeOptions.en")}</option></select></label>
        <div style={field}><span>{t("fields.status")}</span><span style={{ ...input, ...badge[profile.status] }}>{t(`statuses.${profile.status}`)}</span><small>{t("statusManagedByPlatform")}</small></div>
      </div>{canUpdate && <button disabled={busy} style={{ ...input, marginTop: 20, background: "#1f2937", color: "#fff" }}>{busy ? t("saving") : t("saveButton")}</button>}</form>
    </>}
  </PageFrame>;
}
