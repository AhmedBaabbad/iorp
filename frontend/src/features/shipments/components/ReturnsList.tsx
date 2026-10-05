"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import s from "@/features/production-demands/demands.module.css";
import { useFormatter } from "@/hooks/useFormatter";
import { getReturns, type ReturnFilters } from "../api";
import { shippingErrorMessage } from "../shipping-errors";
import { RETURN_STATUSES, type ReturnListItem } from "../types";
import { ReturnStatusBadge } from "./ShipmentStatusBadge";

const EMPTY: Required<Omit<ReturnFilters, "shipment_id">> = { status: "", kind: "", date_from: "", date_to: "", search: "" };

// "المرتجعات": goods that came back after leaving, each numbered against its delivery note.
export function ReturnsList() {
  const t = useTranslations("shipping.returns");
  const shipping = useTranslations("shipping");
  const errors = useTranslations("shipping.errors");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const units = useTranslations("common.units.units");
  const unit = (code: string) => (units.has(code) ? units(code) : code);
  const [filters, setFilters] = useState(EMPTY);
  const [rows, setRows] = useState<ReturnListItem[] | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try { setRows(await getReturns(filters)); } catch (e) { setError(shippingErrorMessage(e, errors)); }
  }, [filters, errors]);
  useEffect(() => { void load(); }, [load]);
  const set = (field: keyof typeof EMPTY, value: string) => setFilters(old => ({ ...old, [field]: value }));

  return <PageFrame title={t("listTitle")} subtitle={t("subtitle")} action={<Link href="/shipments" className={s.button}>{shipping("backToList")}</Link>}>
    <section className={s.toolbar} aria-label={t("filtersAria")}>
      <label className={s.field}>{shipping("filters.search")}
        <input type="search" value={filters.search} placeholder={t("searchPlaceholder")} onChange={e => set("search", e.target.value)} />
      </label>
      <label className={s.field}>{t("fields.kind")}
        <select value={filters.kind} onChange={e => set("kind", e.target.value)}>
          <option value="">{t("allKinds")}</option>
          {(["delivery", "customer"] as const).map(v => <option key={v} value={v}>{t(`kinds.${v}`)}</option>)}
        </select>
      </label>
      <label className={s.field}>{t("fields.status")}
        <select value={filters.status} onChange={e => set("status", e.target.value)}>
          <option value="">{shipping("filters.allStatuses")}</option>
          {RETURN_STATUSES.map(v => <option key={v} value={v}>{t(`statuses.${v}`)}</option>)}
        </select>
      </label>
      <label className={s.field}>{shipping("filters.dateFrom")}<input type="date" value={filters.date_from} onChange={e => set("date_from", e.target.value)} /></label>
      <label className={s.field}>{shipping("filters.dateTo")}<input type="date" value={filters.date_to} min={filters.date_from || undefined} onChange={e => set("date_to", e.target.value)} /></label>
      <button type="button" className={s.button} onClick={() => setFilters(EMPTY)}>{shipping("filters.clear")}</button>
    </section>
    {error && <div className={s.actions}><p role="alert" className={s.error}>{error}</p>
      <button type="button" className={s.button} onClick={() => void load()}>{common("actions.retry")}</button></div>}
    {!error && rows === null && <p className={s.muted}>{messages("loading.default")}</p>}
    {!error && rows?.length === 0 && <section className={s.panel}><h2 style={{ marginTop: 0 }}>{t("empty")}</h2><p className={s.muted} style={{ margin: 0 }}>{t("emptyHint")}</p></section>}
    {!error && rows && rows.length > 0 && <section className={s.panel}>
      <div className={s.tableWrap}><table className={s.table} aria-label={t("listTitle")}>
        <thead><tr>{["number", "requested_at", "note", "customer", "kind", "reason", "quantity", "status"].map(c => <th key={c}>{t(`fields.${c}`)}</th>)}</tr></thead>
        <tbody>{rows.map(r => <tr key={r.id}>
          <td><Link href={`/shipment-returns/${r.id}`}><bdi>{r.return_no}</bdi></Link></td>
          <td>{fmt.date(r.requested_at)}</td>
          <td><Link href={`/shipments/${r.shipment_id}`}><bdi>{r.shipment_no}</bdi></Link></td>
          <td>{r.customer_name}{r.customer_reference && <div className={s.muted}><bdi>{r.customer_reference}</bdi></div>}</td>
          <td>{t(`kinds.${r.kind}`)}</td>
          <td>{t(`reasons.${r.reason}`)}<div className={s.muted}>{t(`responsibility.${r.responsibility}`)}</div></td>
          <td><bdi>{r.quantities.map(q => fmt.quantity(q.quantity, unit(q.unit))).join(" · ") || "—"}</bdi>
            {r.weight_kg && <div className={s.muted}><bdi>{fmt.quantity(r.weight_kg, unit("kg"))}</bdi></div>}</td>
          <td><ReturnStatusBadge status={r.status} />{r.is_late && <div className={s.error}>{t("late")}</div>}</td>
        </tr>)}</tbody>
      </table></div>
    </section>}
  </PageFrame>;
}
