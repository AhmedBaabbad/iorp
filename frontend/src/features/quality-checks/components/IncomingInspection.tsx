"use client";
import { Dialog } from "@/components/ui/Dialog";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { useFormatter } from "@/hooks/useFormatter";
import { Q } from "@/lib/quality-permissions";
import { getAwaitingLots, openIncomingInspection } from "../api/quality-checks-api";
import { LOT_PARTS, type AwaitingReceipt, type LotDecisionRequest, type LotPart, type QualityCheckData } from "../types";
import { QualityCheckStatusBadge } from "./QualityCheckStatusBadge";
import { QUANTITY, qualityErrorMessage } from "./quality-errors";

const thousandths = (value: string) => Math.round(Number(value || 0) * 1000);

// "فحص المواد الواردة": received lots of materials inspected on arrival; one inspection per lot, then its decision.
export function QualityIncomingList() {
  const t = useTranslations("quality.incoming");
  const errors = useTranslations("quality.errors");
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const fmt = useFormatter();
  const units = useTranslations("common.units.units");
  const unit = (code: string) => (units.has(code) ? units(code) : code);
  const router = useRouter();
  const canOpen = usePermission(Q.CHECKS_CREATE);
  const [search, setSearch] = useState("");
  const [rows, setRows] = useState<AwaitingReceipt[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setError("");
    try { setRows(await getAwaitingLots(search)); } catch (e) { setError(qualityErrorMessage(e, errors)); }
  }, [search, errors]);
  useEffect(() => { const timer = setTimeout(() => void load(), 200); return () => clearTimeout(timer); }, [load]);
  async function open(lineId: string) {
    setBusy(lineId); setError("");
    try { router.push(`/quality-checks/${(await openIncomingInspection(lineId)).id}`); }
    catch (e) { setError(qualityErrorMessage(e, errors)); setBusy(null); }
  }

  return <PageFrame title={t("title")} subtitle={t("subtitle")}>
    <section className={s.toolbar} aria-label={t("title")}>
      <label className={s.field}>{t("search")}<input type="search" value={search} placeholder={t("searchPlaceholder")} onChange={e => setSearch(e.target.value)} /></label>
    </section>
    {error && <div className={s.actions}><p role="alert" className={s.error}>{error}</p>
      <button type="button" className={s.button} onClick={() => void load()}>{common("actions.retry")}</button></div>}
    {rows === null && !error && <p className={s.muted}>{messages("loading.default")}</p>}
    {rows?.length === 0 && <section className={s.panel}><h2 style={{ marginTop: 0 }}>{t("empty")}</h2><p className={s.muted} style={{ margin: 0 }}>{t("emptyHint")}</p></section>}
    {rows?.map(r => <section key={r.receipt_id} className={s.panel} aria-label={r.receipt_no}>
      <div className={s.actions} style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}><Link href={`/goods-receipts/${r.receipt_id}`}><bdi>{r.receipt_no}</bdi></Link></h2>
        <span className={s.muted}>{r.received_at ? fmt.dateTime(r.received_at) : fmt.date(r.receipt_date)}</span>
      </div>
      <p style={{ margin: "8px 0" }}><Link href={`/suppliers/${r.supplier_id}`}>{r.supplier_name}</Link>
        {r.supplier_delivery_no && <span className={s.muted}> · <bdi dir="ltr">{r.supplier_delivery_no}</bdi></span>}</p>
      <div className={s.tableWrap}><table className={s.table}>
        <thead><tr><th>#</th><th>{t("material")}</th><th>{t("lot")}</th><th>{t("quantity")}</th><th>{t("specification")}</th><th>{t("inspection")}</th></tr></thead>
        <tbody>{r.lines.map(l => <tr key={l.line_id}>
          <td>{l.line_no}</td>
          <td>{l.description}{l.material_code && <div className={s.muted}><bdi dir="ltr">{l.material_code}</bdi></div>}</td>
          <td><bdi dir="ltr">{l.supplier_lot ?? "—"}</bdi></td>
          <td><bdi>{fmt.quantity(l.quantity, unit(l.unit))}</bdi></td>
          <td><bdi dir="ltr">{l.spec_product_type ?? "—"}</bdi></td>
          <td>{l.inspection_id ? <span className={s.actions}><Link href={`/quality-checks/${l.inspection_id}`}><bdi>{l.inspection_code}</bdi></Link>
            {l.inspection_status && <QualityCheckStatusBadge status={l.inspection_status} />}</span>
            : canOpen ? <button type="button" className={`${s.button} ${s.primary}`} disabled={busy !== null} onClick={() => void open(l.line_id)}>
              {busy === l.line_id ? t("opening") : t("open")}</button> : <span className={s.muted}>{t("notOpened")}</span>}</td>
        </tr>)}</tbody>
      </table></div>
    </section>)}
  </PageFrame>;
}

// The received lot an incoming inspection is about.
export function IncomingSourceSection({ check }: { check: QualityCheckData }) {
  const t = useTranslations("quality.incoming");
  const fmt = useFormatter();
  const source = check.incoming_source!;
  return <section className={s.panel} aria-label={t("sourceTitle")}>
    <h2 style={{ marginTop: 0 }}>{t("sourceTitle")}</h2>
    <dl className={s.grid} style={{ margin: 0 }}>
      <div><dt className={s.muted}>{t("receipt")}</dt><dd style={{ margin: "4px 0 0" }}><Link href={`/goods-receipts/${source.receipt_id}`}><bdi>{source.receipt_no}</bdi></Link>
        <div className={s.muted}>{fmt.date(source.receipt_date)}</div></dd></div>
      <div><dt className={s.muted}>{t("supplier")}</dt><dd style={{ margin: "4px 0 0" }}><Link href={`/suppliers/${source.supplier_id}`}>{source.supplier_name}</Link></dd></div>
      <div><dt className={s.muted}>{t("material")}</dt><dd style={{ margin: "4px 0 0" }}>{source.line_no}. {source.description}
        {source.material_code && <div className={s.muted}><bdi dir="ltr">{source.material_code}</bdi></div>}</dd></div>
      <div><dt className={s.muted}>{t("lot")}</dt><dd style={{ margin: "4px 0 0" }}><bdi dir="ltr">{source.supplier_lot ?? "—"}</bdi></dd></div>
      <div><dt className={s.muted}>{t("specification")}</dt><dd style={{ margin: "4px 0 0" }}><bdi dir="ltr">{source.spec_product_type ?? "—"}</bdi></dd></div>
    </dl>
  </section>;
}

// Closes an incoming inspection: what is released, and where the rest goes (it opens an NCR about the supplier).
export function LotDecisionDialog({ check, busy, onClose, onConfirm }: { check: QualityCheckData; busy: boolean; onClose: () => void;
  onConfirm: (body: LotDecisionRequest) => void }) {
  const t = useTranslations("quality.incoming");
  const common = useTranslations("common");
  const fmt = useFormatter();
  const units = useTranslations("common.units.units");
  const unit = (code: string | null) => (code && units.has(code) ? units(code) : code ?? "");
  const [parts, setParts] = useState<Record<LotPart, string>>({ released: "", use_as_is: "", sort: "", return_to_supplier: "", scrap: "", hold: "" });
  const [notes, setNotes] = useState("");
  const [approver, setApprover] = useState("");
  const valid = LOT_PARTS.every(p => !parts[p].trim() || QUANTITY.test(parts[p].trim()));
  const total = LOT_PARTS.reduce((sum, p) => sum + (valid ? thousandths(parts[p]) : 0), 0);
  const balanced = valid && total === thousandths(check.qty_inspected);
  const rejected = total - thousandths(parts.released);
  const concession = thousandths(parts.use_as_is) > 0;
  const ok = balanced && (!concession || Boolean(approver.trim() && notes.trim()));
  function submit(event: FormEvent) {
    event.preventDefault();
    if (!ok || busy) return;
    onConfirm({ ...Object.fromEntries(LOT_PARTS.map(p => [p, parts[p].trim() || "0"])) as Record<LotPart, string>,
      notes: notes.trim() || null, concession_approved_by: concession ? approver.trim() : null });
  }
  return <Dialog title={t("decisionTitle")} onClose={onClose} busy={busy} onSubmit={submit}
    footer={<><button type="button" className={s.button} disabled={busy} onClick={onClose}>{common("actions.close")}</button>
      <button type="submit" className={`${s.button} ${s.primary}`} disabled={busy || !ok}>{t("decide")}</button></>}>
    <p className={s.muted} style={{ margin: 0 }}>{t("decisionText", { quantity: fmt.quantity(check.qty_inspected, unit(check.unit)) })}</p>
    <div className={s.grid}>{LOT_PARTS.map(p => <label key={p} className={s.field}>{t(`parts.${p}`)}
      <input inputMode="decimal" dir="ltr" value={parts[p]} disabled={busy} onChange={e => setParts(old => ({ ...old, [p]: e.target.value }))} />
      <span className={s.muted}>{t(`partHints.${p}`)}</span></label>)}</div>
    <p role="status" className={balanced ? s.muted : s.error} style={{ margin: 0 }}>
      {t("decisionTotal", { total: String(total / 1000), quantity: String(thousandths(check.qty_inspected) / 1000) })}</p>
    {rejected > 0 && balanced && <p className={s.error} style={{ margin: 0 }}>{t("ncrNotice")}</p>}
    {concession && <label className={s.field}>{t("concessionBy")}<input required maxLength={255} value={approver} disabled={busy} onChange={e => setApprover(e.target.value)} /></label>}
    <label className={s.field}>{concession ? t("notesRequired") : t("notes")}<textarea maxLength={2000} required={concession} value={notes} disabled={busy} onChange={e => setNotes(e.target.value)} /></label>
  </Dialog>;
}
