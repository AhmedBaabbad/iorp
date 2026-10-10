"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { useFormatter } from "@/hooks/useFormatter";
import { Q } from "@/lib/quality-permissions";
import { DefectChips } from "@/features/quality-defects/components/DefectChips";
import type { DefectCategory } from "@/features/quality-defects/types";
import { getQualityChecks } from "../api/quality-checks-api";
import { CHECK_RESULTS, CHECK_STATUSES, CHECK_TYPES, type QualityCheckListFilters, type QualityCheckListItem } from "../types";
import { QualityCheckResultBadge } from "./QualityCheckResultBadge";
import { QualityCheckStatusBadge } from "./QualityCheckStatusBadge";
import { qualityErrorMessage } from "./quality-errors";

type Filters = Required<{ [K in keyof QualityCheckListFilters]: string }>;
const EMPTY: Filters = { production_order_id: "", check_type: "", status: "", result: "", date_from: "", date_to: "", search: "", defect_category: "" };
const DEFECT_CATEGORIES: DefectCategory[] = ["dimension", "thickness", "surface", "color", "strength", "winding", "weight", "packaging", "labeling", "finish", "other"];

// "فحوصات الجودة": inspections of production lots and samples, newest first.
export function QualityChecksList() {
  const t = useTranslations("quality.qualityChecks");
  const errors = useTranslations("quality.errors");
  const enums = useTranslations("enums.qualityCheck");
  const defectEnums = useTranslations("enums.qualityDefect.defectCategory");
  const common = useTranslations("common");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const params = useSearchParams();
  const canCreate = usePermission(Q.CHECKS_CREATE);
  const [filters, setFilters] = useState<Filters>(() => ({ ...EMPTY, production_order_id: params.get("order") ?? "", status: params.get("status") ?? "" }));
  const [checks, setChecks] = useState<QualityCheckListItem[] | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try { setChecks(await getQualityChecks(filters as QualityCheckListFilters)); }
    catch (e) { setError(qualityErrorMessage(e, errors)); }
  }, [filters, errors]);
  useEffect(() => { void load(); }, [load]);

  const set = (field: keyof Filters, value: string) => setFilters(old => ({ ...old, [field]: value }));
  const newHref = filters.production_order_id ? `/quality-checks/new?order=${filters.production_order_id}` : "/quality-checks/new";

  return <PageFrame title={t("listTitle")} subtitle={t("subtitle")}
    action={canCreate ? <Link href={newHref} className={`${s.button} ${s.primary}`}>{t("newButton")}</Link> : undefined}>
    <section className={s.toolbar} aria-label={t("filtersAria")}>
      <label className={s.field}>{t("filters.search")}
        <input type="search" value={filters.search} placeholder={t("filters.searchPlaceholder")} onChange={e => set("search", e.target.value)} />
      </label>
      <label className={s.field}>{t("fields.status")}
        <select value={filters.status} onChange={e => set("status", e.target.value)}>
          <option value="">{t("filters.allStatuses")}</option>
          {CHECK_STATUSES.map(v => <option key={v} value={v}>{enums(`status.${v}`)}</option>)}
        </select>
      </label>
      <label className={s.field}>{t("fields.checkType")}
        <select value={filters.check_type} onChange={e => set("check_type", e.target.value)}>
          <option value="">{t("filters.allTypes")}</option>
          {CHECK_TYPES.map(v => <option key={v} value={v}>{enums(`checkType.${v}`)}</option>)}
        </select>
      </label>
      <label className={s.field}>{t("fields.result")}
        <select value={filters.result} onChange={e => set("result", e.target.value)}>
          <option value="">{t("filters.allResults")}</option>
          {CHECK_RESULTS.map(v => <option key={v} value={v}>{enums(`result.${v}`)}</option>)}
        </select>
      </label>
      <label className={s.field}>{t("filters.defectType")}
        <select value={filters.defect_category} onChange={e => set("defect_category", e.target.value)}>
          <option value="">{t("filters.allDefectTypes")}</option>
          {DEFECT_CATEGORIES.map(v => <option key={v} value={v}>{defectEnums(v)}</option>)}
        </select>
      </label>
      <label className={s.field}>{t("filters.dateFrom")}<input type="date" value={filters.date_from} onChange={e => set("date_from", e.target.value)} /></label>
      <label className={s.field}>{t("filters.dateTo")}<input type="date" value={filters.date_to} min={filters.date_from || undefined} onChange={e => set("date_to", e.target.value)} /></label>
      <button type="button" className={s.button} onClick={() => setFilters(EMPTY)}>{t("filters.clear")}</button>
    </section>
    {filters.production_order_id && checks?.[0]?.order_number && <p className={s.muted}>{t("filters.forOrder", { number: checks[0].order_number })}</p>}
    {error && <div className={s.actions}><p role="alert" className={s.error}>{error}</p>
      <button type="button" className={s.button} onClick={() => void load()}>{common("actions.retry")}</button></div>}
    {!error && checks === null && <p className={s.muted}>{messages("loading.default")}</p>}
    {!error && checks?.length === 0 && <section className={s.panel}><h2 style={{ marginTop: 0 }}>{t("empty")}</h2><p className={s.muted} style={{ margin: 0 }}>{t("createFirst")}</p></section>}
    {!error && checks && checks.length > 0 && <section className={s.panel}>
      <div className={s.tableWrap}><table className={s.table} aria-label={t("listAria")}>
        <thead><tr>
          {["inspectionCode", "checkDate", "checkType", "subject", "line", "qtyInspected", "qtyAccepted", "qtyRejected", "status", "result", "defects", "inspector"].map(c => <th key={c}>{t(`fields.${c}`)}</th>)}
        </tr></thead>
        <tbody>{checks.map(c => <tr key={c.id}>
          <td><Link href={`/quality-checks/${c.id}`}><bdi>{c.inspection_code}</bdi></Link></td>
          <td>{fmt.dateTime(c.check_datetime)}</td>
          <td>{enums(`checkType.${c.check_type}`)}</td>
          <td>{c.order_number ? <Link href={`/production-orders/${c.production_order_id}`}><bdi>{c.order_number}</bdi></Link> : c.sample_code ? <bdi>{c.sample_code}</bdi> : "—"}</td>
          <td>{c.item_line_no ?? "—"}</td>
          <td><bdi>{fmt.quantity(c.qty_inspected, c.unit ?? "")}</bdi></td>
          <td><bdi>{c.status === "closed" ? fmt.quantity(c.qty_accepted, c.unit ?? "") : "—"}</bdi></td>
          <td><bdi>{c.status === "closed" ? fmt.quantity(c.qty_rejected, c.unit ?? "") : "—"}</bdi></td>
          <td><QualityCheckStatusBadge status={c.status} /></td>
          <td><QualityCheckResultBadge result={c.result} /></td>
          <td><DefectChips defects={c.defects ?? []} severity={c.severity} /></td>
          <td>{c.checked_by_name ?? "—"}</td>
        </tr>)}</tbody>
      </table></div>
    </section>}
  </PageFrame>;
}
