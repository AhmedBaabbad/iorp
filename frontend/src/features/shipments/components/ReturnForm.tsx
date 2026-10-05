"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState, type FormEvent } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import s from "@/features/production-demands/demands.module.css";
import { useFormatter } from "@/hooks/useFormatter";
import { createReturn, getShipment, getShippingSettings } from "../api";
import { DECIMAL, shippingErrorMessage } from "../shipping-errors";
import { CUSTOMER_REASONS, type CustomerReason, type Shipment } from "../types";

type Line = { quantity: string; weight: string };

// A customer's return of delivered goods, against its delivery note: the items and quantities coming back (up to what
// was delivered less earlier returns), the reason, and the customer's reference.
export function ReturnForm({ shipmentId }: { shipmentId: string }) {
  const t = useTranslations("shipping.returns");
  const shipping = useTranslations("shipping");
  const errors = useTranslations("shipping.errors");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const units = useTranslations("common.units.units");
  const unit = (code: string) => (units.has(code) ? units(code) : code);
  const router = useRouter();
  const [note, setNote] = useState<Shipment | null>(null);
  const [windowDays, setWindowDays] = useState<number | null>(null);
  const [loading, setLoading] = useState(Boolean(shipmentId));
  const [lines, setLines] = useState<Record<string, Line>>({});
  const [reason, setReason] = useState<CustomerReason | "">("");
  const [details, setDetails] = useState("");
  const [reference, setReference] = useState("");
  const [claim, setClaim] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!shipmentId) return;
    let active = true;
    getShipment(shipmentId).then(x => {
      if (!active) return;
      setNote(x); setReference(x.customer_reference ?? "");
      setLines(Object.fromEntries(x.lines.map(l => [l.id, { quantity: "", weight: "" }])));
    }).catch(e => { if (active) setError(shippingErrorMessage(e, errors)); }).finally(() => { if (active) setLoading(false); });
    getShippingSettings().then(v => { if (active) setWindowDays(v.return_window_days); }).catch(() => undefined);
    return () => { active = false; };
  }, [shipmentId, errors]);

  const back = note ? `/shipments/${note.id}` : "/shipment-returns";
  const backLink = <Link href={back} className={s.button}>{shipping("back")}</Link>;
  if (!shipmentId) return <PageFrame title={t("newTitle")} action={backLink}><p className={s.muted}>{t("chooseNote")}</p></PageFrame>;
  if (loading) return <PageFrame title={t("newTitle")} action={backLink}><p className={s.muted}>{messages("loading.default")}</p></PageFrame>;
  if (!note) return <PageFrame title={t("newTitle")} action={backLink}><p role="alert" className={s.error}>{error || shipping("notFound")}</p></PageFrame>;

  const available = (id: string) => Number(note.line_returns[id]?.returnable ?? 0);
  const chosen = note.lines.filter(l => (lines[l.id]?.quantity ?? "").trim());
  const linesOk = chosen.length > 0 && chosen.every(l => DECIMAL.test(lines[l.id].quantity.trim()) && Number(lines[l.id].quantity) > 0
    && Number(lines[l.id].quantity) <= available(l.id) && (!lines[l.id].weight.trim() || DECIMAL.test(lines[l.id].weight.trim())));
  const valid = linesOk && Boolean(reason) && (reason !== "other" || Boolean(details.trim()));
  const nothingLeft = note.lines.every(l => available(l.id) <= 0);
  const late = windowDays !== null && note.delivered_at !== null && Date.now() - new Date(note.delivered_at).getTime() > windowDays * 86400000;
  const setLine = (id: string, field: keyof Line, value: string) => setLines(old => ({ ...old, [id]: { ...old[id], [field]: value } }));

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid || busy) return;
    setBusy(true); setError("");
    try {
      const saved = await createReturn({ shipment_id: note!.id, reason: reason as CustomerReason, details: details.trim() || null,
        customer_reference: reference.trim() || null, carrier_claim_ref: claim.trim() || null,
        lines: chosen.map(l => ({ shipment_line_id: l.id, quantity: lines[l.id].quantity.trim(), weight: lines[l.id].weight.trim() || null })) });
      router.push(`/shipment-returns/${saved.id}`);
    } catch (e) { setError(shippingErrorMessage(e, errors)); setBusy(false); }
  }

  return <PageFrame title={t("newTitle")} subtitle={t("newSubtitle", { number: note.shipment_no })} action={backLink}>
    <form onSubmit={submit} aria-label={t("newTitle")}>
      {late && <p role="status" className={s.error}>{t("lateHint", { days: String(windowDays) })}</p>}
      {nothingLeft && <p role="status" className={s.error}>{t("nothingLeft")}</p>}
      <fieldset disabled={busy || nothingLeft} style={{ border: 0, padding: 0, margin: 0 }}>
        <section className={s.panel} aria-label={shipping("sections.lines")}>
          <h2 style={{ marginTop: 0 }}>{shipping("sections.lines")}</h2>
          <div className={s.tableWrap}><table className={s.table}>
            <thead><tr><th>#</th><th>{shipping("lineFields.description")}</th><th>{shipping("lineFields.delivered_quantity")}</th>
              <th>{t("returnQuantity")}</th><th>{t("returnWeight")}</th></tr></thead>
            <tbody>{note.lines.map(l => <tr key={l.id}>
              <td>{l.line_no}</td>
              <td>{l.description}{l.production_order_no && <div className={s.muted}><bdi dir="ltr">{l.production_order_no}</bdi></div>}</td>
              <td><bdi>{fmt.quantity(l.delivered_quantity ?? l.quantity, unit(l.unit))}</bdi>
                <div className={s.muted}>{t("available", { quantity: fmt.quantity(String(available(l.id)), unit(l.unit)) })}</div></td>
              <td><input inputMode="decimal" dir="ltr" style={{ maxWidth: 110 }} aria-label={`${t("returnQuantity")} ${l.line_no}`} value={lines[l.id]?.quantity ?? ""}
                disabled={available(l.id) <= 0} onChange={e => setLine(l.id, "quantity", e.target.value)} /></td>
              <td><span className={s.actions}><input inputMode="decimal" dir="ltr" style={{ maxWidth: 110 }} aria-label={`${t("returnWeight")} ${l.line_no}`}
                value={lines[l.id]?.weight ?? ""} disabled={available(l.id) <= 0} onChange={e => setLine(l.id, "weight", e.target.value)} />
                <span className={s.muted}>{unit(l.weight_unit)}</span></span></td>
            </tr>)}</tbody>
          </table></div>
          {!linesOk && <p className={s.muted} style={{ marginBottom: 0 }}>{t("linesHint")}</p>}
        </section>
        <section className={s.panel}>
          <div className={s.grid}>
            <label className={s.field}>{t("fields.reason")}
              <select required value={reason} onChange={e => setReason(e.target.value as CustomerReason)}>
                <option value="">—</option>{CUSTOMER_REASONS.map(r => <option key={r} value={r}>{t(`reasons.${r}`)}</option>)}
              </select></label>
            <label className={s.field}>{t("fields.customer_reference")}<input dir="ltr" maxLength={80} value={reference} onChange={e => setReference(e.target.value)} /></label>
            {reason === "transit_damage" && note.delivery_method === "carrier" &&
              <label className={s.field}>{t("fields.carrier_claim_ref")}<input dir="ltr" maxLength={80} value={claim} onChange={e => setClaim(e.target.value)} /></label>}
          </div>
          <label className={s.field}>{t("fields.details")}<textarea maxLength={4000} required={reason === "other"} value={details} onChange={e => setDetails(e.target.value)} /></label>
          <p className={s.muted} style={{ marginBottom: 0 }}>{t("qualityLater")}</p>
        </section>
      </fieldset>
      {error && <p role="alert" className={s.error}>{error}</p>}
      <div className={s.actions}>
        <button type="submit" className={`${s.button} ${s.primary}`} disabled={!valid || busy || nothingLeft}>{t("create")}</button>
        <Link href={back} className={s.button}>{shipping("cancel")}</Link>
      </div>
    </form>
  </PageFrame>;
}
