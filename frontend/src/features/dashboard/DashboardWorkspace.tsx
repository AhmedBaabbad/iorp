"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useEffect, useState, type CSSProperties } from "react";
import { PageFrame } from "@/components/layout/page-frame";
import { AttentionTable, PeriodBar, StatCard, TrendChart, downloadSeries, usePeriod } from "@/components/dashboard/DashboardKit";
import type { Dashboard, DashboardCard, Period } from "@/components/dashboard/types";
import { useAuth } from "@/features/auth";
import { useFormatter } from "@/hooks/useFormatter";
import { apiClient } from "@/lib/api-client";
import { DEPARTMENTS, type Department } from "./departments";
import s from "./workspace.module.css";

function chartTone(key: string, index: number) {
  if (["accepted", "passed", "delivered", "completed", "received"].includes(key)) return "var(--teal)";
  if (["rejected", "failed", "cancelled", "scrap", "not_delivered"].includes(key)) return "var(--danger)";
  if (["conditional_accept", "pending", "on_hold"].includes(key)) return "var(--warning)";
  return ["var(--accent)", "var(--purple)", "var(--teal)", "var(--warning)"][index % 4];
}

function Spark({ values, tone }: { values: string[]; tone: string }) {
  const numbers = values.map(Number), max = Math.max(...numbers, 1), min = Math.min(...numbers, 0);
  if (numbers.length < 2) return null;
  return <svg viewBox="0 0 200 40" className={s.spark} aria-hidden="true"><polyline fill="none" stroke={tone} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" points={numbers.map((n, i) => `${i * 200 / (numbers.length - 1)},${36 - (n - min) / (max - min) * 30}`).join(" ")} /></svg>;
}

function Metric({ card, title, period, tone }: { card: DashboardCard; title: string; period: Period; tone: string }) {
  const t = useTranslations("dashboard.workspace"), f = useFormatter();
  if (card.style === "count") {
    return <Link href={card.href || "#"} className={s.counter} style={{ "--tone": tone } as CSSProperties}>
      <span className={s.counterMark} aria-hidden="true">●</span><div><span>{title}</span><strong>{card.value === null ? "—" : f.number(card.value)}</strong><small>{t("current")}</small></div><span className={s.chevron} aria-hidden="true">↗</span>
    </Link>;
  }
  if (card.style === "gauge") {
    const value = Math.max(0, Math.min(100, Number(card.value || 0)));
    return <Link href={card.href || "#"} className={s.gaugeCard}>
      <div><span className={s.eyebrow}>{t("performance")}</span><h3>{title}</h3><small>{t("selectedPeriod")}</small></div>
      <div className={s.gauge} style={{ background: `conic-gradient(${tone} ${value}%, var(--border) 0)` }}><strong>{card.value === null ? "—" : `${f.decimal(card.value, 1)}%`}</strong></div>
    </Link>;
  }
  return <div className={s.metric}><StatCard card={card} title={title} period={period} tone={tone} />{card.spark && <Spark values={card.spark} tone={tone} />}</div>;
}

function useBoard(department: Department, period: Period, refresh: number) {
  const { user, permissions } = useAuth();
  const identity = `${user?.organization_id || ""}:${user?.id || ""}:${[...permissions].sort().join(",")}`;
  const [state, setState] = useState<{ key: string; data?: Dashboard; error?: boolean }>({ key: "" });
  const key = `${identity}:${department}:${period}:${refresh}`;
  useEffect(() => {
    let active = true;
    apiClient<Dashboard>(`/${department}/dashboard?period=${period}`).then(data => { if (active) setState({ key, data }); })
      .catch(() => { if (active) setState({ key, error: true }); });
    return () => { active = false; };
  }, [key, department, period]);
  return state.key === key ? state : { key };
}

function DepartmentSection({ department, period, refresh, compact = false }: { department: Department; period: Period; refresh: number; compact?: boolean }) {
  const t = useTranslations(`dashboard.${department}`), common = useTranslations("dashboard.workspace"), f = useFormatter();
  const { data: board, error } = useBoard(department, period, refresh);
  const config = DEPARTMENTS.find(d => d.key === department)!;
  const label = (group: string, key: string) => {
    if (group === "cards" && key.startsWith("confirmed_value_")) return t("cards.confirmed_value", { currency: key.slice(16).toUpperCase() });
    return t.has(`${group}.${key}`) ? t(`${group}.${key}`) : key.replaceAll("_", " ");
  };
  const commercialGroups = department === "commercial" ? [
    { key: "followUps", keys: ["overdue_follow_ups", "due_today_follow_ups", "upcoming_follow_ups"] },
    { key: "samples", keys: ["samples_accepted", "samples_rejected", "samples_pending_decision", "samples_awaiting_evaluation"] },
  ] : [];
  const groupedKeys = new Set(commercialGroups.flatMap(group => group.keys));
  const ordinaryCards = board?.cards.filter(card => !groupedKeys.has(card.key));
  const cards = compact ? ordinaryCards?.slice(0, 4) : ordinaryCards;
  const series = board?.series || [];
  const names = Object.fromEntries(series.map(x => [x.key, label("series", x.key)]));
  const breakdowns = compact ? board?.breakdowns?.slice(0, 1) : board?.breakdowns;
  return <section className={s.department} style={{ "--tone": config.tone } as CSSProperties} aria-label={t("title")}>
    <header className={s.sectionHeader}><div><span className={s.eyebrow}>{common("department")}</span><h2>{t("title")}</h2><p>{t("subtitle")}</p></div>{compact && <Link className={s.openLink} href={`${config.href}?period=${period}`}>{common("explore")} <span aria-hidden="true">↗</span></Link>}</header>
    {error ? <p className={s.error} role="alert">{common("loadError")}</p> : !board ? <div className={s.metrics} aria-label={common("loading")}>{[0, 1, 2, 3].map(i => <div className={`${s.skeleton} iorp-skeleton`} key={i} />)}</div> : <>
      <div className={s.metrics}>{cards?.filter(c => c.style !== "count").map(card => <Metric key={card.key} card={card} title={label("cards", card.key)} period={period} tone={config.tone} />)}</div>
      {cards?.some(c => c.style === "count") && <div className={s.workload}>{cards.filter(c => c.style === "count").map(card => <Metric key={card.key} card={card} title={label("cards", card.key)} period={period} tone={config.tone} />)}</div>}
      {commercialGroups.map(group => {
        const items = group.keys.flatMap(key => board.cards.filter(card => card.key === key));
        return items.length > 0 && <section key={group.key} aria-label={t(`groups.${group.key}`)}>
          <h3>{t(`groups.${group.key}`)}</h3><p>{t(`groups.${group.key}Hint`)}</p>
          <div className={s.workload}>{items.map(card => <Metric key={card.key} card={card} title={label("cards", card.key)} period={period}
            tone={card.key === "overdue_follow_ups" || card.key === "samples_rejected" ? "var(--danger)" : card.key === "samples_accepted" ? "var(--teal)" : "var(--warning)"} />)}</div>
        </section>;
      })}
      <div className={s.analytics}>
        {series.length > 0 && <div className={s.trend}><TrendChart series={series} names={names} colors={Object.fromEntries(series.map((x, i) => [x.key, chartTone(x.key, i)]))} unit={series[0]?.unit} onDownload={() => downloadSeries(series, names, `${department}-${period}.csv`)} /></div>}
        {breakdowns?.map(b => {
          const total = b.items.reduce((n, item) => n + Math.max(0, Number(item.value)), 0);
          return <article key={b.key} className={s.breakdown}><span className={s.eyebrow}>{common("distribution")}</span><h3>{label("breakdowns", b.key)}</h3>
            {total === 0 ? <p className={s.empty}>{common("empty")}</p> : <>
              {b.style === "donut" && <div className={s.segmentBar} aria-hidden="true">{b.items.map((item, i) => <span key={item.key} style={{ width: `${Math.max(0, Number(item.value)) / total * 100}%`, background: chartTone(item.key, i) }} />)}</div>}
              <div className={s.bars}>{b.items.map((item, i) => <div key={item.key} className={s.barRow}><div><span>{item.label || label("labels", item.key)}</span><strong>{f.number(item.value)} {b.unit || ""}</strong></div><div className={s.track}><span style={{ width: `${Math.max(0, Number(item.value)) / total * 100}%`, background: chartTone(item.key, i) }} /></div></div>)}</div>
            </>}
          </article>;
        })}
      </div>
      {!compact && board.rankings?.map(rank => <article className={s.ranking} key={rank.key}><h3>{label("rankings", rank.key)} {rank.unit && <small> · {rank.unit}</small>}</h3>{!rank.items.length ? <p className={s.empty}>{common("empty")}</p> : rank.items.map((item, i) => <div className={s.rankRow} key={`${item.label}-${i}`}><span className={s.rankNumber}>{f.number(i + 1)}</span>{item.href ? <Link href={item.href}>{item.label}</Link> : <span>{item.label}</span>}<strong>{f.number(item.value)} {rank.unit || ""}</strong></div>)}</article>)}
      {!compact && <AttentionTable items={board.attention} total={board.attention_total} kinds={key => label("attention", key)} />}
      {compact && <footer className={s.departmentFooter}><span>{common("waiting", { count: board.attention_total })}</span><Link href={`${config.href}?period=${period}`}>{common("viewPriorities")}</Link></footer>}
    </>}
  </section>;
}

export function DashboardWorkspace({ department }: { department?: Department }) {
  const t = useTranslations("dashboard.workspace"), { user, hasPermission, permissions } = useAuth();
  const [period, setPeriod] = usePeriod(), [refresh, setRefresh] = useState(0);
  const visible = DEPARTMENTS.filter(d => d.permissions.some(p => hasPermission(p)));
  const title = department ? t(`titles.${department}`) : t("title");
  return <PageFrame title={title} subtitle={t("subtitle")} action={<PeriodBar period={period} onPeriod={setPeriod} />}>
    <div className={s.page}>
      <nav className={s.tabs} aria-label={t("navigation")}><Link href={`/dashboard?period=${period}`} aria-current={!department ? "page" : undefined}>{t("overview")}</Link>{visible.map(d => <Link key={d.key} href={`${d.href}?period=${period}`} aria-current={department === d.key ? "page" : undefined}>{t(`titles.${d.key}`)}</Link>)}</nav>
      <header className={s.hero}><div><span className={s.heroTag}>{t("live")}</span><h2>{department ? title : t("welcome", { name: user?.full_name || "" })}</h2><p>{t(department ? "departmentHint" : "overviewHint")}</p></div><button type="button" onClick={() => setRefresh(x => x + 1)}>{t("refresh")} ↻</button></header>
      {!department && <OrganizationSnapshot key={`${user?.organization_id}:${user?.id}:${[...permissions].sort().join(",")}`} refresh={refresh} />}
      {visible.filter(d => !department || d.key === department).map(d => <DepartmentSection key={d.key} department={d.key} period={period} refresh={refresh} compact={!department} />)}
      {(!visible.length || (department && !visible.some(d => d.key === department))) && <p className={s.empty}>{t("noAccess")}</p>}
    </div>
  </PageFrame>;
}

function OrganizationSnapshot({ refresh }: { refresh: number }) {
  const t = useTranslations("dashboard.workspace"), { hasPermission } = useAuth(), f = useFormatter();
  const [state, setState] = useState<{ refresh: number; values?: Record<string, number | null>; error?: boolean }>({ refresh: -1 });
  useEffect(() => { let active = true; apiClient<Record<string, number | null>>("/dashboard/summary").then(values => { if (active) setState({ refresh, values }); }).catch(() => { if (active) setState({ refresh, error: true }); }); return () => { active = false; }; }, [refresh]);
  const items = [
    ["customers_count", "commercial:customers:read", "/customers"], ["workforce_active_count", "workforce:members:read", "/workforce"],
    ["users_count", "foundation:users:read", "/admin/users"], ["roles_count", "foundation:roles:read", "/admin/roles"],
  ].filter(([, permission]) => hasPermission(permission));
  if (!items.length) return null;
  return <section className={s.snapshot}><div><span className={s.eyebrow}>{t("organization")}</span><h2>{t("currentSnapshot")}</h2></div>{items.map(([key, , href]) => <Link href={href} key={key}><strong>{state.refresh === refresh && state.values?.[key] != null ? f.number(state.values[key]) : "—"}</strong><span>{t(`snapshot.${key}`)}</span></Link>)}{state.error && <p role="alert">{t("loadError")}</p>}</section>;
}
