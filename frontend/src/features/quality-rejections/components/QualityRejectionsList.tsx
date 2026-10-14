"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { Pagination } from "@/components/pagination/Pagination";
import { usePagedFilters, type Page } from "@/lib/pagination";
import { usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { qualityErrorMessage } from "@/features/quality-checks/components/quality-errors";
import { useFormatter } from "@/hooks/useFormatter";
import { Q } from "@/lib/quality-permissions";
import { DefectChips } from "@/features/quality-defects/components/DefectChips";
import { getQualityRejections } from "../api/quality-rejections-api";
import { DISPOSITION_STATUSES, DISPOSITIONS, REJECTION_REASONS, type QualityRejectionListFilters, type QualityRejectionListItem } from "../types";
import { DispositionBadge } from "./DispositionBadge";
import { DispositionStatusBadge } from "./DispositionStatusBadge";
import { useClassificationChoices, useClassificationName } from "@/features/masterdata";

type Filters = Required<{ [K in keyof QualityRejectionListFilters]: string }>;
const EMPTY: Filters = { production_order_id: "", quality_check_id: "", rejection_reason: "", disposition: "", disposition_status: "", date_from: "", date_to: "", search: "" };

// "حالات الرفض": rejected quantities awaiting a decision (hold, scrap, rework…) and its execution.
export function QualityRejectionsList() {
  const t = useTranslations("quality.qualityRejections");
  const errors = useTranslations("quality.errors");
  const enums = useTranslations("enums.qualityRejection");
  const reasonName = useClassificationName("rejection_reason", "qualityRejection", "rejectionReason");
  const reasonChoices = useClassificationChoices("rejection_reason", REJECTION_REASONS, "qualityRejection", "rejectionReason");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const canCreate = usePermission(Q.REJECTIONS_CREATE);
  // Filters and page live in the address (ARCH-PAGE-001); ?order= and ?status= are the older links from other pages.
  const paged = usePagedFilters({ ...EMPTY, unresolved: "" }, { order: "production_order_id", status: "disposition_status" });
  const filters = paged.filters;
  const [data, setData] = useState<Page<QualityRejectionListItem> | null>(null);
  const rows = data?.items ?? null;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const key = JSON.stringify(paged.query());
  const load = useCallback(async () => {
    setError(""); setLoading(true);
    try {
      const page = await getQualityRejections(paged.query());
      setData(page);
      // A filter left the page past the end: show the last page rather than an empty one.
      if (!page.items.length && page.total > 0 && paged.page > page.pages) paged.setPage(page.pages);
    } catch (e) { setError(qualityErrorMessage(e, errors)); }
    finally { setLoading(false); }
  }, [key, errors]); // eslint-disable-line react-hooks/exhaustive-deps -- paged changes every render; key is what matters
  useEffect(() => { void load(); }, [load]);

  const set = (field: keyof Filters, value: string) => paged.set(field, value);
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
          {reasonChoices.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}
        </select>
      </label>
      <label className={s.field}>{t("filters.dateFrom")}<input type="date" value={filters.date_from} onChange={e => set("date_from", e.target.value)} /></label>
      <label className={s.field}>{t("filters.dateTo")}<input type="date" value={filters.date_to} min={filters.date_from || undefined} onChange={e => set("date_to", e.target.value)} /></label>
      <button type="button" className={s.button} onClick={() => paged.clear()}>{t("filters.clear")}</button>
    </section>
    {error && <div className={s.actions}><p role="alert" className={s.error}>{error}</p>
      <button type="button" className={s.button} onClick={() => void load()}>{common("actions.retry")}</button></div>}
    {!error && rows === null && <p className={s.muted}>{messages("loading.default")}</p>}
    {!error && rows?.length === 0 && <section className={s.panel}><h2 style={{ marginTop: 0 }}>{t("empty")}</h2><p className={s.muted} style={{ margin: 0 }}>{t("createFirst")}</p></section>}
    {!error && rows && rows.length > 0 && <section className={s.panel}>
      <div className={s.tableWrap}><table className={s.table} aria-label={t("listAria")}>
        <thead><tr>
          {["rejectionCode", "rejectionDate", "productionOrder", "line", "qualityCheck", "quantityRejected", "rejectionReason", "defects", "disposition", "dispositionStatus"].map(c => <th key={c}>{t(`fields.${c}`)}</th>)}
        </tr></thead>
        <tbody>{rows.map(r => <tr key={r.id}>
          <td><Link href={`/quality-rejections/${r.id}`}><bdi>{r.rejection_code}</bdi></Link>
            {r.unresolved && <div><span className={`${s.badge} ${s.high}`} title={t("hints.blocksClose")}>{t("blocksClose")}</span></div>}</td>
          <td>{fmt.date(r.rejection_date)}</td>
          <td>{r.order_number ? <Link href={`/production-orders/${r.production_order_id}`}><bdi>{r.order_number}</bdi></Link> : "—"}</td>
          <td>{r.item_line_no ?? "—"}</td>
          <td>{r.inspection_code ? <Link href={`/quality-checks/${r.quality_check_id}`}><bdi>{r.inspection_code}</bdi></Link> : "—"}</td>
          <td><bdi>{fmt.quantity(r.quantity_rejected, r.unit)}</bdi></td>
          <td>{reasonName(r.rejection_reason)}</td>
          <td><DefectChips defects={r.defects ?? []} severity={r.severity} /></td>
          <td>{r.disposition ? <DispositionBadge disposition={r.disposition} /> : "—"}</td>
          <td><DispositionStatusBadge status={r.disposition_status} /></td>
        </tr>)}</tbody>
      </table></div>
    </section>}
    {data && <Pagination page={data.page} pageSize={data.page_size} total={data.total} pages={data.pages} disabled={loading}
      onPage={paged.setPage} onPageSize={paged.setPageSize} />}
  </PageFrame>;
}
