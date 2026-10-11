"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { qualityErrorMessage } from "@/features/quality-checks/components/quality-errors";
import { Q } from "@/lib/quality-permissions";
import { createCertificate, getCertificateSources, getCertificates } from "../api";
import type { CertificateListItem, CertificateSources } from "../types";
import { CertificateStatusBadge } from "./CertificateStatusBadge";

// On a closed inspection: its certificates, and a draft for a customer of its lot when it is certifiable.
export function CheckCertificatesSection({ checkId }: { checkId: string }) {
  const t = useTranslations("quality.certificates");
  const errors = useTranslations("quality.errors");
  const router = useRouter();
  const canRead = usePermission(Q.COA_READ);
  const canCreate = usePermission(Q.COA_CREATE);
  const [rows, setRows] = useState<CertificateListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [sources, setSources] = useState<CertificateSources | null>(null);
  const [customer, setCustomer] = useState("");
  const [po, setPo] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    // An inspection has few certificates; the largest page is asked for, and a link opens the rest if there are more.
    if (canRead) getCertificates({ quality_check_id: checkId, page_size: 100 }).then(v => { if (active) { setRows(v.items); setTotal(v.total); } }).catch(() => undefined);
    if (canCreate) getCertificateSources(checkId).then(v => { if (active) { setSources(v); setCustomer(v.customers[0]?.id ?? ""); } }).catch(() => undefined);
    return () => { active = false; };
  }, [checkId, canRead, canCreate]);

  if (!canRead && !canCreate) return null;
  async function create() {
    setBusy(true); setError("");
    try { const draft = await createCertificate({ quality_check_id: checkId, customer_id: customer || null, customer_po: po.trim() || null }); router.push(`/quality-certificates/${draft.id}`); }
    catch (e) { setError(qualityErrorMessage(e, errors)); setBusy(false); }
  }

  return <section className={s.panel} aria-label={t("checkSection")}>
    <h2 style={{ marginTop: 0 }}>{t("checkSection")}</h2>
    {rows.length > 0 && <ul style={{ margin: "0 0 12px", paddingInlineStart: 18 }}>{rows.map(r => <li key={r.id} style={{ marginBottom: 4 }}>
      <Link href={`/quality-certificates/${r.id}`}><bdi>{r.certificate_no ?? t("draftNumber")}</bdi></Link> — {r.customer_name || "—"} <CertificateStatusBadge status={r.status} />
    </li>)}</ul>}
    {total > rows.length && <p><Link href={`/quality-certificates?quality_check_id=${checkId}`}>{t("allForCheck", { count: total })}</Link></p>}
    {canCreate && sources && (sources.certifiable ? <div className={s.toolbar} style={{ marginBottom: 0 }}>
      {sources.customers.length > 0 && <label className={s.field}>{t("fields.customer")}
        <select value={customer} disabled={busy} onChange={e => setCustomer(e.target.value)}>
          {sources.customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </label>}
      <label className={s.field}>{t("fields.customerPo")}<input dir="ltr" maxLength={80} value={po} disabled={busy} onChange={e => setPo(e.target.value)} /></label>
      <button type="button" className={`${s.button} ${s.primary}`} disabled={busy} onClick={() => void create()}>{t("actions.create")}</button>
    </div> : <p className={s.muted} style={{ marginBottom: 0 }}>{t(`blockers.${sources.blocker ?? "CHECK_NOT_CLOSED"}`)}</p>)}
    {error && <p role="alert" className={s.error}>{error}</p>}
  </section>;
}
