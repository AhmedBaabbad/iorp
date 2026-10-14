"use client";

import {UnitLabel} from "@/components/UnitLabel";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import s from "@/features/production-demands/demands.module.css";
import { useFormatter } from "@/hooks/useFormatter";
import { getResultsOverview } from "../api";
import type { ResultOverviewRow } from "../types";
import { resultErrorMessage } from "./result-errors";

type Filter = "" | "completed" | "closed";
const pct = (value: string | null) => (value === null ? "—" : `${value}%`);

// "المخرجات الإنتاجية": completed and closed orders with their final result. Entries are recorded on the order page.
export function ResultsList() {
  const t = useTranslations("production.results");
  const orders = useTranslations("enums.productionOrder.status");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const [filter, setFilter] = useState<Filter>("");
  const [rows, setRows] = useState<ResultOverviewRow[] | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try { setRows(await getResultsOverview(filter || undefined)); } catch (e) { setError(resultErrorMessage(e, t)); }
  }, [filter, t]);
  useEffect(() => { void load(); }, [load]);

  return <PageFrame title={t("list.title")} subtitle={t("list.subtitle")}>
    <section className={s.toolbar} aria-label={t("list.filters")}>
      <label className={s.field}>{t("list.status")}
        <select value={filter} onChange={e => setFilter(e.target.value as Filter)}>
          <option value="">{t("list.allStatuses")}</option>
          <option value="completed">{orders("completed")}</option>
          <option value="closed">{orders("closed")}</option>
        </select>
      </label>
    </section>
    {error && <div className={s.actions}><p role="alert" className={s.error}>{error}</p>
      <button type="button" className={s.button} onClick={() => void load()}>{common("actions.retry")}</button></div>}
    {!error && rows === null && <p className={s.muted}>{messages("loading.default")}</p>}
    {!error && rows?.length === 0 && <section className={s.panel}><h2 style={{ marginTop: 0 }}>{t("list.empty")}</h2><p className={s.muted} style={{ margin: 0 }}>{t("list.emptyHint")}</p></section>}
    {!error && rows && rows.length > 0 && <section className={s.panel}>
      <div className={s.tableWrap}><table className={s.table} aria-label={t("list.title")}>
        <thead><tr>
          {["order", "status", "unit", "planned", "customerGood", "stockGood", "samples", "scrap", "rework", "fulfillment", "lossPct", "entries"].map(c => <th key={c}>{t(`list.columns.${c}`)}</th>)}
          <th>{t("columns.actions")}</th>
        </tr></thead>
        <tbody>{rows.flatMap(row => (row.totals.length ? row.totals : [null]).map((total, n) => <tr key={`${row.id}-${total?.unit ?? "none"}`}>
          {n === 0 ? <td rowSpan={Math.max(row.totals.length, 1)}><strong>{row.number}</strong><div className={s.muted}>{row.product_type}</div></td> : null}
          {n === 0 ? <td rowSpan={Math.max(row.totals.length, 1)}>
            <span className={`${s.badge} ${row.status === "closed" ? "" : s.blue}`}>{orders(row.status)}</span>
            {row.status === "completed" && <div className={s.muted} style={{ marginTop: 4 }}>{row.ready_to_close ? t("list.readyToClose") : t("list.needsResult")}</div>}
          </td> : null}
          <td>{total?.unit ? <UnitLabel value={total.unit}/> : "—"}</td>
          <td><bdi>{total ? fmt.number(total.planned_qty) : "—"}</bdi></td>
          <td><bdi>{total ? fmt.number(total.customer_good) : "—"}</bdi></td>
          <td><bdi>{total ? fmt.number(total.stock_good) : "—"}</bdi></td>
          <td><bdi>{total ? fmt.number(total.samples_total) : "—"}</bdi></td>
          <td><bdi>{total ? fmt.number(total.scrap_total) : "—"}</bdi></td>
          <td><bdi>{total ? fmt.number(total.rework_total) : "—"}</bdi></td>
          <td>{total ? pct(total.fulfillment_pct) : "—"}</td>
          <td>{total ? pct(total.loss_pct) : "—"}</td>
          {n === 0 ? <td rowSpan={Math.max(row.totals.length, 1)}>{row.entry_count}{row.correction_count ? ` (+${t("list.corrections", { count: String(row.correction_count) })})` : ""}</td> : null}
          {n === 0 ? <td rowSpan={Math.max(row.totals.length, 1)}>
            <Link className={`${s.button} ${row.status === "completed" ? s.primary : ""}`} href={`/production-orders/${row.id}#result`}>
              {row.status === "completed" ? t("list.record") : t("list.view")}
            </Link>
          </td> : null}
        </tr>))}</tbody>
      </table></div>
    </section>}
  </PageFrame>;
}
