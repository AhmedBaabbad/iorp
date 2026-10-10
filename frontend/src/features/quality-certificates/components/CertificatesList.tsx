"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { qualityErrorMessage } from "@/features/quality-checks/components/quality-errors";
import { useFormatter } from "@/hooks/useFormatter";
import { Q } from "@/lib/quality-permissions";
import { getCertificates, getQualitySettings, updateQualitySettings } from "../api";
import { CERTIFICATE_STATUSES, type CertificateListItem, type CertificateStatus, type QualitySettings } from "../types";
import { CertificateStatusBadge } from "./CertificateStatusBadge";

// "شهادات التحليل": certificates issued to customers for conforming batches, and drafts awaiting approval.
export function CertificatesList() {
  const t = useTranslations("quality.certificates");
  const errors = useTranslations("quality.errors");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const [status, setStatus] = useState<CertificateStatus | "">("");
  const [search, setSearch] = useState("");
  const [rows, setRows] = useState<CertificateListItem[] | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try { setRows(await getCertificates({ status, search })); } catch (e) { setError(qualityErrorMessage(e, errors)); }
  }, [status, search, errors]);
  useEffect(() => { void load(); }, [load]);

  return <PageFrame title={t("listTitle")} subtitle={t("subtitle")}>
    <section className={s.toolbar} aria-label={t("filtersAria")}>
      <label className={s.field}>{t("search")}<input type="search" value={search} placeholder={t("searchPlaceholder")} onChange={e => setSearch(e.target.value)} /></label>
      <label className={s.field}>{t("fields.status")}
        <select value={status} onChange={e => setStatus(e.target.value as CertificateStatus | "")}>
          <option value="">{t("allStatuses")}</option>
          {CERTIFICATE_STATUSES.map(v => <option key={v} value={v}>{t(`statuses.${v}`)}</option>)}
        </select>
      </label>
    </section>
    {error && <p role="alert" className={s.error}>{error}</p>}
    {!error && rows === null && <p className={s.muted}>{messages("loading.default")}</p>}
    {!error && rows?.length === 0 && <section className={s.panel}><h2 style={{ marginTop: 0 }}>{t("empty")}</h2><p className={s.muted} style={{ margin: 0 }}>{t("emptyHint")}</p></section>}
    {!error && rows && rows.length > 0 && <section className={s.panel}>
      <div className={s.tableWrap}><table className={s.table} aria-label={t("listTitle")}>
        <thead><tr>{["number", "status", "customer", "product", "batch", "quantity", "inspection", "issuedAt"].map(c => <th key={c}>{t(`fields.${c}`)}</th>)}</tr></thead>
        <tbody>{rows.map(r => <tr key={r.id}>
          <td><Link href={`/quality-certificates/${r.id}`}><bdi>{r.certificate_no ?? t("draftNumber")}</bdi></Link>
            {r.supersedes_no && <div className={s.muted}>{t("supersedes", { number: r.supersedes_no })}</div>}</td>
          <td><CertificateStatusBadge status={r.status} /></td>
          <td>{r.customer_name || "—"}</td><td>{r.product_description}</td><td><bdi>{r.batch_no}</bdi></td>
          <td><bdi>{fmt.quantity(r.quantity, r.unit_label)}</bdi></td>
          <td><Link href={`/quality-checks/${r.quality_check_id}`}><bdi>{r.inspection_code}</bdi></Link></td>
          <td>{r.issued_at ? `${fmt.date(r.issued_at)} — ${r.issued_by_name ?? ""}` : "—"}</td>
        </tr>)}</tbody>
      </table></div>
    </section>}
    <NumberingSettings />
  </PageFrame>;
}

// Certificate numbering: the prefix and the last number used, to continue from paper certificates (never backwards).
function NumberingSettings() {
  const t = useTranslations("quality.certificates.settings");
  const errors = useTranslations("quality.errors");
  const canEdit = usePermission(Q.SETTINGS_UPDATE);
  const [settings, setSettings] = useState<QualitySettings | null>(null);
  const [draft, setDraft] = useState<QualitySettings | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    getQualitySettings().then(v => { setSettings(v); setDraft(v); }).catch(() => setSettings(null));
  }, []);
  if (!settings || !draft) return null;

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setMessage("");
    try { const saved = await updateQualitySettings(draft!); setSettings(saved); setDraft(saved); setMessage(t("saved")); }
    catch (e) { setMessage(qualityErrorMessage(e, errors)); } finally { setBusy(false); }
  }
  const next = `${settings.coa_prefix}${String(settings.coa_last_number + 1).padStart(4, "0")}`;
  return <form className={s.panel} onSubmit={save} aria-label={t("title")}>
    <h2 style={{ marginTop: 0 }}>{t("title")}</h2>
    <p className={s.muted}>{t("next", { number: next })}</p>
    {canEdit && <>
      <div className={s.grid}>
        <label className={s.field}>{t("prefix")}<input dir="ltr" required maxLength={20} pattern="[A-Za-z0-9_\-/]+" value={draft.coa_prefix}
          onChange={e => setDraft({ ...draft, coa_prefix: e.target.value })} /></label>
        <label className={s.field}>{t("lastNumber")}<input type="number" min={settings.coa_last_number} value={draft.coa_last_number}
          onChange={e => setDraft({ ...draft, coa_last_number: Number(e.target.value) })} /></label>
      </div>
      <p className={s.muted}>{t("hint")}</p>
      <button type="submit" className={s.button} disabled={busy}>{t("save")}</button>
      {message && <span role="status" className={s.muted} style={{ marginInlineStart: 10 }}>{message}</span>}
    </>}
  </form>;
}
