"use client";
/* eslint-disable @next/next/no-img-element -- authenticated blob URLs and local previews cannot use next/image. */

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import type { FormEvent, ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { API_BASE_URL, ApiClientError } from "@/lib/api-client";
import { TIMEZONES, timezoneLabel } from "@/lib/timezones";
import type {
  OrganizationLifecycleAction,
  OrganizationLifecycleStatus,
  PlatformOrganizationSummary,
} from "@/types/platform";
import {
  changeOrganizationStatus,
  createPlatformOrganization,
  listPlatformOrganizations,
  resetOrganizationRootPassword,
} from "./platform-api";
import { usePlatformAuth } from "./platform-auth-context";
import { PlatformProtectedRoute } from "./platform-protected-route";
import { platformStyles as styles } from "./platform-styles";
import css from "./platform-organizations-page.module.css";
import { useFileProblemText } from "@/components/forms/FilePicker";
import { fileProblem, useFilePolicy } from "@/lib/files";

const ORG_CODE_PATTERN = /^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$/;
const PAGE_SIZES = [10, 25, 50] as const;
type SortKey = "name" | "code" | "status" | "industry_type" | "user_count" | "created_at";
type SortDirection = "asc" | "desc";

const emptyForm = {
  organization: {
    name: "",
    code: "",
    industry_type: "",
    timezone: "Asia/Riyadh",
    default_locale: "ar" as "ar" | "en",
    logo_base64: "",
  },
  organization_admin: {
    full_name: "",
    email: "",
    phone: "",
  },
};

const actionForTarget: Partial<Record<OrganizationLifecycleStatus, OrganizationLifecycleAction>> = {
  active: "activate",
  suspended: "suspend",
  inactive: "deactivate",
  archived: "archive",
};

function Icon({ children, size = 20 }: { children: ReactNode; size?: number }) {
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{children}</svg>;
}

const icons = {
  building: <Icon><rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 7h2M14 7h2M8 11h2M14 11h2M9 21v-5h6v5"/></Icon>,
  check: <Icon><circle cx="12" cy="12" r="9"/><path d="m8 12 2.5 2.5L16 9"/></Icon>,
  pause: <Icon><circle cx="12" cy="12" r="9"/><path d="M10 9v6M14 9v6"/></Icon>,
  archive: <Icon><path d="M4 7h16M6 7v13h12V7M3 4h18v3H3zM10 11h4"/></Icon>,
  search: <Icon size={18}><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></Icon>,
  plus: <Icon size={18}><path d="M12 5v14M5 12h14"/></Icon>,
  more: <Icon size={19}><circle cx="5" cy="12" r="1" fill="currentColor"/><circle cx="12" cy="12" r="1" fill="currentColor"/><circle cx="19" cy="12" r="1" fill="currentColor"/></Icon>,
  alert: <Icon size={28}><path d="M10.3 3.7 2.4 18a2 2 0 0 0 1.8 3h15.6a2 2 0 0 0 1.8-3L13.7 3.7a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/></Icon>,
};

function formatDate(value: string, locale: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(locale, { year: "numeric", month: "short", day: "numeric" }).format(date);
}

function initials(name: string) {
  return name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
}

function colorFor(name: string) {
  const colors = ["#2563eb", "#7c3aed", "#0891b2", "#059669", "#c2410c", "#be185d"]; // theme-exempt: logo fallback palette, white initials read on each
  return colors[[...name].reduce((sum, char) => sum + char.charCodeAt(0), 0) % colors.length];
}

function OrganizationLogo({ organization, token, alt }: { organization: PlatformOrganizationSummary; token?: string | null; alt: string }) {
  const [source, setSource] = useState("");
  useEffect(() => {
    if (!organization.has_logo || !organization.logo_url || !token) return;
    let objectUrl = "";
    const url = `${API_BASE_URL.replace(/\/$/, "")}${organization.logo_url}`;
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => response.ok ? response.blob() : Promise.reject())
      .then((blob) => { objectUrl = URL.createObjectURL(blob); setSource(objectUrl); })
      .catch(() => setSource(""));
    return () => { if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [organization.has_logo, organization.logo_url, token]);

  if (source) return <img className={css.logo} src={source} alt={alt} />;
  return <span className={css.logoFallback} style={{ background: colorFor(organization.name) }}>{initials(organization.name)}</span>;
}

function PlatformOrganizationsContent() {
  const t = useTranslations("platform.organizations");
  const locale = useLocale();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { account, token } = usePlatformAuth();
  const isRtl = locale === "ar";
  const permissions = account?.permissions ?? [];
  const canCreate = permissions.includes("platform:organizations:create");
  const canReset = account?.role === "root" && permissions.includes("platform:organizations:update");

  const [organizations, setOrganizations] = useState<PlatformOrganizationSummary[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<OrganizationLifecycleStatus | "all">(() => {
    const requested = searchParams.get("status");
    const known: (OrganizationLifecycleStatus | "all")[] = ["active", "suspended", "inactive", "archived", "provisioning"];
    return known.includes(requested as OrganizationLifecycleStatus) ? (requested as OrganizationLifecycleStatus) : "all";
  });
  const [industryFilter, setIndustryFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("created_at");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(10);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [createError, setCreateError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [logoPreview, setLogoPreview] = useState("");
  const [actionOrg, setActionOrg] = useState<PlatformOrganizationSummary | null>(null);
  const [action, setAction] = useState<OrganizationLifecycleAction | null>(null);
  const [actionReason, setActionReason] = useState("");
  const [actionError, setActionError] = useState("");
  const [actionBusy, setActionBusy] = useState(false);
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const [resetOrganization, setResetOrganization] = useState<PlatformOrganizationSummary | null>(null);
  const [resetError, setResetError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(() => {
    setLoadError(false);
    setOrganizations(null);
    listPlatformOrganizations(token).then(setOrganizations).catch(() => setLoadError(true));
  }, [token]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { const id = window.setTimeout(() => setDebouncedQuery(query.trim().toLocaleLowerCase(locale)), 300); return () => window.clearTimeout(id); }, [query, locale]);
  useEffect(() => { setPage(1); }, [debouncedQuery, statusFilter, industryFilter, pageSize]);

  const counts = useMemo(() => ({
    total: organizations?.length ?? 0,
    active: organizations?.filter((org) => org.status === "active").length ?? 0,
    suspended: organizations?.filter((org) => org.status === "suspended").length ?? 0,
    archived: organizations?.filter((org) => org.status === "archived").length ?? 0,
  }), [organizations]);

  const industries = useMemo(() => Array.from(new Set((organizations ?? []).map((org) => org.industry_type).filter((value): value is string => Boolean(value)))).sort(), [organizations]);

  const filtered = useMemo(() => {
    const items = (organizations ?? []).filter((org) => {
      const matchesSearch = !debouncedQuery || org.name.toLocaleLowerCase(locale).includes(debouncedQuery) || org.code.toLocaleLowerCase(locale).includes(debouncedQuery);
      return matchesSearch && (statusFilter === "all" || org.status === statusFilter) && (industryFilter === "all" || org.industry_type === industryFilter);
    });
    return items.sort((a, b) => {
      const left = a[sortKey] ?? "";
      const right = b[sortKey] ?? "";
      const comparison = typeof left === "number" && typeof right === "number"
        ? left - right
        : String(left).localeCompare(String(right), locale, { numeric: true, sensitivity: "base" });
      return sortDirection === "asc" ? comparison : -comparison;
    });
  }, [organizations, debouncedQuery, statusFilter, industryFilter, sortKey, sortDirection, locale]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const pageItems = filtered.slice((safePage - 1) * pageSize, safePage * pageSize);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDirection((value) => value === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDirection("asc"); }
  }

  function setOrgField(key: keyof typeof form.organization, value: string) {
    setForm((current) => ({ ...current, organization: { ...current.organization, [key]: value } }));
  }
  function setAdminField(key: keyof typeof form.organization_admin, value: string) {
    setForm((current) => ({ ...current, organization_admin: { ...current.organization_admin, [key]: value } }));
  }

  function validateCreate() {
    if (!ORG_CODE_PATTERN.test(form.organization.code)) return t("create.errorInvalidCode");
    return "";
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    const validationError = validateCreate();
    if (validationError) { setCreateError(validationError); return; }
    setCreateError(""); setSubmitting(true);
    try {
      const created = await createPlatformOrganization(form, token);
      router.push(`/platform/organizations/${created.organization.id}?created=1&invited=${created.invitation_sent ? 1 : 0}`);
    } catch (error) {
      if (error instanceof ApiClientError && error.status === 409) {
        const code = error.details && typeof error.details === "object" && "code" in error.details ? String(error.details.code) : "";
        setCreateError(code === "EMAIL_ALREADY_EXISTS" ? t("create.errorEmailTaken") : t("create.errorCodeTaken"));
      } else setCreateError(t("create.errorGeneric"));
    } finally { setSubmitting(false); }
  }

  const logoPolicy = useFilePolicy("logo");
  const problemText = useFileProblemText();

  function handleLogo(file?: File) {
    if (!file) return;
    const problem = fileProblem(file, logoPolicy);
    if (problem) { setCreateError(problemText(problem, logoPolicy)); return; }
    const reader = new FileReader();
    reader.onload = () => { const value = String(reader.result ?? ""); setLogoPreview(value); setOrgField("logo_base64", value); };
    reader.readAsDataURL(file);
  }

  function availableActions(org: PlatformOrganizationSummary) {
    return (org.allowed_transitions ?? []).map((target) => actionForTarget[target]).filter((value): value is OrganizationLifecycleAction => Boolean(value)).filter((value) => {
      const permission = value === "activate" ? "platform:organizations:activate" : "platform:organizations:suspend";
      return permissions.includes(permission);
    });
  }

  async function submitLifecycle(event: FormEvent) {
    event.preventDefault();
    if (!actionOrg || !action) return;
    if (action === "archive" && !actionReason.trim()) { setActionError(t("console.confirm.archive.reasonRequired")); return; }
    setActionBusy(true); setActionError("");
    try {
      const updated = await changeOrganizationStatus(actionOrg.id, action, actionReason.trim() || null, token);
      setOrganizations((current) => current?.map((org) => org.id === updated.id ? updated : org) ?? null);
      setNotice(t("console.actionSuccess")); setActionOrg(null); setAction(null); setActionReason("");
    } catch { setActionError(t("console.actionError")); }
    finally { setActionBusy(false); }
  }

  async function submitReset(event: FormEvent) {
    event.preventDefault();
    if (!resetOrganization) return;
    setActionBusy(true); setResetError("");
    try {
      await resetOrganizationRootPassword(resetOrganization.id, token);
      setNotice(t("resetRoot.success", { organization: resetOrganization.name, email: resetOrganization.root_user_email ?? t("resetRoot.unknownEmail") }));
      setResetOrganization(null);
    } catch { setResetError(t("resetRoot.errorGeneric")); }
    finally { setActionBusy(false); }
  }

  const field = (label: string, value: string, onChange: (value: string) => void, type = "text", optional = false) => (
    <label style={styles.field}><span style={styles.label}>{label}{optional && <span className={css.optional}> {t("console.optional")}</span>}</span><input style={styles.input} type={type} value={value} onChange={(event) => onChange(event.target.value)} required={!optional} /></label>
  );

  return <main className={css.page} dir={isRtl ? "rtl" : "ltr"}>
    <header className={css.header}>
      <div><p style={styles.eyebrow}>{t("console.eyebrow")}</p><h1 className={css.title}>{t("console.listTitle")}</h1><p className={css.subtitle}>{t("console.listSubtitle")}</p></div>
      <div className={css.headerActions}><LanguageSwitcher label={t("console.languageLabel")} /><Link className={css.secondaryLink} href="/platform/dashboard">{t("backToDashboard")}</Link></div>
    </header>

    {notice && <div className={css.notice} role="status">{notice}<button type="button" onClick={() => setNotice("")} aria-label={t("console.dismiss")}>×</button></div>}

    <section className={css.kpis} aria-label={t("console.kpi.label")}>
      {([
        ["total", counts.total, icons.building, "all"],
        ["active", counts.active, icons.check, "active"],
        ["suspended", counts.suspended, icons.pause, "suspended"],
        ["archived", counts.archived, icons.archive, "archived"],
      ] as const).map(([key, value, icon, filter]) => <button key={key} type="button" className={`${css.kpi} ${statusFilter === filter ? css.kpiActive : ""}`} onClick={() => setStatusFilter(filter)}><span className={`${css.kpiIcon} ${css[`kpiIcon_${key}`]}`}>{icon}</span><span>{organizations === null ? <strong aria-label={t("loading")}>…</strong> : <strong>{value}</strong>}<small>{t(`console.kpi.${key}`)}</small></span></button>)}
    </section>

    <section className={css.toolbar}>
      <label className={css.search}><span>{icons.search}</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t("console.searchPlaceholder")} aria-label={t("console.searchLabel")} />{query && <button type="button" onClick={() => setQuery("")} aria-label={t("console.clearSearch")}>×</button>}</label>
      <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)} aria-label={t("console.filters.statusLabel")}><option value="all">{t("console.filters.allStatuses")}</option>{["active", "suspended", "inactive", "archived", "provisioning"].map((status) => <option key={status} value={status}>{t(`status.${status}`)}</option>)}</select>
      {industries.length > 1 && <select value={industryFilter} onChange={(event) => setIndustryFilter(event.target.value)} aria-label={t("console.filters.industryLabel")}><option value="all">{t("console.filters.allIndustries")}</option>{industries.map((industry) => <option key={industry} value={industry}>{industry}</option>)}</select>}
      {(query || statusFilter !== "all" || industryFilter !== "all") && <button type="button" style={styles.secondaryButton} onClick={() => { setQuery(""); setStatusFilter("all"); setIndustryFilter("all"); }}>{t("console.filters.clearAll")}</button>}
      {canCreate && <button type="button" className={css.primaryButton} onClick={() => setShowCreate(true)}>{icons.plus}<span>{t("console.createButton")}</span></button>}
    </section>

    <section className={css.tablePanel}>
      {loadError ? <div className={css.state}>{icons.alert}<h2>{t("console.errorTitle")}</h2><p>{t("console.errorMessage")}</p><button className={css.primaryButton} onClick={load}>{t("console.retryButton")}</button></div>
      : organizations === null ? <div className={css.skeleton} aria-label={t("loading")}>{Array.from({ length: 6 }, (_, index) => <div key={index} />)}</div>
      : filtered.length === 0 ? <div className={css.state}>{icons.building}<h2>{t("console.emptyTitle")}</h2><p>{organizations.length ? t("console.emptyMessage") : t("console.emptyFirstOrg")}</p>{!organizations.length && canCreate && <button className={css.primaryButton} onClick={() => setShowCreate(true)}>{t("console.createButton")}</button>}</div>
      : <>
        <div className={css.tableScroll}><table><thead><tr>
          <th>{t("console.columns.logo")}</th>
          {(["name", "code", "status", "industry_type", "user_count", "created_at"] as SortKey[]).map((key) => <th key={key}><button className={css.sortButton} onClick={() => toggleSort(key)}>{t(`console.columns.${key}`)}<span>{sortKey === key ? (sortDirection === "asc" ? "↑" : "↓") : ""}</span></button></th>)}
          <th>{t("console.columns.timezone")}</th><th>{t("console.columns.rootEmail")}</th><th>{t("console.columns.actions")}</th>
        </tr></thead><tbody>{pageItems.map((org) => {
          const actions = availableActions(org);
          return <tr key={org.id} style={{ cursor: "pointer" }} onClick={(event) => { if (!(event.target as HTMLElement).closest("a,button")) router.push(`/platform/organizations/${org.id}`); }}>
            <td><OrganizationLogo organization={org} token={token} alt={t("console.logoAlt", { name: org.name })} /></td>
            <td><Link className={css.orgName} href={`/platform/organizations/${org.id}`}>{org.name}</Link></td>
            <td><code className={css.code}>{org.code}</code></td>
            <td><span className={`${css.status} ${css[`status_${org.status}`]}`}><i />{t(`status.${org.status}`)}</span></td>
            <td>{org.industry_type ?? t("notAvailable")}</td><td className={css.number}>{org.user_count}</td><td>{formatDate(org.created_at, locale)}</td><td>{org.timezone}</td><td>{org.root_user_email ?? t("notAvailable")}</td>
            <td><div className={css.rowActions}><Link className={css.viewButton} href={`/platform/organizations/${org.id}`}>{t("console.actions.view")}</Link>{(actions.length > 0 || canReset) && <div className={css.menuWrap}><button className={css.iconButton} type="button" onClick={() => setOpenMenu(openMenu === org.id ? null : org.id)} aria-label={t("console.actions.moreActions")}>{icons.more}</button>{openMenu === org.id && <div className={css.menu}>{actions.map((item) => <button key={item} type="button" className={item === "archive" ? css.dangerMenu : ""} onClick={() => { setOpenMenu(null); setActionOrg(org); setAction(item); }}>{t(`console.actions.${item}`)}</button>)}{canReset && <button type="button" onClick={() => { setOpenMenu(null); setResetOrganization(org); }}>{t("console.actions.resetRootPassword")}</button>}</div>}</div>}</div></td>
          </tr>;
        })}</tbody></table></div>
        <div className={css.pagination}><span>{t("console.pagination.showing", { from: (safePage - 1) * pageSize + 1, to: Math.min(safePage * pageSize, filtered.length), total: filtered.length })}</span><label>{t("console.pagination.perPage")}<select value={pageSize} onChange={(event) => setPageSize(Number(event.target.value))}>{PAGE_SIZES.map((size) => <option key={size}>{size}</option>)}</select></label><div><button onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={safePage === 1}>{isRtl ? "→" : "←"}<span>{t("console.pagination.previous")}</span></button><strong>{safePage} / {totalPages}</strong><button onClick={() => setPage((value) => Math.min(totalPages, value + 1))} disabled={safePage === totalPages}><span>{t("console.pagination.next")}</span>{isRtl ? "←" : "→"}</button></div></div>
      </>}
    </section>

    {showCreate && <div className={css.overlay}><div className={css.createDialog} role="dialog" aria-modal="true" aria-labelledby="create-title"><div className={css.dialogHeader}><div><p style={styles.eyebrow}>{t("console.createEyebrow")}</p><h2 id="create-title">{t("create.title")}</h2></div><button type="button" onClick={() => setShowCreate(false)} aria-label={t("create.cancel")}>×</button></div><form onSubmit={handleCreate}>
      <fieldset><legend>{t("console.organizationSection")}</legend><div className={css.formGrid}>{field(t("create.orgName"), form.organization.name, (value) => setOrgField("name", value))}<label style={styles.field}><span style={styles.label}>{t("create.orgCode")}</span><input style={styles.input} value={form.organization.code} onChange={(event) => setOrgField("code", event.target.value.toUpperCase())} pattern="[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*" required /><small>{t("create.orgCodeHint")}</small></label>{field(t("create.industryType"), form.organization.industry_type, (value) => setOrgField("industry_type", value), "text", true)}<label style={styles.field}><span style={styles.label}>{t("create.timezone")}</span><input style={styles.input} list="organization-timezones" value={form.organization.timezone} onChange={(event) => setOrgField("timezone", event.target.value)} required /><datalist id="organization-timezones">{TIMEZONES.map((zone) => <option key={zone} value={zone}>{timezoneLabel(zone)}</option>)}</datalist></label><label style={styles.field}><span style={styles.label}>{t("create.defaultLocale")}</span><select style={styles.input} value={form.organization.default_locale} onChange={(event) => setOrgField("default_locale", event.target.value)}><option value="ar">{t("create.localeArabic")}</option><option value="en">{t("create.localeEnglish")}</option></select></label><label className={css.logoUpload}><span>{t("create.logo")}</span><input type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => handleLogo(event.target.files?.[0])} /><small>{t("create.logoHint")}</small>{logoPreview && <img src={logoPreview} alt={t("create.logoPreviewAlt")} />}</label></div></fieldset>
      <fieldset><legend>{t("console.rootSection")}</legend><p className={css.rootNote}>{icons.check}<span>{t("console.rootAccountNote")}</span></p><div className={css.formGrid}>{field(t("create.adminFullName"), form.organization_admin.full_name, (value) => setAdminField("full_name", value))}{field(t("create.adminEmail"), form.organization_admin.email, (value) => setAdminField("email", value), "email")}{field(t("create.adminPhone"), form.organization_admin.phone, (value) => setAdminField("phone", value), "tel", true)}</div></fieldset>
      {createError && <div style={styles.error}>{createError}</div>}<div className={css.dialogFooter}><button type="button" className={css.cancelButton} onClick={() => setShowCreate(false)}>{t("create.cancel")}</button><button type="submit" className={css.primaryButton} disabled={submitting}>{submitting ? t("create.submitting") : t("create.submit")}</button></div>
    </form></div></div>}

    {actionOrg && action && <div className={css.overlay}><div className={css.confirmDialog} role="dialog" aria-modal="true"><span className={`${css.confirmIcon} ${css[`confirm_${action}`]}`}>{action === "activate" ? icons.check : action === "archive" ? icons.archive : icons.alert}</span><h2>{t(`console.confirm.${action}.title`)}</h2><p>{t(`console.confirm.${action}.message`, { name: actionOrg.name })}</p>{["suspend", "archive"].includes(action) && <p className={css.warning}>{t(`console.confirm.${action}.warning`)}</p>}<form onSubmit={submitLifecycle}><label style={styles.field}><span style={styles.label}>{t("console.confirm.reasonLabel")}</span><textarea style={styles.input} value={actionReason} onChange={(event) => setActionReason(event.target.value)} required={action === "archive"} rows={3} /></label>{actionError && <div style={styles.error}>{actionError}</div>}<div className={css.dialogFooter}><button type="button" className={css.cancelButton} onClick={() => { setActionOrg(null); setAction(null); }}>{t("console.cancel")}</button><button type="submit" className={action === "archive" ? css.dangerButton : css.primaryButton} disabled={actionBusy}>{actionBusy ? t("console.processing") : t(`console.confirm.${action}.button`)}</button></div></form></div></div>}

    {resetOrganization && <div className={css.overlay}><div className={css.confirmDialog} role="dialog" aria-modal="true"><h2>{t("resetRoot.title")}</h2><p>{t("resetRoot.message", { organization: resetOrganization.name, email: resetOrganization.root_user_email ?? t("resetRoot.unknownEmail") })}</p><form onSubmit={submitReset}>{resetError && <div style={styles.error}>{resetError}</div>}<div className={css.dialogFooter}><button type="button" className={css.cancelButton} onClick={() => setResetOrganization(null)}>{t("resetRoot.cancelButton")}</button><button type="submit" className={css.dangerButton} disabled={actionBusy}>{actionBusy ? t("resetRoot.resetting") : t("resetRoot.resetButton")}</button></div></form></div></div>}
  </main>;
}

export function PlatformOrganizationsPage() {
  return <PlatformProtectedRoute><PlatformOrganizationsContent /></PlatformProtectedRoute>;
}
