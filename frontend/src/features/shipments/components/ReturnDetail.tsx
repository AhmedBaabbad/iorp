"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { useHasAnyPermission } from "@/features/auth/permission-hooks";
import { ReasonDialog } from "@/features/production-demands/reason-dialog";
import s from "@/features/production-demands/demands.module.css";
import { useFormatter } from "@/hooks/useFormatter";
import { S } from "@/lib/shipping-permissions";
import { approveReturn, cancelReturn, downloadReturnNote, getReturn, receiveReturn, rejectReturn, type ReceiveBody } from "../api";
import { DECIMAL, shippingErrorMessage } from "../shipping-errors";
import { QUALITY_REASONS, type ShipmentReturn } from "../types";
import { Attachments } from "./Attachments";
import { ReturnStatusBadge } from "./ShipmentStatusBadge";
import { Signatures } from "@/components/Signatures";

function Item({ label, children }: { label: string; children: ReactNode }) {
  return <div><dt className={s.muted}>{label}</dt><dd style={{ margin: "4px 0 0", overflowWrap: "anywhere" }}>{children}</dd></div>;
}

type Dialog = "approve" | "reject" | "receive" | "cancel";

// One return: its delivery note, cause and responsibility, the items expected and received, the next step, photos,
// the PDF and the history.
export function ReturnDetail({ returnId }: { returnId: string }) {
  const t = useTranslations("shipping.returns");
  const shipping = useTranslations("shipping");
  const errors = useTranslations("shipping.errors");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const units = useTranslations("common.units.units");
  const unit = (code: string) => (units.has(code) ? units(code) : code);
  const canAttach = useHasAnyPermission([S.RETURNS_CREATE, S.RETURNS_APPROVE, S.RETURNS_RECEIVE]);
  const [x, setX] = useState<ShipmentReturn | null>(null);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try { setX(await getReturn(returnId)); } catch (e) { setError(shippingErrorMessage(e, errors)); } finally { setLoading(false); }
  }, [returnId, errors]);
  useEffect(() => { void load(); }, [load]);

  async function run(key: string, action: () => Promise<ShipmentReturn | void>) {
    setBusy(key); setError("");
    try { const result = await action(); if (result) setX(result); setDialog(null); }
    catch (e) { setError(shippingErrorMessage(e, errors)); } finally { setBusy(null); }
  }

  const back = <Link href="/shipment-returns" className={s.button}>{t("backToList")}</Link>;
  if (loading) return <PageFrame title={t("detailTitle")} action={back}><p className={s.muted}>{messages("loading.default")}</p></PageFrame>;
  if (!x) return <PageFrame title={t("detailTitle")} action={back}><p role="alert" className={s.error}>{error || t("notFound")}</p></PageFrame>;
  const received = x.status === "received";
  const kg = (value: string | null) => (value ? fmt.quantity(value, unit("kg")) : "—");
  const button = (action: Dialog, kind = s.primary) => x.actions.includes(action) &&
    <button type="button" className={`${s.button} ${kind}`} disabled={busy !== null} onClick={() => setDialog(action)}>{t(`actions.${action}`)}</button>;

  return <PageFrame title={x.return_no} subtitle={`${x.customer_name} — ${t(`kinds.${x.kind}`)}`} action={back}>
    {error && <p role="alert" className={s.error}>{error}</p>}
    <section className={s.panel}>
      <div className={s.actions} style={{ justifyContent: "space-between", marginBottom: 16 }}>
        <span className={s.actions}><ReturnStatusBadge status={x.status} />{x.is_late && <span className={`${s.badge} ${s.urgent}`}>{t("late")}</span>}</span>
        <span className={s.actions}>
          {(["ar", "en"] as const).map(lang => <button key={lang} type="button" className={s.button} disabled={busy !== null}
            onClick={() => void run(`pdf-${lang}`, () => downloadReturnNote(x.id, lang))}>{busy === `pdf-${lang}` ? shipping("preparing") : t(`download.${lang}`)}</button>)}
          {button("approve")}{button("reject", s.danger)}{button("receive")}{button("cancel", s.danger)}
        </span>
      </div>
      <p className={s.muted} style={{ marginTop: 0 }}>{t(`kindHints.${x.kind}`)}</p>
      <dl className={s.grid} style={{ margin: 0 }}>
        <Item label={t("fields.note")}><Link href={`/shipments/${x.shipment_id}`}><bdi>{x.shipment_no}</bdi></Link>
          {x.kind === "delivery" && x.attempt > 1 && <div className={s.muted}>{shipping("attemptBadge", { n: String(x.attempt) })}</div>}</Item>
        <Item label={t("fields.customer")}>{x.customer_name}</Item>
        <Item label={t("fields.requested_at")}>{fmt.dateTime(x.requested_at)} — {x.created_by_name ?? "—"}</Item>
        <Item label={t("fields.reason")}>{t(`reasons.${x.reason}`)}</Item>
        <Item label={t("fields.responsibility")}>{t(`responsibility.${x.responsibility}`)}</Item>
        <Item label={t("fields.customer_reference")}><bdi>{x.customer_reference ?? "—"}</bdi></Item>
        {x.carrier_claim_ref && <Item label={t("fields.carrier_claim_ref")}><bdi>{x.carrier_claim_ref}</bdi></Item>}
        {x.decided_at && <Item label={t("fields.decision")}>{fmt.dateTime(x.decided_at)} — {x.decided_by_name ?? "—"}
          {x.decision_note && <div style={{ whiteSpace: "pre-wrap" }}>{x.decision_note}</div>}</Item>}
        {x.received_at && <Item label={t("fields.received")}>{fmt.dateTime(x.received_at)} — {x.received_by_name ?? "—"}
          {x.receipt_notes && <div style={{ whiteSpace: "pre-wrap" }}>{x.receipt_notes}</div>}</Item>}
        {x.cancel_reason && <Item label={shipping("statuses.cancelled")}>{x.cancel_reason}</Item>}
      </dl>
      {x.details && <p style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}><span className={s.muted}>{t("fields.details")}: </span>{x.details}</p>}
    </section>
    <section className={s.panel} aria-label={shipping("sections.lines")}>
      <h2 style={{ marginTop: 0 }}>{shipping("sections.lines")}</h2>
      <div className={s.tableWrap}><table className={s.table}>
        <thead><tr><th>#</th>{["description", "width_mm", "thickness_mm"].map(c => <th key={c}>{shipping(`lineFields.${c}`)}</th>)}
          <th>{t("fields.returned")}</th><th>{t("fields.received_quantity")}</th><th>{t("fields.weight")}</th></tr></thead>
        <tbody>{x.lines.map(l => <tr key={l.id}>
          <td>{l.line_no}</td>
          <td>{l.description}{l.production_order_no && <div className={s.muted}>{shipping("lineFields.production_order")}: <bdi dir="ltr">{l.production_order_no}</bdi></div>}</td>
          <td><bdi>{l.width_mm !== null ? String(Number(l.width_mm)) : "—"}</bdi></td>
          <td><bdi>{l.thickness_mm !== null ? String(Number(l.thickness_mm)) : "—"}</bdi></td>
          <td><bdi>{fmt.quantity(l.quantity, unit(l.unit))}</bdi></td>
          <td><bdi>{received && l.received_quantity !== null ? fmt.quantity(l.received_quantity, unit(l.unit)) : "—"}</bdi></td>
          <td><bdi>{(received ? l.received_weight : l.weight) ? fmt.quantity((received ? l.received_weight : l.weight)!, unit(l.weight_unit)) : "—"}</bdi></td>
        </tr>)}</tbody>
      </table></div>
      <p className={s.muted} style={{ marginBottom: 0 }}>{shipping("totals", { quantities: x.quantities.map(q => fmt.quantity(q.quantity, unit(q.unit))).join(" · ") || "—",
        weight: kg(received ? x.received_weight_kg ?? x.weight_kg : x.weight_kg) })}</p>
    </section>
    {received && <QualityPanel value={x} />}
    <section className={s.panel} aria-label={shipping("sections.attachments")}>
      <h2 style={{ marginTop: 0 }}>{shipping("sections.attachments")}</h2>
      <Attachments owner={{ kind: "return", id: x.id }} files={x.attachments} kinds={["photo", "document"]}
        canChange={canAttach && x.status !== "rejected" && x.status !== "cancelled"} onChange={files => setX(old => (old ? { ...old, attachments: files } : old))} />
    </section>
    <section className={s.panel} aria-label={t("historyTitle")}>
      <h2 style={{ marginTop: 0 }}>{t("historyTitle")}</h2>
      <ol className={s.timeline}>{x.history.map((e, i) => <li key={`${e.at}-${i}`}>
        <strong>{shipping.has(`events.${e.action}`) ? shipping(`events.${e.action}`, { number: "" }) : e.action}</strong>
        <span className={s.muted}>{e.actor_name ?? "—"} · {fmt.dateTime(e.at)}</span>
        {e.reason && <span style={{ whiteSpace: "pre-wrap" }}>{e.reason}</span>}
      </li>)}</ol>
    </section>
    {dialog === "approve" && <ReasonDialog title={t("approveDialog.title")} description={x.is_late ? t("approveDialog.lateText") : t("approveDialog.text")}
      confirmLabel={t("actions.approve")} reasonRequired={x.is_late} busy={busy !== null} onClose={() => setDialog(null)}
      onConfirm={note => void run("approve", () => approveReturn(x.id, note || null))} />}
    {dialog === "reject" && <ReasonDialog title={t("rejectDialog.title")} description={t("rejectDialog.text")} confirmLabel={t("actions.reject")} danger
      busy={busy !== null} onClose={() => setDialog(null)} onConfirm={reason => void run("reject", () => rejectReturn(x.id, reason))} />}
    {dialog === "cancel" && <ReasonDialog title={t("cancelDialog.title")} description={t("cancelDialog.text")} confirmLabel={t("actions.cancel")} danger
      busy={busy !== null} onClose={() => setDialog(null)} onConfirm={reason => void run("cancel", () => cancelReturn(x.id, reason))} />}
    {dialog === "receive" && <ReceiveDialog value={x} busy={busy !== null} onClose={() => setDialog(null)}
      onConfirm={body => void run("receive", () => receiveReturn(x.id, body))} />}
      <Signatures resourceType="shipment_return" id={x.id} version={x.status} />
</PageFrame>;
}

function ReceiveDialog({ value, busy, onClose, onConfirm }: { value: ShipmentReturn; busy: boolean; onClose: () => void; onConfirm: (body: ReceiveBody) => void }) {
  const t = useTranslations("shipping.returns");
  const shipping = useTranslations("shipping");
  const fmt = useFormatter();
  const units = useTranslations("common.units.units");
  const unit = (code: string) => (units.has(code) ? units(code) : code);
  const [got, setGot] = useState<Record<string, { quantity: string; weight: string }>>(
    Object.fromEntries(value.lines.map(l => [l.id, { quantity: String(Number(l.quantity)), weight: l.weight !== null ? String(Number(l.weight)) : "" }])));
  const [notes, setNotes] = useState("");
  const required = QUALITY_REASONS.includes(value.reason);
  const [toQuality, setToQuality] = useState(required);
  const ok = value.lines.every(l => DECIMAL.test(got[l.id].quantity.trim()) && Number(got[l.id].quantity) <= Number(l.quantity)
    && (!got[l.id].weight.trim() || DECIMAL.test(got[l.id].weight.trim())));
  const set = (id: string, field: "quantity" | "weight", v: string) => setGot(old => ({ ...old, [id]: { ...old[id], [field]: v } }));
  function submit(event: FormEvent) {
    event.preventDefault();
    if (!ok || busy) return;
    onConfirm({ notes: notes.trim() || null, send_to_quality: toQuality, lines: value.lines.map(l => ({ return_line_id: l.id, received_quantity: got[l.id].quantity.trim(),
      received_weight: got[l.id].weight.trim() || null })) });
  }
  return <div className={s.overlay} onKeyDown={e => { if (e.key === "Escape" && !busy) onClose(); }}>
    <form role="dialog" aria-modal="true" aria-label={t("receiveDialog.title")} className={`${s.panel} ${s.dialog}`} onSubmit={submit}>
      <h2 style={{ margin: 0 }}>{t("receiveDialog.title")}</h2>
      <p className={s.muted} style={{ margin: 0 }}>{t("receiveDialog.text")}</p>
      {value.lines.map(l => <div key={l.id} className={s.grid}>
        <label className={s.field}>{`${l.line_no}. ${l.description}`} — {shipping("deliverDialog.of", { quantity: fmt.quantity(l.quantity, unit(l.unit)) })}
          <input inputMode="decimal" dir="ltr" aria-label={`${t("fields.received_quantity")} ${l.line_no}`} value={got[l.id].quantity} disabled={busy}
            onChange={e => set(l.id, "quantity", e.target.value)} /></label>
        <label className={s.field}>{`${t("fields.weight")} (${unit(l.weight_unit)})`}
          <input inputMode="decimal" dir="ltr" aria-label={`${t("fields.weight")} ${l.line_no}`} value={got[l.id].weight} disabled={busy}
            onChange={e => set(l.id, "weight", e.target.value)} /></label>
      </div>)}
      <label className={s.field}>{t("receiveDialog.notes")}<textarea maxLength={2000} value={notes} disabled={busy} onChange={e => setNotes(e.target.value)} /></label>
      <label><input type="checkbox" checked={toQuality} disabled={busy || required} onChange={e => setToQuality(e.target.checked)} /> {t("receiveDialog.toQuality")}</label>
      <p className={s.muted} style={{ margin: 0 }}>{required ? t("receiveDialog.qualityRequired") : t("receiveDialog.toStockHint")}</p>
      <div className={s.actions}>
        <button type="button" className={s.button} disabled={busy} onClick={onClose}>{shipping("cancel")}</button>
        <button type="submit" className={`${s.button} ${s.primary}`} disabled={busy || !ok}>{t("receiveDialog.confirm")}</button>
      </div>
    </form>
  </div>;
}

// What happened to the goods once back: in stock, or quality's inspections and decisions (read from quality).
function QualityPanel({ value }: { value: ShipmentReturn }) {
  const t = useTranslations("shipping.returns.quality");
  const fmt = useFormatter();
  const units = useTranslations("common.units.units");
  const unit = (code: string) => (units.has(code) ? units(code) : code);
  const status = value.quality_status;
  const quality = value.quality;
  return <section className={s.panel} aria-label={t("title")}>
    <h2 style={{ marginTop: 0 }}>{t("title")}</h2>
    {status && <p className={status === "done" || status === "not_required" ? s.muted : s.error} style={{ marginTop: 0 }}>{t(`status.${status}`)}</p>}
    {quality && quality.inspections.length > 0 && <ul style={{ margin: 0, paddingInlineStart: 18, display: "grid", gap: 6 }}>
      {quality.inspections.map(i => <li key={i.id}><Link href={`/quality-checks/${i.id}`}><bdi>{i.inspection_code}</bdi></Link>
        {" — "}{t.has(`checkStatus.${i.status}`) ? t(`checkStatus.${i.status}`) : i.status}
        {i.status === "closed" && <span className={s.muted}> · {t("toStock", { quantity: fmt.quantity(i.qty_accepted, "") })}</span>}</li>)}
    </ul>}
    {quality && quality.decisions.length > 0 && <div className={s.tableWrap} style={{ marginTop: 12 }}><table className={s.table}>
      <thead><tr><th>{t("decision")}</th><th>{t("quantity")}</th><th>{t("state")}</th></tr></thead>
      <tbody>{quality.decisions.map(d => <tr key={d.id}>
        <td>{d.disposition ? t(`dispositions.${d.disposition}`) : "—"}</td>
        <td><bdi>{fmt.quantity(d.quantity, unit(d.unit))}</bdi></td>
        <td>{t.has(`decisionStatus.${d.disposition_status}`) ? t(`decisionStatus.${d.disposition_status}`) : d.disposition_status}</td>
      </tr>)}</tbody>
    </table></div>}
  </section>;
}
