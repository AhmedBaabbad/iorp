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
import { getWasteRecords } from "../api";
import type { WasteCategory, WasteRecordListFilters, WasteRecordListItem } from "../types";
import { WASTE_CATEGORIES } from "../waste-rules";
import { WasteCategoryBadge } from "./WasteCategoryBadge";
import { wasteErrorMessage } from "./waste-errors";
import { P } from "@/lib/production-permissions";

type Filters = { production_order_id: string; work_center_id: string; waste_category: "" | WasteCategory; date_from: string; date_to: string };
const EMPTY: Filters = { production_order_id: "", work_center_id: "", waste_category: "", date_from: "", date_to: "" };

// "سجلات الهدر": material lost while orders run, by order, cause and place.
export function WasteRecordsList() {
  const t = useTranslations("production.wasteRecords");
  const categories = useTranslations("enums.wasteRecord.wasteCategory");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const params = useSearchParams();
  const canWrite = usePermission(P.WASTE_CREATE);
  const [filters, setFilters] = useState<Filters>(() => ({ ...EMPTY, production_order_id: params.get("order") ?? "" }));
  const [records, setRecords] = useState<WasteRecordListItem[] | null>(null);
  const [orders, setOrders] = useState<ProductionOrderListItem[]>([]);
  const [centers, setCenters] = useState<{ id: string; code: string; name: string }[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    getProductionOrders().then(setOrders).catch(() => setOrders([]));
    getWorkCenters().then(setCenters).catch(() => setCenters([]));
  }, []);
  const load = useCallback(async () => {
    setError("");
    try { setRecords(await getWasteRecords(Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) as WasteRecordListFilters)); }
    catch (e) { setError(wasteErrorMessage(e, t)); }
  }, [filters, t]);
  useEffect(() => { void load(); }, [load]);

  const set = (field: keyof Filters, value: string) => setFilters(old => ({ ...old, [field]: value }));
  const newHref = filters.production_order_id ? `/waste-records/new?order=${filters.production_order_id}` : "/waste-records/new";

  return <PageFrame title={t("listTitle")} subtitle={t("listSubtitle")}
    action={canWrite ? <Link href={newHref} className={`${s.button} ${s.primary}`}>{t("actions.record")}</Link> : undefined}>
    <section className={s.toolbar} aria-label={t("filtersLabel")}>
      <label className={s.field}>{t("fields.productionOrder")}
        <select value={filters.production_order_id} onChange={e => set("production_order_id", e.target.value)}>
          <option value="">{t("filters.allOrders")}</option>
          {orders.map(o => <option key={o.id} value={o.id}>{o.production_order_number} — {o.product_type}</option>)}
        </select>
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
      <button type="button" className={s.button} onClick={() => setFilters(EMPTY)}>{t("filters.clear")}</button>
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
          <td><WasteCategoryBadge category={r.waste_category} /></td>
          <td><bdi>{fmt.quantity(r.quantity_wasted, r.unit)}</bdi></td>
          <td>{r.labels?.work_center_name ?? "—"}</td>
          <td>{r.labels?.run_date ? fmt.date(r.labels.run_date) : "—"}</td>
          <td>{r.reason_code ?? "—"}</td>
          <td>{r.labels?.created_by_name ?? "—"}</td>
        </tr>)}</tbody>
      </table></div>
    </section>}
  </PageFrame>;
}
