"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState, type ReactNode } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import s from "@/features/production-demands/demands.module.css";
import { useFormatter } from "@/hooks/useFormatter";
import { useUnitSymbol } from "../unit-symbol";
import { deleteWasteRecord, getWasteRecordById } from "../api";
import type { WasteRecordData } from "../types";
import { WasteCategoryBadge } from "./WasteCategoryBadge";
import { wasteErrorMessage } from "./waste-errors";

function Item({ label, children }: { label: string; children: ReactNode }) {
  return <div><dt className={s.muted}>{label}</dt><dd style={{ margin: "4px 0 0", overflowWrap: "anywhere" }}>{children}</dd></div>;
}

export function WasteRecordDetail({ recordId }: { recordId: string }) {
  const t = useTranslations("production.wasteRecords");
  const orderStatus = useTranslations("enums.productionOrder.status");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const unit = useUnitSymbol();
  const router = useRouter();
  const [record, setRecord] = useState<WasteRecordData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    getWasteRecordById(recordId).then(r => { if (active) setRecord(r); })
      .catch(e => { if (active) setError(wasteErrorMessage(e, t)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [recordId, t]);

  async function remove() {
    if (!record) return;
    setBusy(true); setError("");
    try { await deleteWasteRecord(record.id); router.push(`/waste-records?order=${record.production_order_id}`); }
    catch (e) { setError(wasteErrorMessage(e, t)); setConfirming(false); setBusy(false); }
  }

  const back = <Link href={record ? `/waste-records?order=${record.production_order_id}` : "/waste-records"} className={s.button}>{t("actions.backToList")}</Link>;
  if (loading) return <PageFrame title={t("detailTitle")} action={back}><p className={s.muted}>{messages("loading.default")}</p></PageFrame>;
  if (!record) return <PageFrame title={t("detailTitle")} action={back}><p role="alert" className={s.error}>{error || t("notFound")}</p></PageFrame>;
  const labels = record.labels;
  const actions = labels?.actions ?? [];

  return <PageFrame title={t("detailTitle")} subtitle={labels?.order_number ?? undefined} action={back}>
    {labels?.order_status === "closed" && <p role="status" className={s.muted}>{t("hints.locked")}</p>}
    {error && <p role="alert" className={s.error}>{error}</p>}
    <section className={s.panel}>
      <div className={s.actions} style={{ justifyContent: "space-between", marginBottom: 16 }}>
        <ul aria-label={t("fields.wasteCategories")} className={s.actions} style={{ listStyle: "none", padding: 0, margin: 0, flexWrap: "wrap" }}>
          {record.categories.map(c => <li key={c.category}><WasteCategoryBadge category={c.category} />
            {record.categories.length > 1 && <> <bdi>{fmt.quantity(c.quantity, unit(record.unit))}</bdi></>}</li>)}
        </ul>
        {actions.length > 0 && <span className={s.actions}>
          {actions.includes("edit") && <Link href={`/waste-records/${record.id}/edit`} className={s.button}>{t("actions.edit")}</Link>}
          {actions.includes("delete") && <button type="button" className={`${s.button} ${s.danger}`} disabled={busy} onClick={() => setConfirming(true)}>{t("actions.delete")}</button>}
        </span>}
      </div>
      <dl className={s.grid} style={{ margin: 0 }}>
        <Item label={t("fields.productionOrder")}><Link href={`/production-orders/${record.production_order_id}`}>{labels?.order_number ?? "—"}</Link></Item>
        <Item label={t("fields.orderStatus")}>{labels?.order_status ? orderStatus(labels.order_status) : "—"}</Item>
        <Item label={t("fields.line")}>{labels?.line_no ?? t("placeholders.wholeOrder")}</Item>
        <Item label={t("fields.quantityWasted")}><bdi>{fmt.quantity(record.quantity_wasted, unit(record.unit))}</bdi>
          {record.unit_needs_review && <p role="status" className={s.error}>{t("hints.unitReview", { unit: record.legacy_unit_text ?? record.unit })}</p>}</Item>
        <Item label={t("fields.wasteDate")}>{fmt.date(record.waste_date)}</Item>
        <Item label={t("fields.workCenter")}>{labels?.work_center_name ?? "—"}</Item>
        <Item label={t("fields.run")}>{labels?.run_date ? fmt.date(labels.run_date) : "—"}</Item>
        <Item label={t("fields.reasonCode")}>{record.reason_code ?? "—"}</Item>
        <Item label={t("fields.recordedBy")}>{labels?.created_by_name ?? "—"}</Item>
        <Item label={t("fields.createdAt")}>{fmt.dateTime(record.created_at)}</Item>
      </dl>
      {record.notes && <p style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}><span className={s.muted}>{t("fields.notes")}: </span>{record.notes}</p>}
    </section>
    {confirming && <div className={s.overlay} onKeyDown={e => { if (e.key === "Escape" && !busy) setConfirming(false); }}>
      <div role="dialog" aria-modal="true" aria-label={t("delete.title")} className={`${s.panel} ${s.dialog}`}>
        <h2>{t("delete.title")}</h2>
        <p className={s.muted}>{t("delete.text")}</p>
        <div className={s.actions}>
          <button type="button" className={s.button} disabled={busy} onClick={() => setConfirming(false)} autoFocus>{t("actions.cancel")}</button>
          <button type="button" className={`${s.button} ${s.danger}`} disabled={busy} onClick={() => void remove()}>{t("actions.delete")}</button>
        </div>
      </div>
    </div>}
  </PageFrame>;
}
