"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { useFormatter } from "@/hooks/useFormatter";
import { Q } from "@/lib/quality-permissions";
import { getNcrReports, type NcrFilters } from "../api";
import { ncrErrorMessage } from "../ncr-errors";
import { NCR_SOURCES, NCR_STATUSES, SEVERITIES, type NcrListItem } from "../types";
import { NcrSeverityBadge, NcrStatusBadge } from "./NcrBadges";

const EMPTY: Required<NcrFilters> = { status: "", source_type: "", severity: "", open_only: false, search: "", date_from: "", date_to: "" };

// "تقارير عدم المطابقة": every non-conformance, from a supplier's material to a customer's return, and where it stands.
export function NcrReportsList() {
  const t = useTranslations("ncr");
  const errors = useTranslations("ncr.errors");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const canCreate = usePermission(Q.NCR_CREATE);
  const [filters, setFilters] = useState(EMPTY);
  const [rows, setRows] = useState<NcrListItem[] | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try { setRows(await getNcrReports(filters)); } catch (e) { setError(ncrErrorMessage(e, errors)); }
  }, [filters, errors]);
  useEffect(() => { const timer = setTimeout(() => void load(), 200); return () => clearTimeout(timer); }, [load]);
  const set = (field: keyof NcrFilters, value: string | boolean) => setFilters(old => ({ ...old, [field]: value }));

  return <PageFrame title={t("listTitle")} subtitle={t("subtitle")}
    action={<span className={s.actions}>
      <Link href="/corrective-actions" className={s.button}>{t("actionsList")}</Link>
      {canCreate && <Link href="/non-conformance-reports/new" className={`${s.button} ${s.primary}`}>{t("newButton")}</Link>}
    </span>}>
    <section className={s.toolbar} aria-label={t("filtersAria")}>
      <label className={s.field}>{t("filters.search")}
        <input type="search" value={filters.search} placeholder={t("filters.searchPlaceholder")} onChange={e => set("search", e.target.value)} /></label>
      <label className={s.field}>{t("fields.status")}
        <select value={filters.status} onChange={e => set("status", e.target.value)}>
          <option value="">{t("filters.all")}</option>{NCR_STATUSES.map(v => <option key={v} value={v}>{t(`statuses.${v}`)}</option>)}
        </select></label>
      <label className={s.field}>{t("fields.source_type")}
        <select value={filters.source_type} onChange={e => set("source_type", e.target.value)}>
          <option value="">{t("filters.all")}</option>{NCR_SOURCES.map(v => <option key={v} value={v}>{t(`sources.${v}`)}</option>)}
        </select></label>
      <label className={s.field}>{t("fields.severity")}
        <select value={filters.severity} onChange={e => set("severity", e.target.value)}>
          <option value="">{t("filters.all")}</option>{SEVERITIES.map(v => <option key={v} value={v}>{t(`severities.${v}`)}</option>)}
        </select></label>
      <label className={s.field}>{t("filters.dateFrom")}<input type="date" value={filters.date_from} onChange={e => set("date_from", e.target.value)} /></label>
      <label className={s.field}>{t("filters.dateTo")}<input type="date" value={filters.date_to} onChange={e => set("date_to", e.target.value)} /></label>
      <label><input type="checkbox" checked={filters.open_only} onChange={e => set("open_only", e.target.checked)} /> {t("filters.openOnly")}</label>
      <button type="button" className={s.button} onClick={() => setFilters(EMPTY)}>{t("filters.clear")}</button>
    </section>
    {error && <div className={s.actions}><p role="alert" className={s.error}>{error}</p>
      <button type="button" className={s.button} onClick={() => void load()}>{common("actions.retry")}</button></div>}
    {!error && rows === null && <p className={s.muted}>{messages("loading.default")}</p>}
    {!error && rows?.length === 0 && <section className={s.panel}><h2 style={{ marginTop: 0 }}>{t("empty")}</h2><p className={s.muted} style={{ margin: 0 }}>{t("emptyHint")}</p></section>}
    {!error && rows && rows.length > 0 && <section className={s.panel}>
      <div className={s.tableWrap}><table className={s.table} aria-label={t("listTitle")}>
        <thead><tr>{["number", "date", "title", "source_type", "severity", "owner", "status"].map(c => <th key={c}>{t(`fields.${c}`)}</th>)}</tr></thead>
        <tbody>{rows.map(r => <tr key={r.id}>
          <td><Link href={`/non-conformance-reports/${r.id}`}><bdi>{r.report_number}</bdi></Link></td>
          <td>{fmt.date(r.report_date)}</td>
          <td>{r.title}{(r.supplier_name || r.customer_name) && <div className={s.muted}>{r.supplier_name ?? r.customer_name}</div>}</td>
          <td>{t(`sources.${r.source_type}`)}</td>
          <td><NcrSeverityBadge severity={r.severity} /></td>
          <td>{r.owner_name ?? "—"}{r.due_date && <div className={r.overdue ? s.error : s.muted}>{t("dueOn", { date: fmt.date(r.due_date) })}</div>}</td>
          <td><NcrStatusBadge status={r.status} />
            {r.open_actions > 0 && <div className={r.overdue_actions ? s.error : s.muted}>{t("openActions", { count: String(r.open_actions) })}</div>}</td>
        </tr>)}</tbody>
      </table></div>
    </section>}
  </PageFrame>;
}
