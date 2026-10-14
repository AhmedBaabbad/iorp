"use client";

import Link from "next/link";
import { useTranslations, useLocale } from "next-intl";
import { useEffect, useState, type FormEvent } from "react";

import s from "@/features/production-demands/demands.module.css";
import { useFormatter } from "@/hooks/useFormatter";
import { getBatchShipments } from "../api/quality-checks-api";
import { RETURN_PARTS, type BatchShipment, type QualityCheckData, type ReturnDecisionRequest, type ReturnPart } from "../types";
import { QUANTITY } from "./quality-errors";

import { joinList } from "@/lib/utils";
const thousandths = (value: string) => Math.round(Number(value || 0) * 1000);

// The returned goods an inspection is about, and every delivery note that carried the same production order
// (containment: who else has the goods, and what is about to leave).
export function ReturnSourceSection({ check }: { check: QualityCheckData }) {
  const t = useTranslations("quality.returns");
  const labels = useTranslations("shipping.returns");
  const statuses = useTranslations("shipping.statuses");
  const fmt = useFormatter();
  const units = useTranslations("common.units.units");
  const locale = useLocale();
  const unit = (code: string) => (units.has(code) ? units(code) : code);
  const [batch, setBatch] = useState<BatchShipment[] | null>(null);
  const source = check.return_source!;
  useEffect(() => {
    let active = true;
    if (check.production_order_id) getBatchShipments(check.id).then(v => { if (active) setBatch(v); }).catch(() => { if (active) setBatch([]); });
    return () => { active = false; };
  }, [check.id, check.production_order_id]);
  const leaving = (batch ?? []).filter(b => b.status === "ready");
  const batchTitle = t("batchTitle", { order: source.production_order_no ?? check.order_number ?? "" });

  return <>
    <section className={s.panel} aria-label={t("sourceTitle")}>
      <h2 style={{ marginTop: 0 }}>{t("sourceTitle")}</h2>
      <dl className={s.grid} style={{ margin: 0 }}>
        <div><dt className={s.muted}>{t("returnNo")}</dt><dd style={{ margin: "4px 0 0" }}><Link href={`/shipment-returns/${source.return_id}`}><bdi>{source.return_no}</bdi></Link></dd></div>
        <div><dt className={s.muted}>{t("note")}</dt><dd style={{ margin: "4px 0 0" }}><Link href={`/shipments/${source.shipment_id}`}><bdi>{source.shipment_no}</bdi></Link></dd></div>
        <div><dt className={s.muted}>{t("customer")}</dt><dd style={{ margin: "4px 0 0" }}>{source.customer_name}</dd></div>
        <div><dt className={s.muted}>{t("reason")}</dt><dd style={{ margin: "4px 0 0" }}>{labels(`reasons.${source.reason}`)} — {labels(`responsibility.${source.responsibility}`)}</dd></div>
        <div><dt className={s.muted}>{t("item")}</dt><dd style={{ margin: "4px 0 0" }}>{source.line_no}. {source.description}</dd></div>
      </dl>
      {source.details && <p style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}>{source.details}</p>}
    </section>
    {check.production_order_id && <section className={s.panel} aria-label={batchTitle}>
      <h2 style={{ marginTop: 0 }}>{batchTitle}</h2>
      <p className={s.muted} style={{ marginTop: 0 }}>{t("batchHint")}</p>
      {leaving.length > 0 && <p role="status" className={s.error}>{t("batchLeaving", { notes: joinList(leaving.map(b => b.shipment_no), locale) })}</p>}
      {batch === null ? null : batch.length === 0 ? <p className={s.muted} style={{ margin: 0 }}>{t("batchEmpty")}</p> : <div className={s.tableWrap}><table className={s.table}>
        <thead><tr><th>{t("note")}</th><th>{t("date")}</th><th>{t("customer")}</th><th>{t("quantity")}</th><th>{t("status")}</th></tr></thead>
        <tbody>{batch.map(b => <tr key={`${b.shipment_id}-${b.quantity}`}>
          <td><Link href={`/shipments/${b.shipment_id}`}><bdi>{b.shipment_no}</bdi></Link></td>
          <td>{fmt.date(b.shipment_date)}</td>
          <td>{b.customer_name}</td>
          <td><bdi>{fmt.quantity(b.delivered_quantity ?? b.quantity, unit(b.unit))}</bdi></td>
          <td>{statuses.has(b.status) ? statuses(b.status) : b.status}</td>
        </tr>)}</tbody>
      </table></div>}
    </section>}
  </>;
}

// Closes a return inspection: where each part of the inspected quantity goes. The parts add up to it.
export function ReturnDecisionDialog({ check, busy, onClose, onConfirm }: { check: QualityCheckData; busy: boolean; onClose: () => void;
  onConfirm: (body: ReturnDecisionRequest) => void }) {
  const t = useTranslations("quality.returns");
  const common = useTranslations("common");
  const fmt = useFormatter();
  const units = useTranslations("common.units.units");
  const unit = (code: string | null) => (code && units.has(code) ? units(code) : code ?? "");
  const [parts, setParts] = useState<Record<ReturnPart, string>>({ to_stock: "", use_as_is: "", rework: "", return_to_process: "", scrap: "", hold: "" });
  const [notes, setNotes] = useState("");
  const [approver, setApprover] = useState("");
  const [ncr, setNcr] = useState(true);
  const valid = RETURN_PARTS.every(p => !parts[p].trim() || QUANTITY.test(parts[p].trim()));
  const total = RETURN_PARTS.reduce((sum, p) => sum + (valid ? thousandths(parts[p]) : 0), 0);
  const balanced = valid && total === thousandths(check.qty_inspected);
  const rejected = total - thousandths(parts.to_stock);
  const concession = thousandths(parts.use_as_is) > 0;
  const ok = balanced && (!concession || Boolean(approver.trim() && notes.trim()));
  function submit(event: FormEvent) {
    event.preventDefault();
    if (!ok || busy) return;
    onConfirm({ ...Object.fromEntries(RETURN_PARTS.map(p => [p, parts[p].trim() || "0"])) as Record<ReturnPart, string>,
      notes: notes.trim() || null, concession_approved_by: concession ? approver.trim() : null, open_ncr: rejected > 0 && ncr });
  }
  return <div className={s.overlay} onKeyDown={e => { if (e.key === "Escape" && !busy) onClose(); }}>
    <form role="dialog" aria-modal="true" aria-label={t("decisionTitle")} className={`${s.panel} ${s.dialog}`} onSubmit={submit}>
      <h2 style={{ margin: 0 }}>{t("decisionTitle")}</h2>
      <p className={s.muted} style={{ margin: 0 }}>{t("decisionText", { quantity: fmt.quantity(check.qty_inspected, unit(check.unit)) })}</p>
      <div className={s.grid}>{RETURN_PARTS.map(p => <label key={p} className={s.field}>{t(`parts.${p}`)}
        <input inputMode="decimal" dir="ltr" value={parts[p]} disabled={busy} onChange={e => setParts(old => ({ ...old, [p]: e.target.value }))} />
        <span className={s.muted}>{t(`partHints.${p}`)}</span></label>)}</div>
      <p role="status" className={balanced ? s.muted : s.error} style={{ margin: 0 }}>
        {t("decisionTotal", { total: String(total / 1000), quantity: String(thousandths(check.qty_inspected) / 1000) })}</p>
      {concession && <label className={s.field}>{t("concessionBy")}<input required maxLength={255} value={approver} disabled={busy} onChange={e => setApprover(e.target.value)} /></label>}
      <label className={s.field}>{concession ? t("notesRequired") : t("notes")}<textarea maxLength={2000} required={concession} value={notes} disabled={busy} onChange={e => setNotes(e.target.value)} /></label>
      {rejected > 0 && <label><input type="checkbox" checked={ncr} disabled={busy} onChange={e => setNcr(e.target.checked)} /> {t("openNcr")}</label>}
      <div className={s.actions}>
        <button type="button" className={s.button} disabled={busy} onClick={onClose}>{common("actions.close")}</button>
        <button type="submit" className={`${s.button} ${s.primary}`} disabled={busy || !ok}>{t("decide")}</button>
      </div>
    </form>
  </div>;
}
