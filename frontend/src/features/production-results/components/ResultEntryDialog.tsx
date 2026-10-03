"use client";

import { useId, useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import s from "@/features/production-demands/demands.module.css";
import { customerRoom, DISPOSITIONS, exceeds, FIXED_LOSS, lossFor, QUANTITY, specSummary } from "../result-rules";
import type { Disposition, OrderResult, ResultEntryInput, ResultOriginal } from "../types";

// Add or edit one result entry while the order is completed.
export function ResultEntryDialog({ view, entry, busy, error, onSave, onClose }: {
  view: OrderResult; entry: ResultOriginal | null; busy: boolean; error: string;
  onSave: (body: ResultEntryInput) => void; onClose: () => void;
}) {
  const t = useTranslations("production.results");
  const id = useId();
  const multi = view.items.length > 1;
  const [disposition, setDisposition] = useState<Disposition>(entry?.disposition ?? "stock_good");
  const [itemId, setItemId] = useState<string>(entry?.production_order_item_id ?? (view.items.length === 1 ? view.items[0].id : ""));
  const [quantity, setQuantity] = useState(entry?.quantity ?? "");
  const [secondaryQuantity, setSecondaryQuantity] = useState(entry?.secondary_quantity ?? "");
  const [secondaryUnit, setSecondaryUnit] = useState(entry?.secondary_unit ?? "");
  const [sampleLoss, setSampleLoss] = useState<boolean | null>(entry?.disposition === "sample" ? entry.counts_as_loss : null);
  const [reasonCode, setReasonCode] = useState(entry?.reason_code ?? "");
  const [notes, setNotes] = useState(entry?.notes ?? "");

  const item = view.items.find(i => i.id === itemId) ?? null;
  const unit = item?.unit ?? view.order.unit;
  const loss = lossFor(disposition, sampleLoss);
  const room = disposition === "customer_good" ? customerRoom(view, item?.id ?? null, unit, entry) : null;
  const over = disposition === "customer_good" && exceeds(room, quantity);
  const secondaryPartial = Boolean(secondaryQuantity) !== Boolean(secondaryUnit.trim());
  const valid = QUANTITY.test(quantity) && Number(quantity) > 0 && (!multi || itemId) && loss !== null && !secondaryPartial
    && (!secondaryQuantity || (QUANTITY.test(secondaryQuantity) && Number(secondaryQuantity) > 0));

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid || busy) return;
    onSave({
      production_order_item_id: item?.id ?? null, disposition, quantity,
      secondary_quantity: secondaryQuantity || null, secondary_unit: secondaryUnit.trim() || null,
      // Only samples send the flag; the server fixes it for every other disposition.
      counts_as_loss: disposition === "sample" ? sampleLoss : null,
      reason_code: reasonCode.trim() || null, notes: notes.trim() || null,
    });
  }

  return <div className={s.overlay} onKeyDown={e => { if (e.key === "Escape" && !busy) onClose(); }}>
    <form role="dialog" aria-modal="true" aria-labelledby={`${id}-title`} className={`${s.panel} ${s.dialog}`} onSubmit={submit}>
      <h2 id={`${id}-title`}>{entry ? t("dialog.editTitle") : t("dialog.addTitle")}</h2>
      <label className={s.field}>{t("fields.disposition")}
        <select value={disposition} disabled={busy} onChange={e => { setDisposition(e.target.value as Disposition); setSampleLoss(null); }}>
          {DISPOSITIONS.map(d => <option key={d} value={d}>{t(`dispositions.${d}`)}</option>)}
        </select>
      </label>
      <p className={s.muted} style={{ margin: 0 }}>{t(`dispositionHints.${disposition}`)}</p>
      {multi && <label className={s.field}>{t("fields.item")}
        <select required value={itemId} disabled={busy} onChange={e => setItemId(e.target.value)}>
          <option value="">{t("dialog.selectItem")}</option>
          {view.items.map(i => <option key={i.id} value={i.id}>{t("dialog.itemOption", { no: String(i.line_no), spec: specSummary(i.target_spec_json) || "—", unit: i.unit })}</option>)}
        </select>
      </label>}
      <label className={s.field}>{t("fields.quantityWithUnit", { unit })}
        <input type="number" required min="0.001" step="0.001" inputMode="decimal" value={quantity} disabled={busy} onChange={e => setQuantity(e.target.value)} />
      </label>
      {disposition === "customer_good" && (room
        ? <p role="status" className={over ? s.error : s.muted} style={{ margin: 0 }}>
          {t(over ? "dialog.customerExceeded" : "dialog.customerRoom", { allocated: room.allocated, recorded: room.recorded, remaining: room.remaining, unit })}
        </p>
        : <p role="status" className={s.error} style={{ margin: 0 }}>{t("dialog.noAllocation")}</p>)}
      {disposition === "sample" && <fieldset className={s.field} style={{ border: 0, padding: 0, margin: 0 }}>
        <legend>{t("fields.sampleLoss")}</legend>
        <label><input type="radio" name={`${id}-loss`} checked={sampleLoss === true} disabled={busy} onChange={() => setSampleLoss(true)} required /> {t("dialog.sampleLossYes")}</label>
        <label><input type="radio" name={`${id}-loss`} checked={sampleLoss === false} disabled={busy} onChange={() => setSampleLoss(false)} /> {t("dialog.sampleLossNo")}</label>
      </fieldset>}
      {disposition in FIXED_LOSS && <p className={s.muted} style={{ margin: 0 }}>{FIXED_LOSS[disposition] ? t("dialog.alwaysLoss") : t("dialog.neverLoss")}</p>}
      <div className={s.grid}>
        <label className={s.field}>{t("fields.secondaryQuantity")}
          <input type="number" min="0.001" step="0.001" value={secondaryQuantity} disabled={busy} onChange={e => setSecondaryQuantity(e.target.value)} />
        </label>
        <label className={s.field}>{t("fields.secondaryUnit")}
          <input maxLength={32} value={secondaryUnit} disabled={busy} onChange={e => setSecondaryUnit(e.target.value)} />
        </label>
      </div>
      {secondaryPartial && <p className={s.muted} style={{ margin: 0 }}>{t("dialog.secondaryBoth")}</p>}
      <label className={s.field}>{t("fields.reasonCode")}<input maxLength={64} value={reasonCode} disabled={busy} onChange={e => setReasonCode(e.target.value)} /></label>
      <label className={s.field}>{t("fields.notes")}<textarea maxLength={2000} value={notes} disabled={busy} onChange={e => setNotes(e.target.value)} /></label>
      {error && <p role="alert" className={s.error}>{error}</p>}
      <div className={s.actions}>
        <button type="button" className={s.button} disabled={busy} onClick={onClose}>{t("actions.cancel")}</button>
        <button type="submit" className={`${s.button} ${s.primary}`} disabled={!valid || busy}>{t("actions.save")}</button>
      </div>
    </form>
  </div>;
}
