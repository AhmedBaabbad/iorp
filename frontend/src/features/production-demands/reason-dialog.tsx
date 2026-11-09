"use client";
import { Dialog } from "@/components/ui/Dialog";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import s from "./demands.module.css";

// Collects the mandatory reason for releasing allocations or cancelling an order.
export function ReasonDialog({ title, description, confirmLabel, busy, onConfirm, onClose, reasonRequired = true, danger = false }: {
  title: string; description?: string; confirmLabel: string; busy: boolean;
  onConfirm: (reason: string) => void; onClose: () => void;
  /** false: a confirmation where the reason is optional. */
  reasonRequired?: boolean; danger?: boolean;
}) {
  const t = useTranslations("production.allocation");
  const common = useTranslations("common");
  const input = useRef<HTMLTextAreaElement>(null);
  const [reason, setReason] = useState("");
  const trimmed = reason.trim();
  useEffect(() => { input.current?.focus(); }, []);
  function submit(event: FormEvent) {
    event.preventDefault();
    if ((trimmed || !reasonRequired) && !busy) onConfirm(trimmed);
  }
  return <Dialog title={title} onClose={onClose} busy={busy} onSubmit={submit}
    footer={<><button type="button" className={s.button} disabled={busy} onClick={onClose}>{common("actions.close")}</button>
      <button type="submit" className={`${s.button} ${danger ? s.danger : s.primary}`} disabled={busy || (reasonRequired && !trimmed)}>{confirmLabel}</button></>}>
    {description && <p className={s.muted}>{description}</p>}
    <label className={s.field}>{reasonRequired ? t("reason") : t("reasonOptional")}
      <textarea ref={input} value={reason} maxLength={500} required={reasonRequired} disabled={busy} onChange={e => setReason(e.target.value)} />
    </label>
  </Dialog>;
}
