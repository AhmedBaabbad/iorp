"use client";

import { DriverAffiliation } from "@/features/reference-directory/DirectorySelect";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { useFormatter } from "@/hooks/useFormatter";
import { S } from "@/lib/shipping-permissions";
import { getShipments, getShippingSettings, updateShippingSettings, type ShipmentFilters } from "../api";
import { shippingErrorMessage } from "../shipping-errors";
import { DELIVERY_METHODS, SHIPMENT_STATUSES, type ShipmentListItem, type ShippingSettings } from "../types";
import { ShipmentStatusBadge } from "./ShipmentStatusBadge";

const EMPTY: Required<ShipmentFilters> = { status: "", method: "", date_from: "", date_to: "", search: "" };

// "الشحنات": delivery notes, from preparation to receipt by the customer.
export function ShipmentsList() {
  const t = useTranslations("shipping");
  const errors = useTranslations("shipping.errors");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const units = useTranslations("common.units.units");
  const unit = (code: string) => (units.has(code) ? units(code) : code);
  const canCreate = usePermission(S.SHIPMENTS_CREATE);
  const canSeeReturns = usePermission(S.RETURNS_READ);
  const [filters, setFilters] = useState(EMPTY);
  const [rows, setRows] = useState<ShipmentListItem[] | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try { setRows(await getShipments(filters)); } catch (e) { setError(shippingErrorMessage(e, errors)); }
  }, [filters, errors]);
  useEffect(() => { void load(); }, [load]);
  const set = (field: keyof ShipmentFilters, value: string) => setFilters(old => ({ ...old, [field]: value }));

  return <PageFrame title={t("listTitle")} subtitle={t("subtitle")}
    action={<span className={s.actions}>
      {canSeeReturns && <Link href="/shipment-returns" className={s.button}>{t("actions.returnsList")}</Link>}
      {canCreate && <Link href="/shipments/new" className={`${s.button} ${s.primary}`}>{t("newButton")}</Link>}
    </span>}>
    <section className={s.toolbar} aria-label={t("filtersAria")}>
      <label className={s.field}>{t("filters.search")}
        <input type="search" value={filters.search} placeholder={t("filters.searchPlaceholder")} onChange={e => set("search", e.target.value)} />
      </label>
      <label className={s.field}>{t("fields.status")}
        <select value={filters.status} onChange={e => set("status", e.target.value)}>
          <option value="">{t("filters.allStatuses")}</option>
          {SHIPMENT_STATUSES.map(v => <option key={v} value={v}>{t(`statuses.${v}`)}</option>)}
        </select>
      </label>
      <label className={s.field}>{t("fields.method")}
        <select value={filters.method} onChange={e => set("method", e.target.value)}>
          <option value="">{t("filters.allMethods")}</option>
          {DELIVERY_METHODS.map(v => <option key={v} value={v}>{t(`methods.${v}`)}</option>)}
        </select>
      </label>
      <label className={s.field}>{t("filters.dateFrom")}<input type="date" value={filters.date_from} onChange={e => set("date_from", e.target.value)} /></label>
      <label className={s.field}>{t("filters.dateTo")}<input type="date" value={filters.date_to} min={filters.date_from || undefined} onChange={e => set("date_to", e.target.value)} /></label>
      <button type="button" className={s.button} onClick={() => setFilters(EMPTY)}>{t("filters.clear")}</button>
    </section>
    {error && <div className={s.actions}><p role="alert" className={s.error}>{error}</p>
      <button type="button" className={s.button} onClick={() => void load()}>{common("actions.retry")}</button></div>}
    {!error && rows === null && <p className={s.muted}>{messages("loading.default")}</p>}
    {!error && rows?.length === 0 && <section className={s.panel}><h2 style={{ marginTop: 0 }}>{t("empty")}</h2><p className={s.muted} style={{ margin: 0 }}>{t("emptyHint")}</p></section>}
    {!error && rows && rows.length > 0 && <section className={s.panel}>
      <div className={s.tableWrap}><table className={s.table} aria-label={t("listTitle")}>
        <thead><tr>{["number", "date", "customer", "method", "transport", "quantity", "status"].map(c => <th key={c}>{t(`fields.${c}`)}</th>)}</tr></thead>
        <tbody>{rows.map(r => <tr key={r.id}>
          <td><Link href={`/shipments/${r.id}`}><bdi>{r.shipment_no}</bdi></Link></td>
          <td>{fmt.date(r.shipment_date)}</td>
          <td>{r.customer_name}{r.customer_reference && <div className={s.muted}><bdi>{r.customer_reference}</bdi></div>}</td>
          <td>{t(`methods.${r.delivery_method}`)}</td>
          <td><bdi>{r.delivery_method === "carrier" ? (r.carrier_name ?? "—") : [r.driver_name, r.vehicle_plate].filter(Boolean).join(" — ") || "—"}</bdi>{r.delivery_method!=="carrier"&&r.driver_name&&<div><DriverAffiliation value={r.driver_affiliation}/></div>}</td>
          <td><bdi>{r.quantities.map(q => fmt.quantity(q.quantity, unit(q.unit))).join(" · ") || "—"}</bdi>
            {r.weight_total_kg && <div className={s.muted}><bdi>{fmt.quantity(r.weight_total_kg, unit("kg"))}</bdi></div>}</td>
          <td><ShipmentStatusBadge status={r.status} />
            {r.attempt > 1 && <div className={s.muted}>{t("attemptBadge", { n: String(r.attempt) })}</div>}
            {r.open_returns > 0 && <div className={s.muted}>{t("openReturnsHint", { count: String(r.open_returns) })}</div>}</td>
        </tr>)}</tbody>
      </table></div>
    </section>}
    <NumberingSettings />
  </PageFrame>;
}

// Number prefixes (DN- and RT- by default; numbers already issued keep theirs), the return window and the weight tolerance.
function NumberingSettings() {
  const t = useTranslations("shipping.settings");
  const errors = useTranslations("shipping.errors");
  const canEdit = usePermission(S.SETTINGS_UPDATE);
  const [v, setV] = useState<ShippingSettings | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (canEdit) getShippingSettings().then(setV).catch(() => setV(null)); }, [canEdit]);
  if (!canEdit || v === null) return null;
  const set = (field: keyof ShippingSettings, value: string) => setV(old => (old ? { ...old, [field]: value } : old));

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setMessage("");
    try {
      setV(await updateShippingSettings({ note_prefix: v!.note_prefix, return_prefix: v!.return_prefix,
        return_window_days: Number(v!.return_window_days), weight_tolerance_pct: String(v!.weight_tolerance_pct) }));
      setMessage(t("saved"));
    } catch (e) { setMessage(shippingErrorMessage(e, errors)); } finally { setBusy(false); }
  }
  const year = new Date().getFullYear();
  return <form className={s.panel} onSubmit={save} aria-label={t("title")}>
    <h2 style={{ marginTop: 0 }}>{t("title")}</h2>
    <div className={s.toolbar} style={{ marginBottom: 0 }}>
      <label className={s.field}>{t("prefix")}<input dir="ltr" required maxLength={20} pattern="[A-Za-z0-9_\-/]+" value={v.note_prefix} onChange={e => set("note_prefix", e.target.value)} /></label>
      <label className={s.field}>{t("returnPrefix")}<input dir="ltr" required maxLength={20} pattern="[A-Za-z0-9_\-/]+" value={v.return_prefix} onChange={e => set("return_prefix", e.target.value)} /></label>
      <label className={s.field}>{t("returnWindow")}<input type="number" dir="ltr" required min={0} max={365} value={v.return_window_days} onChange={e => set("return_window_days", e.target.value)} /></label>
      <label className={s.field}>{t("tolerance")}<input type="number" dir="ltr" required min={0} max={50} step="0.01" value={String(Number(v.weight_tolerance_pct))} onChange={e => set("weight_tolerance_pct", e.target.value)} /></label>
      <button type="submit" className={s.button} disabled={busy}>{t("save")}</button>
      <span className={s.muted}>{t("example", { number: `${v.note_prefix}${year}-0001`, returnNumber: `${v.return_prefix}${year}-0001` })}</span>
      {message && <span role="status" className={s.muted}>{message}</span>}
    </div>
  </form>;
}
