"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import { ReasonDialog } from "@/features/production-demands/reason-dialog";
import s from "@/features/production-demands/demands.module.css";
import { QualityDefectsList } from "@/features/quality-defects";
import { RecordReportButton } from "@/features/reports/RecordReportButton";
import { useFormatter } from "@/hooks/useFormatter";
import { Q, QUALITY_REPORT } from "@/lib/quality-permissions";
import { cancelQualityCheck, closeQualityCheck, getQualityCheckById, startQualityCheck } from "../api/quality-checks-api";
import { CHECK_RESULTS, type CloseQualityCheckRequest, type QualityCheckData, type QualityCheckResult } from "../types";
import { QualityCheckResultBadge } from "./QualityCheckResultBadge";
import { QualityCheckStatusBadge } from "./QualityCheckStatusBadge";
import { MeasurementsSection } from "./MeasurementsSection";
import { QualityHistory } from "./QualityHistory";
import { QUANTITY, qualityErrorMessage } from "./quality-errors";

// The rejection reasons a closing check may give; kept here so the check feature does not import the rejection feature.
const REASONS = ["failed_quality_check", "critical_defect", "out_of_spec", "dimension_failure", "surface_failure", "packaging_failure", "labeling_issue", "other"];
const thousandths = (value: string) => Math.round(Number(value || 0) * 1000);

function Item({ label, children }: { label: string; children: ReactNode }) {
  return <div><dt className={s.muted}>{label}</dt><dd style={{ margin: "4px 0 0", overflowWrap: "anywhere" }}>{children}</dd></div>;
}

export function QualityCheckDetail({ qualityCheckId }: { qualityCheckId: string }) {
  const t = useTranslations("quality.qualityChecks");
  const errors = useTranslations("quality.errors");
  const enums = useTranslations("enums.qualityCheck");
  const rejectionEnums = useTranslations("enums.qualityRejection");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const canReadRejections = usePermission(Q.REJECTIONS_READ);
  const canReadDefects = usePermission(Q.DEFECTS_READ);
  const canCreateRejection = usePermission(Q.REJECTIONS_CREATE);
  const [check, setCheck] = useState<QualityCheckData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dialog, setDialog] = useState<"close" | "cancel" | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { setCheck(await getQualityCheckById(qualityCheckId)); }
    catch (e) { setError(qualityErrorMessage(e, errors)); }
    finally { setLoading(false); }
  }, [qualityCheckId, errors]);
  useEffect(() => { void load(); }, [load]);

  async function act(run: () => Promise<QualityCheckData>) {
    setBusy(true); setError("");
    try { setCheck(await run()); setDialog(null); }
    catch (e) { setError(qualityErrorMessage(e, errors)); }
    finally { setBusy(false); }
  }

  const back = <Link href={check?.production_order_id ? `/quality-checks?order=${check.production_order_id}` : "/quality-checks"} className={s.button}>{t("backToList")}</Link>;
  if (loading) return <PageFrame title={t("detailTitle")} action={back}><p className={s.muted}>{messages("loading.default")}</p></PageFrame>;
  if (!check) return <PageFrame title={t("detailTitle")} action={back}><p role="alert" className={s.error}>{error || t("notFound")}</p></PageFrame>;
  const unit = check.unit ?? "";
  const closed = check.status === "closed";

  return <PageFrame title={check.inspection_code} subtitle={enums(`checkType.${check.check_type}`)} action={back}>
    {(closed || check.status === "cancelled") && <p role="status" className={s.muted}>{t("closedMessage")}</p>}
    {error && <p role="alert" className={s.error}>{error}</p>}
    <section className={s.panel}>
      <div className={s.actions} style={{ justifyContent: "space-between", marginBottom: 16 }}>
        <span className={s.actions}><QualityCheckStatusBadge status={check.status} />{closed && <QualityCheckResultBadge result={check.result} />}</span>
        <span className={s.actions}>
          <RecordReportButton module="quality" reportKey="quality.check_full" field="check_id" id={check.id} permission={QUALITY_REPORT.CHECK_FULL} label={t("actions.report")} />
          {check.actions.includes("edit") && <Link href={`/quality-checks/${check.id}/edit`} className={s.button}>{t("actions.edit")}</Link>}
          {check.actions.includes("start") && <button type="button" className={`${s.button} ${s.primary}`} disabled={busy}
            onClick={() => void act(() => startQualityCheck(check.id))}>{t("actions.startInspection")}</button>}
          {check.actions.includes("close") && <button type="button" className={`${s.button} ${s.primary}`} disabled={busy} onClick={() => setDialog("close")}>{t("actions.closeInspection")}</button>}
          {check.actions.includes("cancel") && <button type="button" className={`${s.button} ${s.danger}`} disabled={busy} onClick={() => setDialog("cancel")}>{t("actions.cancelInspection")}</button>}
        </span>
      </div>
      <dl className={s.grid} style={{ margin: 0 }}>
        <Item label={t("fields.checkDate")}>{fmt.dateTime(check.check_datetime)}</Item>
        {check.sample_id ? <Item label={t("fields.sample")}><bdi>{check.sample_code ?? "—"}</bdi></Item> : <>
          <Item label={t("fields.productionOrder")}>{check.production_order_id ? <Link href={`/production-orders/${check.production_order_id}`}><bdi>{check.order_number ?? "—"}</bdi></Link> : "—"}</Item>
          <Item label={t("fields.line")}>{check.item_line_no ?? (check.production_order_id ? t("placeholders.wholeOrder") : "—")}</Item>
        </>}
        <Item label={t("fields.inspector")}>{check.checked_by_name ?? "—"}</Item>
        <Item label={t("fields.startedAt")}>{check.started_at ? fmt.dateTime(check.started_at) : "—"}</Item>
        <Item label={t("fields.closedAt")}>{check.closed_at ? `${fmt.dateTime(check.closed_at)} — ${check.closed_by_name ?? ""}` : "—"}</Item>
      </dl>
      {check.cancel_reason && <p style={{ whiteSpace: "pre-wrap" }}><span className={s.muted}>{t("fields.cancelReason")}: </span>{check.cancel_reason}</p>}
      {check.notes && <p style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}><span className={s.muted}>{t("fields.notes")}: </span>{check.notes}</p>}
    </section>
    <section className={s.panel} aria-label={t("quantitySection")}>
      <h2 style={{ marginTop: 0 }}>{t("quantitySection")}</h2>
      <dl className={s.grid} style={{ margin: 0 }}>
        <Item label={t("fields.qtyInspected")}><bdi>{fmt.quantity(check.qty_inspected, unit)}</bdi></Item>
        <Item label={t("fields.qtyAccepted")}><bdi>{closed ? fmt.quantity(check.qty_accepted, unit) : "—"}</bdi></Item>
        <Item label={t("fields.qtyRejected")}><bdi>{closed ? fmt.quantity(check.qty_rejected, unit) : "—"}</bdi></Item>
      </dl>
    </section>
    {(check.measurements.length > 0 || check.actions.includes("measure")) && <MeasurementsSection check={check} onChange={setCheck} />}
    {canReadRejections && closed && thousandths(check.qty_rejected) > 0 && <section className={s.panel} aria-label={t("rejections.title")}>
      <div className={s.actions} style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>{t("rejections.title")}</h2>
        {canCreateRejection && <Link href={`/quality-rejections/new?check=${check.id}`} className={s.button}>{t("rejections.add")}</Link>}
      </div>
      <p className={s.muted}>{t("rejections.hint")}</p>
      {check.rejections.length === 0 ? <p className={s.muted} style={{ margin: 0 }}>{t("rejections.empty")}</p> : <div className={s.tableWrap}><table className={s.table}>
        <thead><tr><th>{t("rejections.code")}</th><th>{t("fields.qtyRejected")}</th><th>{t("rejections.disposition")}</th><th>{t("rejections.status")}</th></tr></thead>
        <tbody>{check.rejections.map(r => <tr key={r.id}>
          <td><Link href={`/quality-rejections/${r.id}`}><bdi>{r.rejection_code}</bdi></Link></td>
          <td><bdi>{fmt.quantity(r.quantity_rejected, r.unit)}</bdi></td>
          <td>{r.disposition ? rejectionEnums(`disposition.${r.disposition}`) : "—"}</td>
          <td>{rejectionEnums(`dispositionStatus.${r.disposition_status}`)}</td>
        </tr>)}</tbody>
      </table></div>}
    </section>}
    {canReadDefects && <QualityDefectsList qualityCheckId={check.id} checkStatus={check.status} />}
    <QualityHistory entries={check.history} statusLabel={v => enums.has(`status.${v}`) ? enums(`status.${v}`) : v} />
    {dialog === "close" && <CloseDialog check={check} busy={busy} onClose={() => setDialog(null)}
      onConfirm={body => void act(() => closeQualityCheck(check.id, body))} />}
    {dialog === "cancel" && <ReasonDialog title={t("cancelDialog.title")} description={t("cancelDialog.text")} confirmLabel={t("actions.cancelInspection")}
      busy={busy} danger onClose={() => setDialog(null)} onConfirm={reason => void act(() => cancelQualityCheck(check.id, reason))} />}
  </PageFrame>;
}

// Records the result: accepted + rejected must equal inspected, and the result must agree with the rejected quantity.
function CloseDialog({ check, busy, onClose, onConfirm }: { check: QualityCheckData; busy: boolean; onClose: () => void; onConfirm: (body: CloseQualityCheckRequest) => void }) {
  const t = useTranslations("quality.qualityChecks");
  const enums = useTranslations("enums.qualityCheck.result");
  const reasons = useTranslations("enums.qualityRejection.rejectionReason");
  const common = useTranslations("common");
  const inspectedStart = thousandths(check.qty_inspected) > 0 ? check.qty_inspected : "";
  const [result, setResult] = useState<QualityCheckResult | "">("");
  const [inspected, setInspected] = useState(inspectedStart);
  const [accepted, setAccepted] = useState(inspectedStart);
  const [rejected, setRejected] = useState("0");
  const [reason, setReason] = useState("failed_quality_check");
  const [notes, setNotes] = useState(check.notes ?? "");
  const unit = check.unit ? ` (${check.unit})` : "";

  const numbers = [inspected, accepted, rejected].every(v => QUANTITY.test(v));
  const balanced = numbers && thousandths(accepted) + thousandths(rejected) === thousandths(inspected) && thousandths(inspected) > 0;
  const hasRejected = thousandths(rejected) > 0;
  const mismatch = result === "accepted" && hasRejected ? "acceptedWithRejected" : result === "rejected" && !hasRejected ? "rejectedWithout" : "";
  // QUAL-SPEC-001: a plan must be fully measured; a failed measurement rules out "accepted" (the server enforces both).
  const pendingMeasurements = check.measurements.filter(m => m.status === "pending").length;
  const failedMeasurements = check.measurements.filter(m => m.status === "fail").length;
  const valid = Boolean(result) && balanced && !mismatch && pendingMeasurements === 0 && !(result === "accepted" && failedMeasurements > 0);
  // Changing the inspected or accepted quantity keeps the rest as rejected.
  const rebalance = (nextInspected: string, nextAccepted: string) => {
    if (QUANTITY.test(nextInspected) && QUANTITY.test(nextAccepted) && thousandths(nextAccepted) <= thousandths(nextInspected))
      setRejected(String((thousandths(nextInspected) - thousandths(nextAccepted)) / 1000));
  };

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid || busy || !result) return;
    onConfirm({ result, qty_inspected: inspected, qty_accepted: accepted, qty_rejected: rejected, notes: notes.trim() || null,
      rejection_reason: hasRejected ? reason : null });
  }

  return <div className={s.overlay} onKeyDown={e => { if (e.key === "Escape" && !busy) onClose(); }}>
    <form role="dialog" aria-modal="true" aria-label={t("closeDialog.title")} className={`${s.panel} ${s.dialog}`} onSubmit={submit}>
      <h2 style={{ margin: 0 }}>{t("closeDialog.title")}</h2>
      <p className={s.muted} style={{ margin: 0 }}>{t("closeDialog.text")}</p>
      <label className={s.field}>{t("fields.result")}
        <select required value={result} disabled={busy} onChange={e => setResult(e.target.value as QualityCheckResult)} autoFocus>
          <option value="">{t("selectResult")}</option>
          {CHECK_RESULTS.map(v => <option key={v} value={v}>{enums(v)}</option>)}
        </select>
      </label>
      <div className={s.grid}>
        <label className={s.field}>{t("fields.qtyInspected")}{unit}
          <input type="number" required min="0.001" step="0.001" inputMode="decimal" value={inspected} disabled={busy}
            onChange={e => { setInspected(e.target.value); rebalance(e.target.value, accepted); }} />
        </label>
        <label className={s.field}>{t("fields.qtyAccepted")}{unit}
          <input type="number" required min="0" step="0.001" inputMode="decimal" value={accepted} disabled={busy}
            onChange={e => { setAccepted(e.target.value); rebalance(inspected, e.target.value); }} />
        </label>
        <label className={s.field}>{t("fields.qtyRejected")}{unit}
          <input type="number" required min="0" step="0.001" inputMode="decimal" value={rejected} disabled={busy} onChange={e => setRejected(e.target.value)} />
        </label>
      </div>
      {numbers && !balanced && <p className={s.error} style={{ margin: 0 }}>{t("qtyConstraint")}</p>}
      {mismatch && <p className={s.error} style={{ margin: 0 }}>{t(`closeDialog.${mismatch}`)}</p>}
      {pendingMeasurements > 0 && <p className={s.error} style={{ margin: 0 }}>{t("closeDialog.measurementsPending", { count: String(pendingMeasurements) })}</p>}
      {failedMeasurements > 0 && <p className={s.muted} style={{ margin: 0 }}>{t("closeDialog.measurementsFailed", { count: String(failedMeasurements) })}</p>}
      {hasRejected && <>
        <label className={s.field}>{t("closeDialog.rejectionReason")}
          <select value={reason} disabled={busy} onChange={e => setReason(e.target.value)}>
            {REASONS.map(v => <option key={v} value={v}>{reasons(v)}</option>)}
          </select>
        </label>
        <p className={s.muted} style={{ margin: 0 }}>{t("closeDialog.rejectionHint")}</p>
      </>}
      <label className={s.field}>{t("fields.notes")}<textarea maxLength={2000} value={notes} disabled={busy} onChange={e => setNotes(e.target.value)} /></label>
      <div className={s.actions}>
        <button type="button" className={s.button} disabled={busy} onClick={onClose}>{common("actions.close")}</button>
        <button type="submit" className={`${s.button} ${s.primary}`} disabled={!valid || busy}>{t("actions.closeInspection")}</button>
      </div>
    </form>
  </div>;
}
