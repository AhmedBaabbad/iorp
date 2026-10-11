"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { Pagination } from "@/components/pagination/Pagination";
import { ProductionOrderPicker } from "@/features/production-orders/components/ProductionOrderPicker";
import { useListQuery, type Page } from "@/lib/pagination";
import { getWorkCenters } from "@/features/work-centers";
import { useFormatter } from "@/hooks/useFormatter";
import { getWasteRecords } from "../api";
import type { WasteRecordListItem } from "../types";
import { WASTE_CATEGORIES } from "../waste-rules";
import { WasteCategoryBadge } from "./WasteCategoryBadge";
import { wasteErrorMessage } from "./waste-errors";
import { useUnitSymbol } from "../unit-symbol";
import { P } from "@/lib/production-permissions";

// Filters and page live in the address (ARCH-PAGE-001); "order" is the older link from an order's page.
const FILTERS = ["production_order_id", "order", "work_center_id", "waste_category", "date_from", "date_to"] as const;
type Filter = (typeof FILTERS)[number];

// "سجلات الهدر": material lost while orders run, by order, cause and place.
export function WasteRecordsList() {
  const t = useTranslations("production.wasteRecords");
  const categories = useTranslations("enums.wasteRecord.wasteCategory");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const unit = useUnitSymbol();
  const canWrite = usePermission(P.WASTE_CREATE);
  const list = useListQuery(FILTERS);
  const filters = { ...list.filters, production_order_id: list.filters.production_order_id || list.filters.order };
  const query = new URLSearchParams([["page", String(list.page)], ["page_size", String(list.pageSize)],
    ...FILTERS.filter(k => k !== "order" && filters[k]).map(k => [k, filters[k]] as [string, string])]).toString();
  const [data, setData] = useState<Page<WasteRecordListItem> | null>(null);
  const records = data?.items ?? null;
  const [loading, setLoading] = useState(true);
  const [centers, setCenters] = useState<{ id: string; code: string; name: string }[]>([]);
  const [error, setError] = useState("");

  useEffect(() => { getWorkCenters().then(setCenters).catch(() => setCenters([])); }, []);
  const load = useCallback(async () => {
    setError(""); setLoading(true);
    try {
      const page = await getWasteRecords(query);
      setData(page);
      if (!page.items.length && page.total > 0 && list.page > page.pages) list.setPage(page.pages);
    } catch (e) { setError(wasteErrorMessage(e, t)); }
    finally { setLoading(false); }
  }, [query, t]); // eslint-disable-line react-hooks/exhaustive-deps -- list changes every render; query is what matters
  useEffect(() => { void load(); }, [load]);

  const set = (field: Filter, value: string) => field === "production_order_id" ? list.setFilters({ production_order_id: value, order: "" }) : list.setFilter(field, value);
  const newHref = filters.production_order_id ? `/waste-records/new?order=${filters.production_order_id}` : "/waste-records/new";

  return <PageFrame title={t("listTitle")} subtitle={t("listSubtitle")}
    action={canWrite ? <Link href={newHref} className={`${s.button} ${s.primary}`}>{t("actions.record")}</Link> : undefined}>
    <section className={s.toolbar} aria-label={t("filtersLabel")}>
      <label className={s.field}>{t("fields.productionOrder")}
        <ProductionOrderPicker value={filters.production_order_id} onChange={id => set("production_order_id", id)} emptyLabel={t("filters.allOrders")}
          ariaLabel={t("fields.productionOrder")} />
      </label>
      <label className={s.field}>{t("fields.wasteCategory")}
        <select value={filters.waste_category} onChange={e => set("waste_category", e.target.value)}>
          <option value="">{t("filters.allCategories")}</option>
          {WASTE_CATEGORIES.map(c => <option key={c} value={c}>{categories(c)}</option>)}
        </select>
      </label>
      <label className={s.field}>{t("fields.workCenter")}
        <select value={filters.work_center_id} onChange={e => set("work_center_id", e.target.value)}>
          <option value="">{t("filters.allWorkCenters")}</option>
          {centers.map(c => <option key={c.id} value={c.id}>{c.code} — {c.name}</option>)}
        </select>
      </label>
      <label className={s.field}>{t("filters.dateFrom")}<input type="date" value={filters.date_from} onChange={e => set("date_from", e.target.value)} /></label>
      <label className={s.field}>{t("filters.dateTo")}<input type="date" value={filters.date_to} min={filters.date_from || undefined} onChange={e => set("date_to", e.target.value)} /></label>
      <button type="button" className={s.button} onClick={() => list.clearFilters()}>{t("filters.clear")}</button>
    </section>
    {error && <div className={s.actions}><p role="alert" className={s.error}>{error}</p>
      <button type="button" className={s.button} onClick={() => void load()}>{common("actions.retry")}</button></div>}
    {!error && records === null && <p className={s.muted}>{messages("loading.default")}</p>}
    {!error && records?.length === 0 && <section className={s.panel}><h2 style={{ marginTop: 0 }}>{t("empty")}</h2><p className={s.muted} style={{ margin: 0 }}>{t("emptyHint")}</p></section>}
    {!error && records && records.length > 0 && <section className={s.panel}>
      <div className={s.tableWrap}><table className={s.table} aria-label={t("listLabel")}>
        <thead><tr>
          {["wasteDate", "productionOrder", "line", "wasteCategory", "quantityWasted", "workCenter", "run", "reasonCode", "recordedBy"].map(c => <th key={c}>{t(`fields.${c}`)}</th>)}
        </tr></thead>
        <tbody>{records.map(r => <tr key={r.id}>
          <td><Link href={`/waste-records/${r.id}`}>{fmt.date(r.waste_date)}</Link></td>
          <td>{r.labels?.order_number ? <Link href={`/production-orders/${r.production_order_id}`}>{r.labels.order_number}</Link> : "—"}</td>
          <td>{r.labels?.line_no ?? "—"}</td>
          <td><span className={s.actions} style={{ flexWrap: "wrap", gap: 4 }}>{r.categories.map(c => <WasteCategoryBadge key={c.category} category={c.category} />)}</span></td>
          <td><bdi>{fmt.quantity(r.quantity_wasted, unit(r.unit))}</bdi>
            {r.unit_needs_review && <> <span className={s.badge} title={t("hints.unitReview", { unit: r.legacy_unit_text ?? r.unit })}>{t("unitReviewBadge")}</span></>}</td>
          <td>{r.labels?.work_center_name ?? "—"}</td>
          <td>{r.labels?.run_date ? fmt.date(r.labels.run_date) : "—"}</td>
          <td>{r.reason_code ?? "—"}</td>
          <td>{r.labels?.created_by_name ?? "—"}</td>
        </tr>)}</tbody>
      </table></div>
    </section>}
    {data && <Pagination page={data.page} pageSize={data.page_size} total={data.total} pages={data.pages} disabled={loading}
      onPage={list.setPage} onPageSize={list.setPageSize} />}
  </PageFrame>;
}
