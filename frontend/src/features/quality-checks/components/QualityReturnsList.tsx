"use client";
import {useListPage} from "@/hooks/useListPage";
import {Pagination,ListToolbar} from "@/components/pagination";

import { useCustomerNames } from "@/features/customers/use-customer-names";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { useFormatter } from "@/hooks/useFormatter";
import { Q } from "@/lib/quality-permissions";
import { getAwaitingReturns, openReturnInspection } from "../api/quality-checks-api";
import type { AwaitingReturn } from "../types";
import { QualityCheckStatusBadge } from "./QualityCheckStatusBadge";
import { qualityErrorMessage } from "./quality-errors";

// "مرتجعات بانتظار الجودة": returned goods received for quality; one inspection per returned line, then its decision.
export function QualityReturnsList() {
  const t = useTranslations("quality.returns");
  const labels = useTranslations("shipping.returns");  // reasons and responsibility, as shipping names them
  const errors = useTranslations("quality.errors");
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const fmt = useFormatter();
  const units = useTranslations("common.units.units");
  const unit = (code: string) => (units.has(code) ? units(code) : code);
  const router = useRouter();
  const canOpen = usePermission(Q.CHECKS_CREATE);
  const page=useListPage<AwaitingReturn>({search:""});
  const {params,accept}=page;
  const [rows, setRows] = useState<AwaitingReturn[] | null>(null);
  const customerName = useCustomerNames((rows ?? []).map(row => row.customer_id));
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try { accept(await getAwaitingReturns(String(params.search??""),params),setRows); } catch (e) { setError(qualityErrorMessage(e, errors)); }
  }, [params,accept,errors]);
  useEffect(() => { const timer = setTimeout(() => void load(), 200); return () => clearTimeout(timer); }, [load]);

  async function open(lineId: string) {
    setBusy(lineId); setError("");
    try { router.push(`/quality-checks/${(await openReturnInspection(lineId)).id}`); }
    catch (e) { setError(qualityErrorMessage(e, errors)); setBusy(null); }
  }

  return <PageFrame title={t("title")} subtitle={t("subtitle")}>
    <ListToolbar search={page.filters.search} onSearch={value=>page.set("search",value)} searchHint={t("searchPlaceholder")} onClear={page.clear}/>
    {error && <div className={s.actions}><p role="alert" className={s.error}>{error}</p>
      <button type="button" className={s.button} onClick={() => void load()}>{common("actions.retry")}</button></div>}
    {rows === null && !error && <p className={s.muted}>{messages("loading.default")}</p>}
    {rows?.length === 0 && <section className={s.panel}><h2 style={{ marginTop: 0 }}>{t("empty")}</h2><p className={s.muted} style={{ margin: 0 }}>{t("emptyHint")}</p></section>}
    {rows?.map(r => <section key={r.return_id} className={s.panel} aria-label={r.return_no}>
      <div className={s.actions} style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}><Link href={`/shipment-returns/${r.return_id}`}><bdi>{r.return_no}</bdi></Link></h2>
        <span className={s.muted}>{r.received_at ? fmt.dateTime(r.received_at) : ""}</span>
      </div>
      <p style={{ margin: "8px 0" }}>{customerName(r.customer_id, r.customer_name)} — <Link href={`/shipments/${r.shipment_id}`}><bdi>{r.shipment_no}</bdi></Link>
        {" · "}{labels(`reasons.${r.reason}`)} · <span className={s.muted}>{t("responsibility")}: {labels(`responsibility.${r.responsibility}`)}</span></p>
      {r.details && <p className={s.muted} style={{ whiteSpace: "pre-wrap", marginTop: 0 }}>{r.details}</p>}
      <div className={s.tableWrap}><table className={s.table}>
        <thead><tr><th>#</th><th>{t("item")}</th><th>{t("productionOrder")}</th><th>{t("received")}</th><th>{t("inspection")}</th></tr></thead>
        <tbody>{r.lines.map(l => <tr key={l.line_id}>
          <td>{l.line_no}</td>
          <td>{l.description}{(l.width_mm || l.thickness_mm) && <div className={s.muted}><bdi dir="ltr">
            {[l.width_mm && `${Number(l.width_mm)} mm`, l.thickness_mm && `${Number(l.thickness_mm)} mm`].filter(Boolean).join(" × ")}</bdi></div>}</td>
          <td><bdi dir="ltr">{l.production_order_no ?? "—"}</bdi></td>
          <td><bdi>{l.received_quantity ? fmt.quantity(l.received_quantity, unit(l.unit)) : "—"}</bdi></td>
          <td>{l.inspection_id ? <span className={s.actions}><Link href={`/quality-checks/${l.inspection_id}`}><bdi>{l.inspection_code}</bdi></Link>
            {l.inspection_status && <QualityCheckStatusBadge status={l.inspection_status} />}</span>
            : canOpen ? <button type="button" className={`${s.button} ${s.primary}`} disabled={busy !== null} onClick={() => void open(l.line_id)}>
              {busy === l.line_id ? t("opening") : t("open")}</button> : <span className={s.muted}>{t("notOpened")}</span>}</td>
        </tr>)}</tbody>
      </table></div>
    </section>)}
    <Pagination {...page.pagination} disabled={rows===null||page.pending}/>
  </PageFrame>;
}
