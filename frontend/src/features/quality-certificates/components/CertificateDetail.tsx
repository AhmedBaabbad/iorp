"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { ReasonDialog } from "@/features/production-demands/reason-dialog";
import s from "@/features/production-demands/demands.module.css";
import { QualityHistory } from "@/features/quality-checks/components/QualityHistory";
import { qualityErrorMessage } from "@/features/quality-checks/components/quality-errors";
import { useFormatter } from "@/hooks/useFormatter";
import { downloadCertificate, getCertificate, issueCertificate, replaceCertificate, revokeCertificate, updateCertificate } from "../api";
import type { Certificate, CertificateUpdate, FrozenMeasurement } from "../types";
import { CertificateStatusBadge } from "./CertificateStatusBadge";

function Item({ label, children }: { label: string; children: ReactNode }) {
  return <div><dt className={s.muted}>{label}</dt><dd style={{ margin: "4px 0 0", overflowWrap: "anywhere" }}>{children}</dd></div>;
}

const plain = (v: string | null) => (v === null ? null : String(Number(v)));
function limits(m: FrozenMeasurement) {
  if (m.kind === "attribute") return m.acceptance ?? "—";
  if (m.lower !== null && m.upper !== null) return `${plain(m.lower)} – ${plain(m.upper)}`;
  if (m.lower !== null) return `≥ ${plain(m.lower)}`;
  if (m.upper !== null) return `≤ ${plain(m.upper)}`;
  return "—";
}

// One certificate: its frozen results, the fields completed before issue, approval, revocation and replacement, and the PDF.
export function CertificateDetail({ certificateId }: { certificateId: string }) {
  const t = useTranslations("quality.certificates");
  const errors = useTranslations("quality.errors");
  const measurements = useTranslations("quality.measurements");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const ar = useLocale() === "ar";
  const router = useRouter();
  const [c, setC] = useState<Certificate | null>(null);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState<"issue" | "revoke" | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try { setC(await getCertificate(certificateId)); } catch (e) { setError(qualityErrorMessage(e, errors)); } finally { setLoading(false); }
  }, [certificateId, errors]);
  useEffect(() => { void load(); }, [load]);

  async function run(key: string, action: () => Promise<Certificate | void>, after?: (c: Certificate) => void) {
    setBusy(key); setError("");
    try { const result = await action(); if (result) { setC(result); after?.(result); } setDialog(null); }
    catch (e) { setError(qualityErrorMessage(e, errors)); } finally { setBusy(null); }
  }

  const back = <Link href="/quality-certificates" className={s.button}>{t("backToList")}</Link>;
  if (loading) return <PageFrame title={t("detailTitle")} action={back}><p className={s.muted}>{messages("loading.default")}</p></PageFrame>;
  if (!c) return <PageFrame title={t("detailTitle")} action={back}><p role="alert" className={s.error}>{error || t("notFound")}</p></PageFrame>;
  const editable = c.actions.includes("edit");

  return <PageFrame title={c.certificate_no ?? t("draftTitle")} subtitle={`${c.product_description} — ${c.batch_no}`} action={back}>
    {c.status === "draft" && <p role="status" className={s.muted}>{t("draftHint")}</p>}
    {c.status === "revoked" && <p role="status" className={s.error}>{t("revokedHint", { reason: c.revoke_reason ?? "" })}</p>}
    {error && <p role="alert" className={s.error}>{error}</p>}
    <section className={s.panel}>
      <div className={s.actions} style={{ justifyContent: "space-between", marginBottom: 16 }}>
        <span className={s.actions}><CertificateStatusBadge status={c.status} />
          {c.supersedes_no && <span className={s.muted}>{t("supersedes", { number: c.supersedes_no })}</span>}
          {c.superseded_by_no && <span className={s.muted}>{t("supersededBy", { number: c.superseded_by_no })}</span>}</span>
        <span className={s.actions}>
          {(["en", "ar"] as const).map(lang => <button key={lang} type="button" className={s.button} disabled={busy !== null}
            onClick={() => void run(`pdf-${lang}`, () => downloadCertificate(c.id, lang))}>{busy === `pdf-${lang}` ? t("preparing") : t(`download.${lang}`)}</button>)}
          {c.actions.includes("issue") && <button type="button" className={`${s.button} ${s.primary}`} disabled={busy !== null} onClick={() => setDialog("issue")}>{t("actions.issue")}</button>}
          {c.actions.includes("replace") && <button type="button" className={s.button} disabled={busy !== null}
            onClick={() => void run("replace", () => replaceCertificate(c.id), next => router.push(`/quality-certificates/${next.id}`))}>{t("actions.replace")}</button>}
          {c.actions.includes("revoke") && <button type="button" className={`${s.button} ${s.danger}`} disabled={busy !== null} onClick={() => setDialog("revoke")}>{t("actions.revoke")}</button>}
        </span>
      </div>
      {editable ? <CertificateFields c={c} busy={busy !== null} onSave={body => void run("save", () => updateCertificate(c.id, body))} />
        : <dl className={s.grid} style={{ margin: 0 }}>
          <Item label={t("fields.customer")}>{c.customer_name || "—"}</Item>
          <Item label={t("fields.customerPo")}><bdi>{c.customer_po ?? "—"}</bdi></Item>
          <Item label={t("fields.product")}>{c.product_description}</Item>
          <Item label={t("fields.grade")}>{c.grade ?? "—"}</Item>
          <Item label={t("fields.batch")}><bdi>{c.batch_no}</bdi></Item>
          <Item label={t("fields.quantity")}><bdi>{fmt.quantity(c.quantity, c.unit_label)}{c.package_count ? ` — ${c.package_count}` : ""}</bdi></Item>
          <Item label={t("fields.productionDate")}>{c.production_date ? fmt.date(c.production_date) : "—"}</Item>
          <Item label={t("fields.inspectionDate")}>{c.inspection_date ? fmt.date(c.inspection_date) : "—"}</Item>
          <Item label={t("fields.deliveryRef")}><bdi>{c.delivery_ref ?? "—"}</bdi></Item>
          <Item label={t("fields.sampleSize")}>{c.sample_size ?? "—"}</Item>
          <Item label={t("fields.samplingReference")}><bdi>{c.sampling_reference ?? "—"}</bdi></Item>
          <Item label={t("fields.retainedSample")}>{c.retained_sample ? `${t("yes")}${c.retention_ref ? ` — ${c.retention_ref}` : ""}` : t("no")}</Item>
          <Item label={t("fields.issuedBy")}>{c.issued_at ? `${c.issued_by_name ?? ""} — ${fmt.dateTime(c.issued_at)}` : "—"}</Item>
        </dl>}
      {!editable && c.deviation_note && <p style={{ whiteSpace: "pre-wrap" }}><span className={s.muted}>{t("fields.deviationNote")}: </span>{c.deviation_note}</p>}
      {!editable && c.remarks && <p style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}><span className={s.muted}>{t("fields.remarks")}: </span>{c.remarks}</p>}
    </section>
    <section className={s.panel} aria-label={t("resultsTitle")}>
      <div className={s.actions} style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>{t("resultsTitle")}</h2>
        <span className={s.muted}>{t("source", { inspection: c.inspection_code, specification: c.specification_code ? `${c.specification_code} — rev ${c.specification_revision}` : "—" })}</span>
      </div>
      <p className={s.muted}>{t("frozenHint")}</p>
      <div className={s.tableWrap}><table className={s.table}>
        <thead><tr>{["parameter", "unit", "target", "acceptance", "result", "verdict"].map(k => <th key={k}>{t(`columns.${k}`)}</th>)}</tr></thead>
        <tbody>{c.measurements.map(m => <tr key={m.code}>
          <td><strong>{ar ? m.name_ar : m.name_en}</strong>{m.method && <div className={s.muted}>{m.method}</div>}</td>
          <td>{m.unit ?? "—"}</td>
          <td><bdi>{m.kind === "numeric" ? (plain(m.target) ?? "—") : (m.requirement ?? "—")}</bdi></td>
          <td><bdi>{limits(m)}</bdi></td>
          <td><bdi>{m.kind === "numeric"
            ? (m.count > 1 ? `${plain(m.mean)} (${plain(m.minimum)} – ${plain(m.maximum)}, n=${m.count})` : (plain(m.mean) ?? "—"))
            : `${m.attribute_result ? measurements(m.attribute_result) : "—"}${m.observation ? ` — ${m.observation}` : ""}`}</bdi></td>
          <td><span className={`${s.badge} ${m.status === "fail" ? s.urgent : s.green}`}>{measurements(`verdict.${m.status}`)}</span></td>
        </tr>)}</tbody>
      </table></div>
    </section>
    <QualityHistory entries={c.history} statusLabel={v => (t.has(`statuses.${v}`) ? t(`statuses.${v}`) : v)} />
    {dialog === "issue" && <div className={s.overlay} onKeyDown={e => { if (e.key === "Escape" && !busy) setDialog(null); }}>
      <div role="dialog" aria-modal="true" aria-label={t("issueDialog.title")} className={`${s.panel} ${s.dialog}`}>
        <h2 style={{ margin: 0 }}>{t("issueDialog.title")}</h2>
        <p className={s.muted}>{t("issueDialog.text")}</p>
        <div className={s.actions}>
          <button type="button" className={s.button} disabled={busy !== null} onClick={() => setDialog(null)} autoFocus>{t("cancel")}</button>
          <button type="button" className={`${s.button} ${s.primary}`} disabled={busy !== null} onClick={() => void run("issue", () => issueCertificate(c.id))}>{t("actions.issue")}</button>
        </div>
      </div>
    </div>}
    {dialog === "revoke" && <ReasonDialog title={t("revokeDialog.title")} description={t("revokeDialog.text")} confirmLabel={t("actions.revoke")}
      busy={busy !== null} danger onClose={() => setDialog(null)} onConfirm={reason => void run("revoke", () => revokeCertificate(c.id, reason))} />}
  </PageFrame>;
}

// The fields completed before issue; the results themselves are frozen.
function CertificateFields({ c, busy, onSave }: { c: Certificate; busy: boolean; onSave: (body: CertificateUpdate) => void }) {
  const t = useTranslations("quality.certificates");
  const [v, setV] = useState({
    customer_name: c.customer_name, customer_po: c.customer_po ?? "", delivery_ref: c.delivery_ref ?? "", batch_no: c.batch_no,
    product_description: c.product_description, grade: c.grade ?? "", production_date: c.production_date ?? "", inspection_date: c.inspection_date ?? "",
    quantity: c.quantity, unit_label: c.unit_label, package_count: c.package_count === null ? "" : String(c.package_count), sample_size: c.sample_size ?? "",
    sampling_reference: c.sampling_reference ?? "", retained_sample: c.retained_sample, retention_ref: c.retention_ref ?? "",
    deviation_note: c.deviation_note ?? "", remarks: c.remarks ?? "" });
  const set = (field: keyof typeof v, value: string | boolean) => setV(old => ({ ...old, [field]: value }));
  const text = (field: keyof typeof v, extra: Record<string, unknown> = {}) =>
    <label className={s.field}>{t(`fields.${fieldLabel[field]}`)}<input value={String(v[field])} disabled={busy} onChange={e => set(field, e.target.value)} {...extra} /></label>;

  function submit(event: FormEvent) {
    event.preventDefault();
    const blank = (value: string) => value.trim() || null;
    onSave({ customer_name: v.customer_name.trim(), customer_po: blank(v.customer_po), delivery_ref: blank(v.delivery_ref), batch_no: v.batch_no.trim(),
      product_description: v.product_description.trim(), grade: blank(v.grade), production_date: v.production_date || null, inspection_date: v.inspection_date || null,
      quantity: v.quantity, unit_label: v.unit_label.trim(), package_count: v.package_count === "" ? null : Number(v.package_count), sample_size: blank(v.sample_size),
      sampling_reference: blank(v.sampling_reference), retained_sample: v.retained_sample, retention_ref: blank(v.retention_ref),
      deviation_note: blank(v.deviation_note), remarks: blank(v.remarks) });
  }
  return <form onSubmit={submit} aria-label={t("fieldsTitle")}>
    <div className={s.grid}>
      {text("customer_name", { required: true, maxLength: 255 })}
      {text("customer_po", { maxLength: 80, dir: "ltr" })}
      {text("product_description", { required: true, maxLength: 255 })}
      {text("grade", { maxLength: 80 })}
      {text("batch_no", { required: true, maxLength: 80, dir: "ltr" })}
      {text("quantity", { required: true, type: "number", min: "0.001", step: "0.001" })}
      {text("unit_label", { maxLength: 32 })}
      {text("package_count", { type: "number", min: 0 })}
      {text("production_date", { type: "date" })}
      {text("inspection_date", { type: "date" })}
      {text("delivery_ref", { maxLength: 80, dir: "ltr" })}
      {text("sample_size", { maxLength: 120 })}
      {text("sampling_reference", { maxLength: 120, dir: "ltr" })}
      <label className={s.field}>{t("fields.retainedSample")}
        <select value={v.retained_sample ? "yes" : "no"} disabled={busy} onChange={e => set("retained_sample", e.target.value === "yes")}>
          <option value="no">{t("no")}</option><option value="yes">{t("yes")}</option>
        </select>
      </label>
      {v.retained_sample && text("retention_ref", { maxLength: 80, dir: "ltr" })}
    </div>
    {c.inspection_result === "conditional_accept" && <>
      <label className={s.field}>{t("fields.deviationNote")}
        <textarea required maxLength={2000} value={v.deviation_note} disabled={busy} onChange={e => set("deviation_note", e.target.value)} />
      </label>
      <p className={s.muted} style={{ marginTop: 4 }}>{t("deviationHint")}</p>
    </>}
    <label className={s.field}>{t("fields.remarks")}<textarea maxLength={2000} value={v.remarks} disabled={busy} onChange={e => set("remarks", e.target.value)} /></label>
    <div className={s.actions} style={{ marginTop: 12 }}><button type="submit" className={s.button} disabled={busy}>{t("save")}</button></div>
  </form>;
}

const fieldLabel: Record<string, string> = {
  customer_name: "customer", customer_po: "customerPo", product_description: "product", grade: "grade", batch_no: "batch", quantity: "quantity",
  unit_label: "unitLabel", package_count: "packageCount", production_date: "productionDate", inspection_date: "inspectionDate",
  delivery_ref: "deliveryRef", sample_size: "sampleSize", sampling_reference: "samplingReference", retention_ref: "retentionRef",
};
