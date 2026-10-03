"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import {
  IconAlertTriangle, IconCalendar, IconCheckCircle, IconClipboardCheck, IconFactory,
  IconFlask, IconIdCard, IconPlus, IconShield, IconUserCog, IconUsers,
} from "@/components/layout/nav-icons";
import { useAuth } from "@/features/auth";
import { useEnumLabel } from "@/i18n/enum-helpers";
import { useFormatter } from "@/hooks/useFormatter";
import { getDashboardSummary } from "./api/dashboard-api";
import type { DashboardSummary } from "./types";
import styles from "./dashboard.module.css";
import { P } from "@/lib/production-permissions";

// The server sends these sections only with the matching read permission (dashboard summary route).
const QUALITY_CHECKS_READ = "quality:quality_checks:read";

type Icon = (props: { size?: number }) => ReactNode;
type Kpi = { key: string; href: string; permission?: string; icon: Icon; tone: string; value: (s: DashboardSummary) => number | null };
type Action = { key: string; href: string; permission: string };

const kpis: Kpi[] = [
  { key: "followUpsOverdue", href: "/follow-ups?tab=overdue", permission: "commercial:follow_ups:read", icon: IconAlertTriangle, tone: "danger", value: s => s.follow_ups_overdue },
  { key: "followUpsDueToday", href: "/follow-ups?tab=today", permission: "commercial:follow_ups:read", icon: IconCalendar, tone: "warning", value: s => s.follow_ups_due_today },
  { key: "productionOrders", href: "/production-orders", permission: P.ORDERS_READ, icon: IconFactory, tone: "orange", value: s => s.production_orders_count },
  { key: "qualityChecks", href: "/quality-checks", permission: QUALITY_CHECKS_READ, icon: IconClipboardCheck, tone: "purple", value: s => s.quality_checks_count },
  { key: "customers", href: "/customers", permission: "commercial:customers:read", icon: IconUsers, tone: "blue", value: s => s.customers_count },
  { key: "activeMembers", href: "/workforce", permission: "workforce:members:read", icon: IconCheckCircle, tone: "success", value: s => s.workforce_active_count },
  { key: "systemUsers", href: "/admin/users", permission: "foundation:users:read", icon: IconUserCog, tone: "teal", value: s => s.users_count },
  { key: "samples", href: "/samples", permission: "commercial:samples:read", icon: IconFlask, tone: "purple", value: s => s.samples_count },
];

const actions: Action[] = [
  { key: "newCustomer", href: "/customers/new", permission: "commercial:customers:create" },
  { key: "newSample", href: "/samples/new", permission: "commercial:samples:create" },
  { key: "newMember", href: "/workforce/new", permission: "workforce:members:create" },
  { key: "newUser", href: "/admin/users/new", permission: "foundation:users:write" },
  { key: "newRole", href: "/admin/roles/new", permission: "foundation:roles:write" },
];

function DistributionChart({ data, label }: { data: Record<string, number> | null | undefined; label: (key: string) => string }) {
  const entries = Object.entries(data ?? {}).filter(([, value]) => value > 0).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((sum, [, value]) => sum + value, 0);
  if (!entries.length) return <div className={styles.empty}>{label("empty")}</div>;
  return <div className={styles.chart}>{entries.map(([key, value], index) => (
    <div className={styles.chartRow} key={key}>
      <div className={styles.chartMeta}><span>{label(key)}</span><strong>{value}</strong></div>
      <div className={styles.track}><span className={styles[`bar${index % 4}`]} style={{ width: `${Math.max(7, (value / total) * 100)}%` }} /></div>
    </div>
  ))}</div>;
}

function SkeletonGrid() {
  return <div className={styles.kpiGrid}>{Array.from({ length: 8 }).map((_, i) => <div className={`${styles.kpiCard} ${styles.skeletonCard}`} key={i}><span className="iorp-skeleton" /><span className="iorp-skeleton" /><span className="iorp-skeleton" /></div>)}</div>;
}

let dashboardSummaryCache: DashboardSummary | null = null;

export function DashboardPage() {
  const t = useTranslations("dashboard.home");
  const enumLabel = useEnumLabel();
  const formatter = useFormatter();
  const { user, token, hasPermission } = useAuth();
  const [summary, setSummary] = useState<DashboardSummary | null>(dashboardSummaryCache);
  const [loading, setLoading] = useState(!dashboardSummaryCache);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(false);
    try { const data = await getDashboardSummary(token); dashboardSummaryCache = data; setSummary(data); }
    catch { setError(true); }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => { void load(); }, [load]);

  const visibleKpis = kpis.filter(item => !item.permission || hasPermission(item.permission));
  const visibleActions = actions.filter(item => hasPermission(item.permission));
  const attention = [
    hasPermission("commercial:follow_ups:read") && (summary?.follow_ups_overdue ?? 0) > 0 ? { key: "overdue", value: summary!.follow_ups_overdue!, href: "/follow-ups?tab=overdue" } : null,
    hasPermission("commercial:follow_ups:assign") && (summary?.follow_ups_needing_assignment ?? 0) > 0 ? { key: "unassigned", value: summary!.follow_ups_needing_assignment!, href: "/follow-ups?unassigned=true" } : null,
  ].filter(Boolean) as { key: string; value: number; href: string }[];

  return <PageFrame title={t("title")} section="IORP" subtitle={t("subtitle")}>
    <div className={styles.page}>
      <section className={styles.hero}>
        <div><span className={styles.heroBadge}>{t("hero.badge")}</span><h2>{t("welcome", { name: user?.full_name ?? "" })}</h2><p>{user?.organization_name} · {t("today")}: {formatter.date(new Date())}</p></div>
        <div className={styles.heroActions}>
          <span>{t("hero.lastUpdated")}: {summary?.last_updated_at ? formatter.dateTime(new Date(summary.last_updated_at)) : t("noData")}</span>
          <button type="button" onClick={() => void load()} disabled={loading}>{loading ? t("hero.refreshing") : t("hero.refresh")}</button>
        </div>
      </section>

      {error ? <section className={styles.error} role="alert"><div><strong>{t("error.title")}</strong><p>{t("error.description")}</p></div><button type="button" onClick={() => void load()}>{t("error.retry")}</button></section> : null}

      <div className={styles.sectionHeading}><div><span>{t("sections.overviewEyebrow")}</span><h3>{t("sections.overview")}</h3></div></div>
      {loading && !summary ? <SkeletonGrid /> : <div className={styles.kpiGrid}>{visibleKpis.map(item => { const ItemIcon = item.icon; const value = summary ? item.value(summary) : null; return <Link className={`${styles.kpiCard} ${styles[item.tone]}`} href={item.href} key={item.key}><span className={styles.icon}><ItemIcon size={20} /></span><div><strong>{value ?? t("noData")}</strong><p>{t(`kpi.${item.key}`)}</p></div><span className={styles.cardLink}>{t("viewDetails")}</span></Link>; })}</div>}

      <div className={styles.mainGrid}>
        <section className={styles.panelWide}>
          <div className={styles.panelHeader}><div><span>{t("sections.analyticsEyebrow")}</span><h3>{t("sections.analytics")}</h3></div></div>
          <div className={styles.chartGrid}>
            {hasPermission(P.ORDERS_READ) ? <article><h4>{t("charts.production")}</h4><DistributionChart data={summary?.production_by_status} label={key => key === "empty" ? t("charts.empty") : enumLabel("productionOrder", "status", key)} /></article> : null}
            {hasPermission(QUALITY_CHECKS_READ) ? <article><h4>{t("charts.quality")}</h4><DistributionChart data={summary?.quality_checks_by_result} label={key => key === "empty" ? t("charts.empty") : enumLabel("qualityCheck", "result", key)} /></article> : null}
            {hasPermission("workforce:members:read") ? <article><h4>{t("charts.workforce")}</h4><DistributionChart data={summary?.workforce_by_status} label={key => key === "empty" ? t("charts.empty") : enumLabel("workforceMember", "status", key)} /></article> : null}
          </div>
        </section>

        <section className={styles.panel}>
          <div className={styles.panelHeader}><div><span>{t("sections.priorityEyebrow")}</span><h3>{t("attention.title")}</h3></div><IconAlertTriangle size={20} /></div>
          {attention.length ? <div className={styles.attentionList}>{attention.map(item => <Link href={item.href} key={item.key}><span>{t(`attention.${item.key}`)}</span><strong>{item.value}</strong></Link>)}</div> : <div className={styles.empty}>{t("attention.empty")}</div>}
        </section>
      </div>

      <section className={styles.panelWide}>
        <div className={styles.panelHeader}><div><span>{t("sections.departmentsEyebrow")}</span><h3>{t("sections.departments")}</h3></div></div>
        <div className={styles.moduleGrid}>
          {hasPermission("commercial:customers:read") ? <Link href="/customers" className={styles.moduleCard}><IconUsers size={23}/><div><h4>{t("modules.commercial.title")}</h4><p>{t("modules.commercial.description")}</p></div><span>{summary?.customers_count ?? t("noData")}</span></Link> : null}
          {hasPermission(P.ORDERS_READ) ? <Link href="/production-orders" className={styles.moduleCard}><IconFactory size={23}/><div><h4>{t("modules.production.title")}</h4><p>{t("modules.production.description")}</p></div><span>{summary?.production_orders_count ?? t("noData")}</span></Link> : null}
          {hasPermission(QUALITY_CHECKS_READ) ? <Link href="/quality-checks" className={styles.moduleCard}><IconClipboardCheck size={23}/><div><h4>{t("modules.quality.title")}</h4><p>{t("modules.quality.description")}</p></div><span>{summary?.quality_checks_count ?? t("noData")}</span></Link> : null}
          {hasPermission("workforce:members:read") ? <Link href="/workforce" className={styles.moduleCard}><IconIdCard size={23}/><div><h4>{t("modules.workforce.title")}</h4><p>{t("modules.workforce.description")}</p></div><span>{summary?.workforce_count ?? t("noData")}</span></Link> : null}
          {hasPermission("foundation:users:read") ? <Link href="/admin/users" className={styles.moduleCard}><IconShield size={23}/><div><h4>{t("modules.administration.title")}</h4><p>{t("modules.administration.description")}</p></div><span>{summary?.users_count ?? t("noData")}</span></Link> : null}
        </div>
      </section>

      {visibleActions.length ? <section className={styles.quickPanel}><div><span>{t("quickActions.eyebrow")}</span><h3>{t("quickActions.title")}</h3></div><div>{visibleActions.map(action => <Link href={action.href} key={action.key}><IconPlus size={15}/>{t(`quickActions.${action.key}`)}</Link>)}</div></section> : null}
    </div>
  </PageFrame>;
}
