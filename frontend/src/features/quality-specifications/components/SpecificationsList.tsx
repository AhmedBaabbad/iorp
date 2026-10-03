"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { qualityErrorMessage } from "@/features/quality-checks/components/quality-errors";
import { useFormatter } from "@/hooks/useFormatter";
import { Q } from "@/lib/quality-permissions";
import { getSpecifications } from "../api";
import { SPEC_STATUSES, type SpecificationListItem, type SpecificationStatus } from "../types";
import { SpecificationStatusBadge } from "./SpecificationStatusBadge";

// "مواصفات المنتجات": the factory's technical data sheets, each a controlled document with revisions.
export function SpecificationsList() {
  const t = useTranslations("quality.specifications");
  const errors = useTranslations("quality.errors");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const canCreate = usePermission(Q.SPECS_CREATE);
  const [status, setStatus] = useState<SpecificationStatus | "">("");
  const [search, setSearch] = useState("");
  const [rows, setRows] = useState<SpecificationListItem[] | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try { setRows(await getSpecifications({ status, search })); } catch (e) { setError(qualityErrorMessage(e, errors)); }
  }, [status, search, errors]);
  useEffect(() => { void load(); }, [load]);

  return <PageFrame title={t("listTitle")} subtitle={t("subtitle")}
    action={<span className={s.actions}>
      <Link href="/quality-test-parameters" className={s.button}>{t("parameters")}</Link>
      {canCreate && <Link href="/quality-specifications/new" className={`${s.button} ${s.primary}`}>{t("newButton")}</Link>}
    </span>}>
    <section className={s.toolbar} aria-label={t("filtersAria")}>
      <label className={s.field}>{t("search")}<input type="search" value={search} placeholder={t("searchPlaceholder")} onChange={e => setSearch(e.target.value)} /></label>
      <label className={s.field}>{t("fields.status")}
        <select value={status} onChange={e => setStatus(e.target.value as SpecificationStatus | "")}>
          <option value="">{t("allStatuses")}</option>
          {SPEC_STATUSES.map(v => <option key={v} value={v}>{t(`statuses.${v}`)}</option>)}
        </select>
      </label>
    </section>
    {error && <p role="alert" className={s.error}>{error}</p>}
    {!error && rows === null && <p className={s.muted}>{messages("loading.default")}</p>}
    {!error && rows?.length === 0 && <section className={s.panel}><h2 style={{ marginTop: 0 }}>{t("empty")}</h2><p className={s.muted} style={{ margin: 0 }}>{t("emptyHint")}</p></section>}
    {!error && rows && rows.length > 0 && <section className={s.panel}>
      <div className={s.tableWrap}><table className={s.table} aria-label={t("listTitle")}>
        <thead><tr>{["code", "revision", "title", "productType", "grade", "status", "activatedAt"].map(c => <th key={c}>{t(`fields.${c}`)}</th>)}</tr></thead>
        <tbody>{rows.map(r => <tr key={r.id}>
          <td><Link href={`/quality-specifications/${r.id}`}><bdi>{r.code}</bdi></Link></td>
          <td>{r.revision}</td><td>{r.title}</td><td>{r.product_type}</td><td>{r.grade ?? "—"}</td>
          <td><SpecificationStatusBadge status={r.status} /></td>
          <td>{r.activated_at ? `${fmt.date(r.activated_at)} — ${r.activated_by_name ?? ""}` : "—"}</td>
        </tr>)}</tbody>
      </table></div>
    </section>}
  </PageFrame>;
}
