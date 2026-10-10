"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { useFormatter } from "@/hooks/useFormatter";
import { useUnitSymbol } from "../unit-symbol";
import { getWasteSummary } from "../api";
import type { WasteSummary } from "../types";

import { WasteCategoryBadge } from "./WasteCategoryBadge";
import { wasteErrorMessage } from "./waste-errors";
import { P } from "@/lib/production-permissions";

// "هدر التشغيل" on the order page: totals per unit and cause. Kept apart from the final result's scrap.
export function OrderWasteSection({ order, revision = 0 }: { order: { id: string; status: string }; revision?: number }) {
  const t = useTranslations("production.wasteRecords");
  const fmt = useFormatter();
  const unit = useUnitSymbol();
  const canRead = usePermission(P.WASTE_READ);
  const relevant = !["draft", "released", "cancelled"].includes(order.status);
  const [summary, setSummary] = useState<WasteSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!canRead || !relevant) return;
    let active = true;
    getWasteSummary(order.id).then(v => { if (active) setSummary(v); }).catch(e => { if (active) setError(wasteErrorMessage(e, t)); });
    return () => { active = false; };
  }, [canRead, relevant, order.id, order.status, revision, t]);

  if (!canRead || !relevant) return null;
  return <section className={s.panel} aria-label={t("orderSection.title")}>
    <div className={s.actions} style={{ justifyContent: "space-between" }}>
      <h2 style={{ margin: 0 }}>{t("orderSection.title")}</h2>
      <span className={s.actions}>
        <Link className={s.button} href={`/waste-records?order=${order.id}`}>{t("orderSection.viewAll")}</Link>
        {summary?.actions.includes("create") && <Link className={`${s.button} ${s.primary}`} href={`/waste-records/new?order=${order.id}`}>{t("actions.record")}</Link>}
      </span>
    </div>
    <p className={s.muted}>{t("orderSection.hint")}</p>
    {error && <p role="alert" className={s.error}>{error}</p>}
    {summary && (summary.totals.length === 0 ? <p className={s.muted} style={{ margin: 0 }}>{t("orderSection.empty")}</p> : <>
      <dl className={s.grid} style={{ margin: "0 0 12px" }}>
        {summary.totals.map(total => <div key={total.unit} className={s.panel} style={{ margin: 0, padding: 14 }}>
          <dt className={s.muted}>{t("orderSection.total", { unit: unit(total.unit) })}</dt>
          <dd style={{ margin: "6px 0 0", fontSize: 20, fontWeight: 700 }}><bdi>{fmt.quantity(total.quantity, unit(total.unit))}</bdi></dd>
          <dd className={s.muted} style={{ margin: 0 }}>{t("orderSection.count", { count: String(total.count) })}</dd>
        </div>)}
      </dl>
      <div className={s.tableWrap}><table className={s.table} aria-label={t("orderSection.byCategory")}>
        <thead><tr><th>{t("fields.wasteCategory")}</th><th>{t("fields.quantityWasted")}</th><th>{t("orderSection.records")}</th></tr></thead>
        <tbody>{summary.by_category.map(row => <tr key={`${row.category}-${row.unit}`}>
          <td><WasteCategoryBadge category={row.category} /></td><td><bdi>{fmt.quantity(row.quantity, unit(row.unit))}</bdi></td><td>{row.count}</td>
        </tr>)}</tbody>
      </table></div>
    </>)}
  </section>;
}
