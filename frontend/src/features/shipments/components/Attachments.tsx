"use client";

import { useTranslations } from "next-intl";
import { useRef, useState } from "react";

import s from "@/features/production-demands/demands.module.css";
import { useFormatter } from "@/hooks/useFormatter";
import { openAttachment, removeAttachment, uploadAttachment, type AttachmentOwner } from "../api";
import { shippingErrorMessage } from "../shipping-errors";
import type { Attachment } from "../types";

// Files kept with a shipment (the signed note as proof of delivery) or a return (photos): list, open, upload, remove.
export function Attachments({ owner, files, kinds, canChange, onChange }: {
  owner: AttachmentOwner; files: Attachment[]; kinds: string[]; canChange: boolean; onChange: (files: Attachment[]) => void;
}) {
  const t = useTranslations("shipping.attachments");
  const errors = useTranslations("shipping.errors");
  const fmt = useFormatter();
  const picker = useRef<HTMLInputElement>(null);
  const [kind, setKind] = useState(kinds[0]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run(action: () => Promise<Attachment[] | void>) {
    setBusy(true); setError("");
    try { const result = await action(); if (result) onChange(result); }
    catch (e) { setError(shippingErrorMessage(e, errors)); } finally { setBusy(false); }
  }
  async function upload(file: File | undefined) {
    if (picker.current) picker.current.value = "";
    if (file) await run(() => uploadAttachment(owner, file, kind));
  }

  return <div>
    {files.length === 0 ? <p className={s.muted}>{t("empty")}</p> : <ul style={{ listStyle: "none", padding: 0, margin: "0 0 12px", display: "grid", gap: 8 }}>
      {files.map(f => <li key={f.id} className={s.actions} style={{ justifyContent: "space-between" }}>
        <span><strong>{t.has(`kinds.${f.kind}`) ? t(`kinds.${f.kind}`) : f.kind}</strong> — <bdi>{f.file_name}</bdi>
          <span className={s.muted}> · {f.uploaded_by_name ?? "—"} · {fmt.dateTime(f.uploaded_at)}</span></span>
        <span className={s.actions}>
          <button type="button" className={s.button} disabled={busy} onClick={() => void run(() => openAttachment(owner, f))}>{t("open")}</button>
          {canChange && <button type="button" className={`${s.button} ${s.danger}`} disabled={busy}
            onClick={() => { if (window.confirm(t("removeConfirm", { name: f.file_name }))) void run(() => removeAttachment(owner, f.id)); }}>{t("remove")}</button>}
        </span>
      </li>)}
    </ul>}
    {canChange && <div className={s.toolbar} style={{ marginBottom: 0 }}>
      {kinds.length > 1 && <label className={s.field}>{t("kind")}
        <select value={kind} disabled={busy} onChange={e => setKind(e.target.value)}>{kinds.map(k => <option key={k} value={k}>{t(`kinds.${k}`)}</option>)}</select>
      </label>}
      <input ref={picker} type="file" accept="image/png,image/jpeg,image/webp,application/pdf" hidden aria-label={t("upload")}
        onChange={e => void upload(e.target.files?.[0])} />
      <button type="button" className={s.button} disabled={busy} onClick={() => picker.current?.click()}>{busy ? t("uploading") : t("upload")}</button>
      <span className={s.muted}>{t("hint")}</span>
    </div>}
    {error && <p role="alert" className={s.error}>{error}</p>}
  </div>;
}
