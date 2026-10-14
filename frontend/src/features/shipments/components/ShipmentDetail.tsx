"use client";

import { TransportSelection, DriverAffiliation, type TransportValues } from "@/features/reference-directory/DirectorySelect";
import Link from "next/link";
import { useTranslations, useLocale } from "next-intl";
import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";

import { UnitSelect } from "@/components/forms/UnitSelect";
import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import { ReasonDialog } from "@/features/production-demands/reason-dialog";
import s from "@/features/production-demands/demands.module.css";
import { useFormatter } from "@/hooks/useFormatter";
import { S } from "@/lib/shipping-permissions";
import {
  cancelShipment, closeShipment, deliverShipment, dispatchShipment, downloadDeliveryNote, failShipment, getShipment, readyShipment, reopenShipment,
  rescheduleShipment, type DeliverBody, type RescheduleBody,
} from "../api";
import { DECIMAL, shippingErrorMessage, todayIso } from "../shipping-errors";
import { DELIVERY_METHODS, DELIVERY_REASONS, type DeliveryMethod, type DeliveryReason, type Shipment } from "../types";
import { Attachments } from "./Attachments";
import { ReturnStatusBadge, ShipmentStatusBadge } from "./ShipmentStatusBadge";
import { ListSelect, useListName } from "@/features/masterdata";

import { joinList } from "@/lib/utils";
function Item({ label, children }: { label: string; children: ReactNode }) {
  return <div><dt className={s.muted}>{label}</dt><dd style={{ margin: "4px 0 0", overflowWrap: "anywhere" }}>{children}</dd></div>;
}

const LEFT = ["dispatched", "returned", "delivered", "partially_delivered", "not_delivered"];
type Dialog = "dispatch" | "deliver" | "fail" | "reschedule" | "close" | "cancel";

// One delivery note: its parties, transport and lines, the next lifecycle step, what came back, the proof of delivery,
// the PDF and the history.
export function ShipmentDetail({ shipmentId }: { shipmentId: string }) {
  const t = useTranslations("shipping");
  const errors = useTranslations("shipping.errors");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const units = useTranslations("common.units.units");
  const locale = useLocale();
  const cityName = useListName("city");  // MD-002: the name, not the key
  const vehicleTypeName = useListName("vehicle_type");  // MD-003
  // Units are codes from the shared catalogue, shown in the screen's language (older free text as written).
  const unit = (code: string) => (units.has(code) ? units(code) : code);
  const canAttach = usePermission(S.SHIPMENTS_DELIVER);
  const [x, setX] = useState<Shipment | null>(null);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try { setX(await getShipment(shipmentId)); } catch (e) { setError(shippingErrorMessage(e, errors)); } finally { setLoading(false); }
  }, [shipmentId, errors]);
  useEffect(() => { void load(); }, [load]);

  async function run(key: string, action: () => Promise<Shipment | void>) {
    setBusy(key); setError("");
    try { const result = await action(); if (result) setX(result); setDialog(null); }
    catch (e) { setError(shippingErrorMessage(e, errors, f => t(`fields.${f}`))); } finally { setBusy(null); }
  }

  const back = <Link href="/shipments" className={s.button}>{t("backToList")}</Link>;
  if (loading) return <PageFrame title={t("detailTitle")} action={back}><p className={s.muted}>{messages("loading.default")}</p></PageFrame>;
  if (!x) return <PageFrame title={t("detailTitle")} action={back}><p role="alert" className={s.error}>{error || t("notFound")}</p></PageFrame>;
  const pickup = x.delivery_method === "pickup";
  const label = (key: string) => t(`fields.${key}`);
  const kg = (value: string | null) => (value ? fmt.quantity(value, unit("kg")) : "—");
  const numbers = (list: Shipment["returns"]) => joinList(list.map(r => r.return_no), locale);
  const coming = x.returns.filter(r => r.kind === "delivery" && r.status === "approved");
  const atDoor = x.returns.filter(r => r.kind === "delivery" && r.attempt === x.attempt);
  const received = x.status === "delivered" || x.status === "partially_delivered";
  const anyReturned = Object.values(x.line_returns).some(v => Number(v.returned) > 0);
  const button = (action: Dialog, text: string, kind = s.primary) => x.actions.includes(action) &&
    <button type="button" className={`${s.button} ${kind}`} disabled={busy !== null} onClick={() => setDialog(action)}>{text}</button>;

  return <PageFrame title={x.shipment_no} subtitle={`${x.customer_name} — ${t(`methods.${x.delivery_method}`)}`} action={back}>
    {x.status === "draft" && x.missing_details.length > 0 && <p role="status" className={s.muted}>
      {t("missingHint", { fields: joinList(x.missing_details.map(label), locale) })}</p>}
    {x.status === "cancelled" && <p role="status" className={s.error}>{t("cancelledHint", { reason: x.cancel_reason ?? "" })}</p>}
    {x.status === "returned" && <p role="status" className={s.error}>{coming.length ? t("returningHint", { numbers: numbers(coming) }) : t("backHint")}</p>}
    {x.status === "not_delivered" && <p role="status" className={s.error}>{t("notDeliveredHint", { reason: x.close_reason ?? "" })}</p>}
    {x.status === "partially_delivered" && atDoor.length > 0 && <p role="status" className={s.muted}>{t("partialHint", { numbers: numbers(atDoor) })}</p>}
    {error && <p role="alert" className={s.error}>{error}</p>}
    <section className={s.panel}>
      <div className={s.actions} style={{ justifyContent: "space-between", marginBottom: 16 }}>
        <span className={s.actions}>
          <ShipmentStatusBadge status={x.status} />
          {x.attempt > 1 && <span className={`${s.badge} ${s.high}`}>{t("attemptBadge", { n: String(x.attempt) })}</span>}
        </span>
        <span className={s.actions}>
          {(["ar", "en"] as const).map(lang => <button key={lang} type="button" className={s.button} disabled={busy !== null}
            onClick={() => void run(`pdf-${lang}`, () => downloadDeliveryNote(x.id, lang))}>{busy === `pdf-${lang}` ? t("preparing") : t(`download.${lang}`)}</button>)}
          {x.actions.includes("edit") && <Link href={`/shipments/${x.id}/edit`} className={s.button}>{t("actions.edit")}</Link>}
          {x.actions.includes("ready") && <button type="button" className={`${s.button} ${s.primary}`} disabled={busy !== null}
            onClick={() => void run("ready", () => readyShipment(x.id))}>{t("actions.ready")}</button>}
          {x.actions.includes("reopen") && <button type="button" className={s.button} disabled={busy !== null}
            onClick={() => void run("reopen", () => reopenShipment(x.id))}>{t("actions.reopen")}</button>}
          {button("dispatch", t("actions.dispatch"))}
          {button("deliver", pickup ? t("actions.collected") : t("actions.deliver"))}
          {button("fail", t("actions.fail"), s.danger)}
          {button("reschedule", t("actions.reschedule"))}
          {button("close", t("actions.close"), s.danger)}
          {x.actions.includes("return") && <Link href={`/shipment-returns/new?shipment=${x.id}`} className={s.button}>{t("actions.return")}</Link>}
          {button("cancel", t("actions.cancel"), s.danger)}
        </span>
      </div>
      <dl className={s.grid} style={{ margin: 0 }}>
        <Item label={label("date")}>{fmt.date(x.shipment_date)}</Item>
        <Item label={label("customer")}>{x.customer_name}{!x.customer_id && <div className={s.muted}>{t("namedCustomer")}</div>}</Item>
        <Item label={label("customer_reference")}><bdi>{x.customer_reference ?? "—"}</bdi></Item>
        <Item label={label("consignee_name")}>{x.consignee_name ?? x.customer_name}</Item>
        <Item label={label("consignee_phone")}><bdi dir="ltr">{x.consignee_phone ?? "—"}</bdi>{x.notify_consignee && <div className={s.muted}>{t("willNotify")}</div>}</Item>
        <Item label={label("consignee_email")}><bdi dir="ltr">{x.consignee_email ?? "—"}</bdi></Item>
        <Item label={label("delivery_city")}>{x.delivery_city ? cityName(x.delivery_city) : "—"}</Item>
        <Item label={label("delivery_address")}>{x.delivery_address ?? "—"}{x.location_url && <div><a href={x.location_url} target="_blank" rel="noopener noreferrer">{t("openLocation")}</a></div>}</Item>
      </dl>
    </section>
    <section className={s.panel} aria-label={t("sections.transport")}>
      <h2 style={{ marginTop: 0 }}>{t("sections.transport")}</h2>
      <dl className={s.grid} style={{ margin: 0 }}>
        {x.delivery_method === "carrier" ? <>
          <Item label={label("carrier_name")}>{x.carrier_name ?? "—"}</Item>
          <Item label={label("tracking_no")}><bdi dir="ltr">{x.tracking_no ?? "—"}</bdi></Item>
        </> : <>
          <Item label={pickup ? label("collector_name") : label("driver_name")}>{x.driver_name ?? "—"} — <DriverAffiliation value={x.driver_affiliation}/></Item>
          <Item label={label("driver_phone")}><bdi dir="ltr">{x.driver_phone ?? "—"}</bdi></Item>
          {pickup && <Item label={label("driver_id_no")}><bdi dir="ltr">{x.driver_id_no ?? "—"}</bdi></Item>}
          <Item label={label("vehicle_plate")}><bdi>{x.vehicle_plate ?? "—"}</bdi></Item>
          <Item label={label("vehicle_type")}>{vehicleTypeName(x.vehicle_type)}</Item>
        </>}
        <Item label={label("dispatched_at")}>{x.dispatched_at ? `${fmt.dateTime(x.dispatched_at)} — ${x.dispatched_by_name ?? ""}` : "—"}</Item>
        <Item label={label("received_by_name")}>{x.received_by_name ? `${x.received_by_name} — ${fmt.dateTime(x.delivered_at!)}` : "—"}</Item>
      </dl>
      {x.delivery_notes && <p style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}><span className={s.muted}>{label("delivery_notes")}: </span>{x.delivery_notes}</p>}
    </section>
    <section className={s.panel} aria-label={t("sections.lines")}>
      <h2 style={{ marginTop: 0 }}>{t("sections.lines")}</h2>
      <div className={s.tableWrap}><table className={s.table}>
        <thead><tr>
          <th>#</th>{["description", "width_mm", "thickness_mm", "quantity"].map(c => <th key={c}>{t(`lineFields.${c}`)}</th>)}
          {received && <th>{t("lineFields.delivered_quantity")}</th>}
          {anyReturned && <th>{t("lineFields.returned_quantity")}</th>}
          <th>{t("lineFields.weight")}</th>
        </tr></thead>
        <tbody>{x.lines.map(l => <tr key={l.id}>
          <td>{l.line_no}</td>
          <td>{l.description}{l.production_order_no && <div className={s.muted}>{t("lineFields.production_order")}: <bdi dir="ltr">{l.production_order_no}</bdi></div>}</td>
          <td><bdi>{l.width_mm !== null ? String(Number(l.width_mm)) : "—"}</bdi></td>
          <td><bdi>{l.thickness_mm !== null ? String(Number(l.thickness_mm)) : "—"}</bdi></td>
          <td><bdi>{fmt.quantity(l.quantity, unit(l.unit))}</bdi></td>
          {received && <td><bdi>{l.delivered_quantity !== null ? fmt.quantity(l.delivered_quantity, unit(l.unit)) : "—"}</bdi></td>}
          {anyReturned && <td><bdi>{fmt.quantity(x.line_returns[l.id]?.returned ?? "0", unit(l.unit))}</bdi></td>}
          <td><bdi>{l.weight ? fmt.quantity(l.weight, unit(l.weight_unit)) : "—"}</bdi></td>
        </tr>)}</tbody>
      </table></div>
      <p className={s.muted} style={{ marginBottom: 0 }}>{t("totals", { quantities: x.quantities.map(q => fmt.quantity(q.quantity, unit(q.unit))).join(" · ") || "—",
        weight: kg(x.weight_total_kg) })}</p>
    </section>
    {(x.gate_weight_kg || x.received_weight_kg) && <section className={s.panel} aria-label={t("weightCheck.title")}>
      <h2 style={{ marginTop: 0 }}>{t("weightCheck.title")}</h2>
      <dl className={s.grid} style={{ margin: 0 }}>
        <Item label={label("gate_weight")}><bdi>{kg(x.gate_weight_kg)}</bdi></Item>
        <Item label={label("received_weight")}><bdi>{kg(x.received_weight_kg)}</bdi></Item>
        {x.weight_check && <>
          <Item label={t("weightCheck.reference")}><bdi>{kg(x.weight_check.reference_kg)}</bdi></Item>
          <Item label={t("weightCheck.difference")}><bdi dir="ltr">{`${fmt.quantity(x.weight_check.difference_kg, unit("kg"))} (${Number(x.weight_check.difference_pct)}%)`}</bdi>
            <div className={x.weight_check.within_tolerance ? s.muted : s.error}>
              {t(x.weight_check.within_tolerance ? "weightCheck.within" : "weightCheck.outside", { tolerance: String(Number(x.weight_check.tolerance_pct)) })}</div></Item>
        </>}
      </dl>
    </section>}
    {x.returns.length > 0 && <section className={s.panel} aria-label={t("sections.returns")}>
      <h2 style={{ marginTop: 0 }}>{t("sections.returns")}</h2>
      <ul style={{ margin: 0, paddingInlineStart: 18, display: "grid", gap: 6 }}>{x.returns.map(r => <li key={r.id}>
        <Link href={`/shipment-returns/${r.id}`}><bdi>{r.return_no}</bdi></Link> — {t(`returns.kinds.${r.kind}`)} · {t(`returns.reasons.${r.reason}`)}
        {r.kind === "delivery" && x.attempt > 1 && <span className={s.muted}> · {t("attemptBadge", { n: String(r.attempt) })}</span>} <ReturnStatusBadge status={r.status} />
      </li>)}</ul>
    </section>}
    {LEFT.includes(x.status) && <section className={s.panel} aria-label={t("sections.attachments")}>
      <h2 style={{ marginTop: 0 }}>{t("sections.attachments")}</h2>
      <Attachments owner={{ kind: "shipment", id: x.id }} files={x.attachments} kinds={["proof_of_delivery", "document"]} canChange={canAttach}
        onChange={files => setX(old => (old ? { ...old, attachments: files } : old))} />
    </section>}
    {x.notes && <section className={s.panel}><h2 style={{ marginTop: 0 }}>{label("notes")}</h2><p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{x.notes}</p></section>}
    <section className={s.panel} aria-label={t("historyTitle")}>
      <h2 style={{ marginTop: 0 }}>{t("historyTitle")}</h2>
      <ol className={s.timeline}>{x.history.map((e, i) => <li key={`${e.at}-${i}`}>
        <strong>{t.has(`events.${e.action}`) ? t(`events.${e.action}`, { number: e.return_no ?? "" }) : e.action}</strong>
        <span className={s.muted}>{e.actor_name ?? "—"} · {fmt.dateTime(e.at)}</span>
        {e.reason && <span style={{ whiteSpace: "pre-wrap" }}>{e.reason}</span>}
      </li>)}</ol>
    </section>
    {dialog === "dispatch" && <DispatchDialog transport={x.delivery_method === "carrier" ? (x.carrier_name ?? "") : `${x.driver_name ?? ""} — ${x.vehicle_plate ?? ""}`}
      busy={busy !== null} onClose={() => setDialog(null)} onConfirm={body => void run("dispatch", () => dispatchShipment(x.id, body))} />}
    {dialog === "deliver" && <DeliverDialog shipment={x} busy={busy !== null} onClose={() => setDialog(null)}
      onConfirm={body => void run("deliver", () => deliverShipment(x.id, body))} />}
    {dialog === "fail" && <FailDialog busy={busy !== null} onClose={() => setDialog(null)} onConfirm={body => void run("fail", () => failShipment(x.id, body))} />}
    {dialog === "reschedule" && <RescheduleDialog shipment={x} busy={busy !== null} onClose={() => setDialog(null)}
      onConfirm={body => void run("reschedule", () => rescheduleShipment(x.id, body))} />}
    {dialog === "close" && <ReasonDialog title={t("closeDialog.title")} description={t("closeDialog.text")} confirmLabel={t("actions.close")}
      busy={busy !== null} danger onClose={() => setDialog(null)} onConfirm={reason => void run("close", () => closeShipment(x.id, reason))} />}
    {dialog === "cancel" && <ReasonDialog title={t("cancelDialog.title")} description={t("cancelDialog.text")} confirmLabel={t("actions.cancel")}
      busy={busy !== null} danger onClose={() => setDialog(null)} onConfirm={reason => void run("cancel", () => cancelShipment(x.id, reason))} />}
  </PageFrame>;
}

function Modal({ title, busy, onClose, onSubmit, children }: { title: string; busy: boolean; onClose: () => void; onSubmit: (e: FormEvent) => void; children: ReactNode }) {
  return <div className={s.overlay} onKeyDown={e => { if (e.key === "Escape" && !busy) onClose(); }}>
    <form role="dialog" aria-modal="true" aria-label={title} className={`${s.panel} ${s.dialog}`} onSubmit={onSubmit}>
      <h2 style={{ margin: 0 }}>{title}</h2>
      {children}
    </form>
  </div>;
}

const optionalDecimal = (v: string) => !v.trim() || DECIMAL.test(v.trim());

function DispatchDialog({ transport, busy, onClose, onConfirm }: { transport: string; busy: boolean; onClose: () => void;
  onConfirm: (body: { gate_weight: string | null; gate_weight_unit: string }) => void }) {
  const t = useTranslations("shipping");
  const [weight, setWeight] = useState("");
  const [weightUnit, setWeightUnit] = useState("kg");
  const ok = optionalDecimal(weight);
  return <Modal title={t("dispatchDialog.title")} busy={busy} onClose={onClose}
    onSubmit={e => { e.preventDefault(); if (ok && !busy) onConfirm({ gate_weight: weight.trim() || null, gate_weight_unit: weightUnit }); }}>
    <p className={s.muted}>{t("dispatchDialog.text", { transport })}</p>
    <div className={s.grid}>
      <label className={s.field}>{t("dispatchDialog.gateWeight")}<input inputMode="decimal" dir="ltr" value={weight} disabled={busy} onChange={e => setWeight(e.target.value)} /></label>
      <label className={s.field}>{t("dispatchDialog.weightUnit")}
        <UnitSelect value={weightUnit} onChange={v => setWeightUnit(v || "kg")} groups={["weight"]} ariaLabel={t("dispatchDialog.weightUnit")} /></label>
    </div>
    <div className={s.actions}>
      <button type="button" className={s.button} disabled={busy} onClick={onClose} autoFocus>{t("cancel")}</button>
      <button type="submit" className={`${s.button} ${s.primary}`} disabled={busy || !ok}>{t("actions.dispatch")}</button>
    </div>
  </Modal>;
}

function DeliverDialog({ shipment, busy, onClose, onConfirm }: { shipment: Shipment; busy: boolean; onClose: () => void; onConfirm: (body: DeliverBody) => void }) {
  const t = useTranslations("shipping");
  const fmt = useFormatter();
  const units = useTranslations("common.units.units");
  const locale = useLocale();
  const unit = (code: string) => (units.has(code) ? units(code) : code);
  const pickup = shipment.delivery_method === "pickup";
  const [name, setName] = useState(pickup ? shipment.driver_name ?? "" : shipment.consignee_name ?? "");
  const [notes, setNotes] = useState("");
  const [taken, setTaken] = useState<Record<string, string>>(Object.fromEntries(shipment.lines.map(l => [l.id, String(Number(l.quantity))])));
  const [reason, setReason] = useState<DeliveryReason | "">("");
  const [details, setDetails] = useState("");
  const [weight, setWeight] = useState("");
  const [weightUnit, setWeightUnit] = useState("kg");
  const title = pickup ? t("deliverDialog.pickupTitle") : t("deliverDialog.title");
  const valid = shipment.lines.every(l => DECIMAL.test((taken[l.id] ?? "").trim()) && Number(taken[l.id]) <= Number(l.quantity));
  const short = shipment.lines.filter(l => valid && Number(taken[l.id]) < Number(l.quantity));
  const ok = Boolean(name.trim()) && valid && (!short.length || Boolean(reason)) && optionalDecimal(weight);
  function submit(event: FormEvent) {
    event.preventDefault();
    if (!ok || busy) return;
    onConfirm({ received_by_name: name.trim(), delivery_notes: notes.trim() || null,
      lines: short.map(l => ({ line_id: l.id, delivered_quantity: taken[l.id].trim() })),
      refusal_reason: short.length ? (reason as DeliveryReason) : null, refusal_details: short.length ? details.trim() || null : null,
      received_weight: weight.trim() || null, received_weight_unit: weightUnit });
  }
  return <Modal title={title} busy={busy} onClose={onClose} onSubmit={submit}>
    <p className={s.muted} style={{ margin: 0 }}>{t("deliverDialog.text")}</p>
    <label className={s.field}>{t("fields.received_by_name")}<input required autoFocus maxLength={200} value={name} disabled={busy} onChange={e => setName(e.target.value)} /></label>
    {!pickup && <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
      <legend className={s.muted}>{t("deliverDialog.lines")}</legend>
      {shipment.lines.map(l => <label key={l.id} className={s.field}>{`${l.line_no}. ${l.description}`}
        <span className={s.actions}><input inputMode="decimal" dir="ltr" style={{ maxWidth: 120 }} value={taken[l.id]} disabled={busy}
          aria-label={`${t("lineFields.delivered_quantity")} ${l.line_no}`} onChange={e => setTaken(old => ({ ...old, [l.id]: e.target.value }))} />
          <span className={s.muted}>{t("deliverDialog.of", { quantity: fmt.quantity(l.quantity, unit(l.unit)) })}</span></span>
      </label>)}
    </fieldset>}
    {short.length > 0 && <>
      <p role="status" className={s.error} style={{ margin: 0 }}>{t("deliverDialog.partial", {
        items: joinList(short.map(l => `${l.line_no}: ${fmt.quantity(String(Number(l.quantity) - Number(taken[l.id])), unit(l.unit))}`), locale) })}</p>
      <label className={s.field}>{t("deliverDialog.refusalReason")}
        <select required value={reason} disabled={busy} onChange={e => setReason(e.target.value as DeliveryReason)}>
          <option value="">—</option>{DELIVERY_REASONS.map(r => <option key={r} value={r}>{t(`returns.reasons.${r}`)}</option>)}
        </select></label>
      <label className={s.field}>{t("deliverDialog.refusalDetails")}<textarea maxLength={2000} value={details} disabled={busy} onChange={e => setDetails(e.target.value)} /></label>
    </>}
    <div className={s.grid}>
      <label className={s.field}>{t("deliverDialog.receivedWeight")}<input inputMode="decimal" dir="ltr" value={weight} disabled={busy} onChange={e => setWeight(e.target.value)} /></label>
      <label className={s.field}>{t("dispatchDialog.weightUnit")}
        <UnitSelect value={weightUnit} onChange={v => setWeightUnit(v || "kg")} groups={["weight"]} ariaLabel={t("dispatchDialog.weightUnit")} /></label>
    </div>
    <label className={s.field}>{t("fields.delivery_notes")}<textarea maxLength={2000} value={notes} disabled={busy} onChange={e => setNotes(e.target.value)} /></label>
    <div className={s.actions}>
      <button type="button" className={s.button} disabled={busy} onClick={onClose}>{t("cancel")}</button>
      <button type="submit" className={`${s.button} ${s.primary}`} disabled={busy || !ok}>{t("deliverDialog.confirm")}</button>
    </div>
  </Modal>;
}

function FailDialog({ busy, onClose, onConfirm }: { busy: boolean; onClose: () => void; onConfirm: (body: { reason: DeliveryReason; details: string | null }) => void }) {
  const t = useTranslations("shipping");
  const [reason, setReason] = useState<DeliveryReason | "">("");
  const [details, setDetails] = useState("");
  const ok = Boolean(reason) && (reason !== "other" || Boolean(details.trim()));
  return <Modal title={t("failDialog.title")} busy={busy} onClose={onClose}
    onSubmit={e => { e.preventDefault(); if (ok && !busy) onConfirm({ reason: reason as DeliveryReason, details: details.trim() || null }); }}>
    <p className={s.muted} style={{ margin: 0 }}>{t("failDialog.text")}</p>
    <label className={s.field}>{t("failDialog.reason")}
      <select required autoFocus value={reason} disabled={busy} onChange={e => setReason(e.target.value as DeliveryReason)}>
        <option value="">—</option>{DELIVERY_REASONS.map(r => <option key={r} value={r}>{t(`returns.reasons.${r}`)}</option>)}
      </select></label>
    <label className={s.field}>{t("failDialog.details")}<textarea maxLength={2000} required={reason === "other"} value={details} disabled={busy} onChange={e => setDetails(e.target.value)} /></label>
    <div className={s.actions}>
      <button type="button" className={s.button} disabled={busy} onClick={onClose}>{t("cancel")}</button>
      <button type="submit" className={`${s.button} ${s.danger}`} disabled={busy || !ok}>{t("failDialog.confirm")}</button>
    </div>
  </Modal>;
}

type Transport = Required<{ [K in keyof RescheduleBody]: string }>;

function RescheduleDialog({ shipment, busy, onClose, onConfirm }: { shipment: Shipment; busy: boolean; onClose: () => void; onConfirm: (body: RescheduleBody) => void }) {
  const t = useTranslations("shipping");
  const [transport,setTransport]=useState<TransportValues>({driver_id:shipment.driver_id,vehicle_id:shipment.vehicle_id,carrier_id:shipment.carrier_id,driver_affiliation:shipment.driver_affiliation});
  const [v, setV] = useState<Transport>({
    delivery_method: shipment.delivery_method, shipment_date: todayIso(), driver_name: shipment.driver_name ?? "", driver_phone: shipment.driver_phone ?? "",
    driver_id_no: shipment.driver_id_no ?? "", vehicle_plate: shipment.vehicle_plate ?? "", vehicle_type: shipment.vehicle_type ?? "",
    carrier_name: shipment.carrier_name ?? "", tracking_no: shipment.tracking_no ?? "",
  });
  const set = (field: keyof Transport, value: string) => setV(old => ({ ...old, [field]: value }));
  const method = v.delivery_method as DeliveryMethod;
  const ok = Boolean(v.shipment_date) && (method === "carrier" ? Boolean(transport.carrier_id || v.carrier_name.trim()) : Boolean((transport.driver_id || v.driver_name.trim()) && (transport.vehicle_id || v.vehicle_plate.trim())));
  const input = (field: keyof Transport, text: string, extra: Record<string, unknown> = {}) =>
    <label className={s.field}>{text}<input value={v[field]} disabled={busy} onChange={e => set(field, e.target.value)} {...extra} /></label>;
  function submit(event: FormEvent) {
    event.preventDefault();
    if (!ok || busy) return;
    onConfirm({...Object.fromEntries(Object.entries(v).map(([k, value]) => [k, value.trim() || null])),...transport} as RescheduleBody);
  }
  return <Modal title={t("rescheduleDialog.title")} busy={busy} onClose={onClose} onSubmit={submit}>
    <p className={s.muted} style={{ margin: 0 }}>{t("rescheduleDialog.text", { n: String(shipment.attempt + 1) })}</p><TransportSelection value={transport} onChange={setTransport} carrier={method==="carrier"}/>
    <div className={s.grid}>
      <label className={s.field}>{t("fields.date")}<input type="date" required value={v.shipment_date} disabled={busy} onChange={e => set("shipment_date", e.target.value)} /></label>
      <label className={s.field}>{t("fields.method")}
        <select value={method} disabled={busy} onChange={e => set("delivery_method", e.target.value)}>
          {DELIVERY_METHODS.map(m => <option key={m} value={m}>{t(`methods.${m}`)}</option>)}
        </select></label>
      {method === "carrier" ? <>
        {input("carrier_name", t("fields.carrier_name"), { maxLength: 200, required: !transport.carrier_id, disabled:!!transport.carrier_id })}
        {input("tracking_no", t("fields.tracking_no"), { maxLength: 80, dir: "ltr" })}
      </> : <>
        {input("driver_name", method === "pickup" ? t("fields.collector_name") : t("fields.driver_name"), { maxLength: 200, required: !transport.driver_id, disabled:!!transport.driver_id })}
        {input("driver_phone", t("fields.driver_phone"), { maxLength: 30, dir: "ltr", inputMode: "tel" })}
        {method === "pickup" && input("driver_id_no", t("fields.driver_id_no"), { maxLength: 40, dir: "ltr" })}
        {input("vehicle_plate", t("fields.vehicle_plate"), { maxLength: 40, required: !transport.vehicle_id, disabled:!!transport.vehicle_id })}
        <label className={s.field}>{t("fields.vehicle_type")}
          <ListSelect list="vehicle_type" value={v.vehicle_type} disabled={busy} ariaLabel={t("fields.vehicle_type")} onChange={key => set("vehicle_type", key)} /></label>
      </>}
    </div>
    <div className={s.actions}>
      <button type="button" className={s.button} disabled={busy} onClick={onClose}>{t("cancel")}</button>
      <button type="submit" className={`${s.button} ${s.primary}`} disabled={busy || !ok}>{t("rescheduleDialog.confirm")}</button>
    </div>
  </Modal>;
}
