"use client";
import { Dialog } from "@/components/ui/Dialog";

import {useUnitLabel} from "@/components/UnitLabel";
import { useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import { fromMilli, toMilli } from "@/features/production-demands/planning-lifecycle";
import s from "@/features/production-demands/demands.module.css";
import { SIGNED_QUANTITY } from "../result-rules";
import type { ResultCorrectionInput, ResultOriginal } from "../types";

// A signed correction against an original entry of a closed order. The original stays as recorded.
export function CorrectionDialog({ entry, busy, error, onSave, onClose }: {
  entry: ResultOriginal; busy: boolean; error: string; onSave: (body: ResultCorrectionInput) => void; onClose: () => void;
}) {
  const unitText = useUnitLabel();
  const t = useTranslations("production.results");
  const [quantity, setQuantity] = useState("");
  const [secondary, setSecondary] = useState("");
  const [reason, setReason] = useState("");
  const signed = SIGNED_QUANTITY.test(quantity.trim()) && toMilli(quantity) !== BigInt(0);
  const after = signed ? toMilli(entry.effective_quantity) + toMilli(quantity) : null;
  const negative = after !== null && after < BigInt(0);
  const valid = signed && !negative && reason.trim().length > 0 && (!secondary || SIGNED_QUANTITY.test(secondary.trim()));

  function submit(event: FormEvent) {
    event.preventDefault();
    if (valid && !busy) onSave({ quantity: quantity.trim(), secondary_quantity: secondary.trim() || null, correction_reason: reason.trim() });
  }
  return <Dialog title={t("correction.title")} onClose={onClose} busy={busy} onSubmit={submit}
    footer={<><button type="button" className={s.button} disabled={busy} onClick={onClose}>{t("actions.cancel")}</button>
      <button type="submit" className={`${s.button} ${s.primary}`} disabled={!valid || busy}>{t("actions.correct")}</button></>}>
    <p className={s.muted}>{t("correction.text", { disposition: t(`dispositions.${entry.disposition}`), effective: entry.effective_quantity, unit: unitText(entry.unit) })}</p>
    <label className={s.field}>{t("correction.delta", { unit: unitText(entry.unit) })}
      <input type="number" step="0.001" required value={quantity} disabled={busy} onChange={e => setQuantity(e.target.value)} />
    </label>
    {after !== null && <p role="status" className={negative ? s.error : s.muted} style={{ margin: 0 }}>
      {t(negative ? "correction.negative" : "correction.after", { value: fromMilli(after), unit: unitText(entry.unit) })}
    </p>}
    {entry.secondary_unit && <label className={s.field}>{t("correction.secondaryDelta", { unit: entry.secondary_unit })}
      <input type="number" step="0.001" value={secondary} disabled={busy} onChange={e => setSecondary(e.target.value)} />
    </label>}
    <label className={s.field}>{t("fields.correctionReason")}
      <textarea required maxLength={500} value={reason} disabled={busy} onChange={e => setReason(e.target.value)} />
    </label>
    {error && <p role="alert" className={s.error}>{error}</p>}
  </Dialog>;
}
