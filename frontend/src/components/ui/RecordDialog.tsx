"use client";
import { useState, type ReactNode } from "react";
import { useTranslations } from "next-intl";
import { Dialog } from "./Dialog";
import css from "./records.module.css";

export function RecordDialog({ title, children, onSave, onClose, error, errorAction, saveLabel, disabled = false }: {
  title: ReactNode; children: ReactNode; onSave: () => Promise<boolean | void>; onClose: () => void;
  error?: string; errorAction?: ReactNode; saveLabel?: string; disabled?: boolean;
}) {
  const t = useTranslations("directory");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  return <Dialog title={title} size="lg" busy={busy} onClose={onClose} onSubmit={async event => {
    event.preventDefault(); if (busy || disabled) return;
    setBusy(true); setFailed(false);
    try { if (await onSave() !== false) onClose(); }
    catch { setFailed(true); }
    finally { setBusy(false); }
  }} footer={<>
    <button className={css.button} type="button" disabled={busy} onClick={onClose}>{t("cancel")}</button>
    <button className={`${css.button} ${css.primary}`} type="submit" disabled={busy || disabled}>{busy ? t("saving") : saveLabel ?? t("save")}</button>
  </>}>
    {(error || failed) && <div role="alert" className={css.error}>{error || t("saveFailed")}{errorAction}</div>}
    <fieldset className={css.fields} disabled={busy}>{children}</fieldset>
  </Dialog>;
}
