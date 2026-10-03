"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { getProductionOrders } from "@/features/production-orders/api/production-orders-api";
import type { ProductionOrderListItem } from "@/features/production-orders/types";
import { getWorkCenters } from "@/features/work-centers";
import { useFormatter } from "@/hooks/useFormatter";
import { getDowntimeEvents, getDowntimeSummary } from "../api";
import { ALL_CATEGORIES } from "../downtime-rules";
import type { DowntimeEvent, DowntimeFilters, DowntimeSummary } from "../types";
import { DowntimeCategoryBadge, DowntimeStatusBadge, DowntimeTypeBadge } from "./DowntimeBadges";
import { DowntimeSummaryCards } from "./DowntimeSummaryCards";
import { downtimeErrorMessage } from "./downtime-errors";
import { P } from "@/lib/production-permissions";

type Filters = Required<{ [K in keyof DowntimeFilters]: string }>;
const EMPTY: Filters = { work_center_id: "", production_order_id: "", production_run_id: "", category: "", planned: "", status: "", date_from: "", date_to: "" };

// "أحداث التوقف": when, where and why machines stopped, with the report figures for the same filters.
export function DowntimeEventsList() {
  const t = useTranslations("production.downtimeEvents");
  const categories = useTranslations("enums.downtimeEvent.category");
  const statuses = useTranslations("enums.downtimeEvent.status");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const params = useSearchParams();
  const canWrite = usePermission(P.DOWNTIME_CREATE);
  const [filters, setFilters] = useState<Filters>(() => ({ ...EMPTY, production_order_id: params.get("order") ?? "", work_center_id: params.get("work_center") ?? "" }));
  const [events, setEvents] = useState<DowntimeEvent[] | null>(null);
  const [summary, setSummary] = useState<DowntimeSummary | null>(null);
  const [orders, setOrders] = useState<ProductionOrderListItem[]>([]);
  const [centers, setCenters] = useState<{ id: string; code: string; name: string }[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    getProductionOrders().then(setOrders).catch(() => setOrders([]));
    getWorkCenters().then(setCenters).catch(() => setCenters([]));
  }, []);
  const load = useCallback(async () => {
    setError("");
    const query = Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) as DowntimeFilters;
    try {
      const [list, totals] = await Promise.all([getDowntimeEvents(query), getDowntimeSummary(query)]);
      setEvents(list); setSummary(totals);
    } catch (e) { setError(downtimeErrorMessage(e, t)); }
  }, [filters, t]);
  useEffect(() => { void load(); }, [load]);

  const set = (field: keyof Filters, value: string) => setFilters(old => ({ ...old, [field]: value }));
  const newQuery = new URLSearchParams(Object.entries({ order: filters.production_order_id, work_center: filters.work_center_id }).filter(([, v]) => v)).toString();
  const minutes = (value: string | null) => (value === null ? "—" : fmt.duration(Math.round(Number(value))));

  return <PageFrame title={t("listTitle")} subtitle={t("listSubtitle")}
    action={canWrite ? <Link href={`/downtime-events/new${newQuery ? `?${newQuery}` : ""}`} className={`${s.button} ${s.primary}`}>{t("actions.record")}</Link> : undefined}>
    <section className={s.toolbar} aria-label={t("filtersLabel")}>
      <label className={s.field}>{t("fields.workCenter")}
        <select value={filters.work_center_id} onChange={e => set("work_center_id", e.target.value)}>
          <option value="">{t("filters.allWorkCenters")}</option>
          {centers.map(c => <option key={c.id} value={c.id}>{c.code} — {c.name}</option>)}
        </select>
      </label>
      <label className={s.field}>{t("fields.productionOrder")}
        <select value={filters.production_order_id} onChange={e => set("production_order_id", e.target.value)}>
          <option value="">{t("filters.allOrders")}</option>
          {orders.map(o => <option key={o.id} value={o.id}>{o.production_order_number} — {o.product_type}</option>)}
        </select>
      </label>
      <label className={s.field}>{t("fields.category")}
        <select value={filters.category} onChange={e => set("category", e.target.value)}>
          <option value="">{t("filters.allCategories")}</option>
          {ALL_CATEGORIES.map(c => <option key={c} value={c}>{categories(c)}</option>)}
        </select>
      </label>
      <label className={s.field}>{t("fields.type")}
        <select value={filters.planned} onChange={e => set("planned", e.target.value)}>
          <option value="">{t("filters.allTypes")}</option>
          <option value="false">{t("types.loss")}</option>
          <option value="true">{t("types.planned")}</option>
        </select>
      </label>
      <label className={s.field}>{t("fields.status")}
        <select value={filters.status} onChange={e => set("status", e.target.value)}>
          <option value="">{t("filters.allStatuses")}</option>
          <option value="open">{statuses("open")}</option>
          <option value="closed">{statuses("closed")}</option>
        </select>
      </label>
      <label className={s.field}>{t("filters.dateFrom")}<input type="date" value={filters.date_from} onChange={e => set("date_from", e.target.value)} /></label>
      <label className={s.field}>{t("filters.dateTo")}<input type="date" value={filters.date_to} min={filters.date_from || undefined} onChange={e => set("date_to", e.target.value)} /></label>
      <button type="button" className={s.button} onClick={() => setFilters(EMPTY)}>{t("filters.clear")}</button>
    </section>
    {error && <div className={s.actions}><p role="alert" className={s.error}>{error}</p>
      <button type="button" className={s.button} onClick={() => void load()}>{common("actions.retry")}</button></div>}
    {!error && events === null && <p className={s.muted}>{messages("loading.default")}</p>}
    {!error && summary && events && events.length > 0 && <section className={s.panel}><DowntimeSummaryCards summary={summary} /></section>}
    {!error && events?.length === 0 && <section className={s.panel}><h2 style={{ marginTop: 0 }}>{t("empty")}</h2><p className={s.muted} style={{ margin: 0 }}>{t("emptyHint")}</p></section>}
    {!error && events && events.length > 0 && <section className={s.panel}>
      <div className={s.tableWrap}><table className={s.table} aria-label={t("listLabel")}>
        <thead><tr>{["startTime", "endTime", "duration", "workCenter", "category", "type", "status", "productionOrder", "reasonCode"].map(c => <th key={c}>{t(`fields.${c}`)}</th>)}</tr></thead>
        <tbody>{events.map(e => <tr key={e.id}>
          <td><Link href={`/downtime-events/${e.id}`}>{fmt.dateTime(e.start_time)}</Link></td>
          <td>{e.end_time ? fmt.dateTime(e.end_time) : "—"}</td>
          <td>{e.status === "open" ? t("elapsed", { minutes: minutes(e.labels?.elapsed_minutes ?? null) }) : minutes(e.duration_minutes)}</td>
          <td>{e.labels?.work_center_name ?? "—"}</td>
          <td><DowntimeCategoryBadge category={e.category} /></td>
          <td><DowntimeTypeBadge planned={e.planned} /></td>
          <td><DowntimeStatusBadge status={e.status} /></td>
          <td>{e.production_order_id && e.labels?.order_number ? <Link href={`/production-orders/${e.production_order_id}`}>{e.labels.order_number}</Link> : "—"}</td>
          <td>{e.reason_code ?? "—"}</td>
        </tr>)}</tbody>
      </table></div>
    </section>}
  </PageFrame>;
}
