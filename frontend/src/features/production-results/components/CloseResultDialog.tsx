"use client";

import { useEffect, useId, useState, type FormEvent } from "react";
import { useTranslations, useLocale } from "next-intl";
import s from "@/features/production-demands/demands.module.css";
import { getOrderResult } from "../api";
import type { OrderResult } from "../types";
import { resultErrorMessage } from "./result-errors";
import { SummaryCards } from "./OrderResultSection";

import { joinList } from "@/lib/utils";
// Confirmation before closing: the final result and its variance, or an explicit zero-output close with a reason.
// The server's close guard decides; this dialog only shows what it will check.
// canReadResult=false: the user may close but not read the result; the dialog then skips the summary
// and offers zero output as a plain option (the server still rejects it when entries exist).
export function CloseResultDialog({ orderId, orderNumber, busy, error, onConfirm, onClose, canReadResult = true }: {
  orderId: string; orderNumber: string; busy: boolean; error: string; canReadResult?: boolean;
  onConfirm: (options: { reason?: string; zeroOutput: boolean }) => void; onClose: () => void;
}) {
  const t = useTranslations("production.results");
  const locale = useLocale();
  const id = useId();
  const [view, setView] = useState<OrderResult | null>(null);
  const [loadError, setLoadError] = useState("");
  const [zeroOutput, setZeroOutput] = useState(false);
  const [reason, setReason] = useState("");

  useEffect(() => {
    if (!canReadResult) return;
    let active = true;
    getOrderResult(orderId).then(v => { if (active) setView(v); }).catch(e => { if (active) setLoadError(resultErrorMessage(e, t)); });
    return () => { active = false; };
  }, [orderId, t, canReadResult]);

  const check = view?.close_check;
  const missing = view ? view.items.filter(i => check?.missing_item_ids.includes(i.id)).map(i => i.line_no) : [];
  const canZero = canReadResult ? Boolean(check && !check.has_entries) : true;
  const valid = zeroOutput ? canZero && Boolean(reason.trim()) : canReadResult ? Boolean(check?.ready) : true;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (valid && !busy) onConfirm(zeroOutput ? { reason: reason.trim(), zeroOutput: true } : { reason: reason.trim() || undefined, zeroOutput: false });
  }
  return <div className={s.overlay} onKeyDown={e => { if (e.key === "Escape" && !busy) onClose(); }}>
    <form role="dialog" aria-modal="true" aria-labelledby={`${id}-title`} className={`${s.panel} ${s.dialog}`} style={{ width: "min(760px, 100%)" }} onSubmit={submit}>
      <h2 id={`${id}-title`}>{t("close.title", { order: orderNumber })}</h2>
      <p className={s.muted}>{t("close.text")}</p>
      {loadError && <p role="alert" className={s.error}>{loadError}</p>}
      {view && !zeroOutput && view.totals.map(total => <SummaryCards key={total.unit} summary={total} unit={total.unit} showUnit={view.totals.length > 1} />)}
      {check && !check.has_entries && <p role="status" className={s.error} style={{ margin: 0 }}>{t("close.noEntries")}</p>}
      {missing.length > 0 && <p role="status" className={s.error} style={{ margin: 0 }}>{t("close.missingItems", { lines: joinList(missing, locale) })}</p>}
      {canZero && <label><input type="checkbox" checked={zeroOutput} disabled={busy} onChange={e => setZeroOutput(e.target.checked)} /> {t("close.zeroOutput")}</label>}
      {(zeroOutput || check?.ready || !canReadResult) && <label className={s.field}>{zeroOutput ? t("close.zeroReason") : t("close.reasonOptional")}
        <textarea maxLength={500} required={zeroOutput} value={reason} disabled={busy} onChange={e => setReason(e.target.value)} />
      </label>}
      {error && <p role="alert" className={s.error}>{error}</p>}
      <div className={s.actions}>
        <button type="button" className={s.button} disabled={busy} onClick={onClose}>{t("actions.cancel")}</button>
        <button type="submit" className={`${s.button} ${s.primary}`} disabled={!valid || busy}>{t("close.confirm")}</button>
      </div>
    </form>
  </div>;
}
