"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { qualityErrorMessage } from "@/features/quality-checks/components/quality-errors";
import { useFormatter } from "@/hooks/useFormatter";
import { Q } from "@/lib/quality-permissions";
import { getQualityRejections } from "../api/quality-rejections-api";
import { DISPOSITION_STATUSES, DISPOSITIONS, REJECTION_REASONS, type QualityRejectionListFilters, type QualityRejectionListItem } from "../types";
import { DispositionBadge } from "./DispositionBadge";
import { DispositionStatusBadge } from "./DispositionStatusBadge";

type Filters = Required<{ [K in keyof QualityRejectionListFilters]: string }>;
const EMPTY: Filters = { production_order_id: "", quality_check_id: "", rejection_reason: "", disposition: "", disposition_status: "", date_from: "", date_to: "", search: "" };

// "حالات الرفض": rejected quantities awaiting a decision (hold, scrap, rework…) and its execution.
export function QualityRejectionsList() {
  const t = useTranslations("quality.qualityRejections");
  const errors = useTranslations("quality.errors");
  const enums = useTranslations("enums.qualityRejection");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const params = useSearchParams();
  const canCreate = usePermission(Q.REJECTIONS_CREATE);
  const [filters, setFilters] = useState<Filters>(() => ({ ...EMPTY, production_order_id: params.get("order") ?? "", disposition_status: params.get("status") ?? "" }));
  const [rows, setRows] = useState<QualityRejectionListItem[] | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try { setRows(await getQualityRejections(filters as QualityRejectionListFilters)); }
    catch (e) { setError(qualityErrorMessage(e, errors)); }
  }, [filters, errors]);
  useEffect(() => { void load(); }, [load]);

  const set = (field: keyof Filters, value: string) => setFilters(old => ({ ...old, [field]: value }));
  const newHref = filters.production_order_id ? `/quality-rejections/new?order=${filters.production_order_id}` : "/quality-rejections/new";

  return <PageFrame title={t("listTitle")} subtitle={t("subtitle")}
    action={canCreate ? <Link href={newHref} className={`${s.button} ${s.primary}`}>{t("newButton")}</Link> : undefined}>
    <section className={s.toolbar} aria-label={t("filtersAria")}>
      <label className={s.field}>{t("filters.search")}
        <input type="search" value={filters.search} placeholder={t("filters.searchPlaceholder")} onChange={e => set("search", e.target.value)} />
      </label>
      <label className={s.field}>{t("fields.dispositionStatus")}
        <select value={filters.disposition_status} onChange={e => set("disposition_status", e.target.value)}>
          <option value="">{t("filters.allStatuses")}</option>
          {DISPOSITION_STATUSES.map(v => <option key={v} value={v}>{enums(`dispositionStatus.${v}`)}</option>)}
        </select>
      </label>
      <label className={s.field}>{t("fields.disposition")}
        <select value={filters.disposition} onChange={e => set("disposition", e.target.value)}>
          <option value="">{t("filters.allDispositions")}</option>
          {DISPOSITIONS.map(v => <option key={v} value={v}>{enums(`disposition.${v}`)}</option>)}
        </select>
      </label>
      <label className={s.field}>{t("fields.rejectionReason")}
        <select value={filters.rejection_reason} onChange={e => set("rejection_reason", e.target.value)}>
          <option value="">{t("filters.allReasons")}</option>
          {REJECTION_REASONS.map(v => <option key={v} value={v}>{enums(`rejectionReason.${v}`)}</option>)}
        </select>
      </label>
      <label className={s.field}>{t("filters.dateFrom")}<input type="date" value={filters.date_from} onChange={e => set("date_from", e.target.value)} /></label>
      <label className={s.field}>{t("filters.dateTo")}<input type="date" value={filters.date_to} min={filters.date_from || undefined} onChange={e => set("date_to", e.target.value)} /></label>
      <button type="button" className={s.button} onClick={() => setFilters(EMPTY)}>{t("filters.clear")}</button>
    </section>
    {error && <div className={s.actions}><p role="alert" className={s.error}>{error}</p>
      <button type="button" className={s.button} onClick={() => void load()}>{common("actions.retry")}</button></div>}
    {!error && rows === null && <p className={s.muted}>{messages("loading.default")}</p>}
    {!error && rows?.length === 0 && <section className={s.panel}><h2 style={{ marginTop: 0 }}>{t("empty")}</h2><p className={s.muted} style={{ margin: 0 }}>{t("createFirst")}</p></section>}
    {!error && rows && rows.length > 0 && <section className={s.panel}>
      <div className={s.tableWrap}><table className={s.table} aria-label={t("listAria")}>
        <thead><tr>
          {["rejectionCode", "rejectionDate", "productionOrder", "line", "qualityCheck", "quantityRejected", "rejectionReason", "disposition", "dispositionStatus"].map(c => <th key={c}>{t(`fields.${c}`)}</th>)}
        </tr></thead>
        <tbody>{rows.map(r => <tr key={r.id}>
          <td><Link href={`/quality-rejections/${r.id}`}><bdi>{r.rejection_code}</bdi></Link>
            {r.unresolved && <div><span className={`${s.badge} ${s.high}`} title={t("hints.blocksClose")}>{t("blocksClose")}</span></div>}</td>
          <td>{fmt.date(r.rejection_date)}</td>
          <td>{r.order_number ? <Link href={`/production-orders/${r.production_order_id}`}><bdi>{r.order_number}</bdi></Link> : "—"}</td>
          <td>{r.item_line_no ?? "—"}</td>
          <td>{r.inspection_code ? <Link href={`/quality-checks/${r.quality_check_id}`}><bdi>{r.inspection_code}</bdi></Link> : "—"}</td>
          <td><bdi>{fmt.quantity(r.quantity_rejected, r.unit)}</bdi></td>
          <td>{enums(`rejectionReason.${r.rejection_reason}`)}</td>
          <td>{r.disposition ? <DispositionBadge disposition={r.disposition} /> : "—"}</td>
          <td><DispositionStatusBadge status={r.disposition_status} /></td>
        </tr>)}</tbody>
      </table></div>
    </section>}
  </PageFrame>;
}
