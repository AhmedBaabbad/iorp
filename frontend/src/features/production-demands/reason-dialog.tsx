"use client";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import s from "./demands.module.css";

// Collects the mandatory reason for releasing allocations or cancelling an order.
export function ReasonDialog({ title, description, confirmLabel, busy, onConfirm, onClose }: {
  title: string; description?: string; confirmLabel: string; busy: boolean;
  onConfirm: (reason: string) => void; onClose: () => void;
}) {
  const t = useTranslations("production.allocation");
  const common = useTranslations("common");
  const id = useId();
  const input = useRef<HTMLTextAreaElement>(null);
  const [reason, setReason] = useState("");
  const trimmed = reason.trim();
  useEffect(() => { input.current?.focus(); }, []);
  function submit(event: FormEvent) {
    event.preventDefault();
    if (trimmed && !busy) onConfirm(trimmed);
  }
  return <div className={s.overlay} onKeyDown={e => { if (e.key === "Escape" && !busy) onClose(); }}>
    <form role="dialog" aria-modal="true" aria-labelledby={`${id}-title`} className={`${s.panel} ${s.dialog}`} onSubmit={submit}>
      <h2 id={`${id}-title`}>{title}</h2>
      {description && <p className={s.muted}>{description}</p>}
      <label className={s.field}>{t("reason")}
        <textarea ref={input} value={reason} maxLength={500} required disabled={busy} onChange={e => setReason(e.target.value)} />
      </label>
      <div className={s.actions}>
        <button type="button" className={s.button} disabled={busy} onClick={onClose}>{common("actions.close")}</button>
        <button type="submit" className={`${s.button} ${s.primary}`} disabled={busy || !trimmed}>{confirmLabel}</button>
      </div>
    </form>
  </div>;
}
