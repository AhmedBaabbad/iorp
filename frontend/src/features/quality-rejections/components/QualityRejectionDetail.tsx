"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { ReasonDialog } from "@/features/production-demands/reason-dialog";
import s from "@/features/production-demands/demands.module.css";
import { QualityHistory } from "@/features/quality-checks/components/QualityHistory";
import { qualityErrorMessage } from "@/features/quality-checks/components/quality-errors";
import { useFormatter } from "@/hooks/useFormatter";
import { decideQualityRejection, executeQualityRejection, getQualityRejectionById } from "../api/quality-rejections-api";
import { DISPOSITIONS, type Disposition, type QualityRejectionData, type RejectionDecisionRequest } from "../types";
import { DispositionBadge } from "./DispositionBadge";
import { DispositionStatusBadge } from "./DispositionStatusBadge";

function Item({ label, children }: { label: string; children: ReactNode }) {
  return <div><dt className={s.muted}>{label}</dt><dd style={{ margin: "4px 0 0", overflowWrap: "anywhere" }}>{children}</dd></div>;
}

export function QualityRejectionDetail({ qualityRejectionId }: { qualityRejectionId: string }) {
  const t = useTranslations("quality.qualityRejections");
  const errors = useTranslations("quality.errors");
  const enums = useTranslations("enums.qualityRejection");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const [rejection, setRejection] = useState<QualityRejectionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dialog, setDialog] = useState<"decide" | "execute" | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { setRejection(await getQualityRejectionById(qualityRejectionId)); }
    catch (e) { setError(qualityErrorMessage(e, errors)); }
    finally { setLoading(false); }
  }, [qualityRejectionId, errors]);
  useEffect(() => { void load(); }, [load]);

  async function act(run: () => Promise<QualityRejectionData>) {
    setBusy(true); setError("");
    try { setRejection(await run()); setDialog(null); }
    catch (e) { setError(qualityErrorMessage(e, errors)); }
    finally { setBusy(false); }
  }

  const back = <Link href={rejection?.production_order_id ? `/quality-rejections?order=${rejection.production_order_id}` : "/quality-rejections"} className={s.button}>{t("backToList")}</Link>;
  if (loading) return <PageFrame title={t("detailTitle")} action={back}><p className={s.muted}>{messages("loading.default")}</p></PageFrame>;
  if (!rejection) return <PageFrame title={t("detailTitle")} action={back}><p role="alert" className={s.error}>{error || t("notFound")}</p></PageFrame>;
  const r = rejection;

  return <PageFrame title={r.rejection_code} subtitle={enums(`rejectionReason.${r.rejection_reason}`)} action={back}>
    {r.disposition_status === "executed" && <p role="status" className={s.muted}>{t("executedMessage")}</p>}
    {r.unresolved && <p role="status" className={s.error}>{r.disposition === "hold" ? t("hints.holdBlocks") : t("hints.pendingBlocks")}</p>}
    {error && <p role="alert" className={s.error}>{error}</p>}
    <section className={s.panel}>
      <div className={s.actions} style={{ justifyContent: "space-between", marginBottom: 16 }}>
        <span className={s.actions}><DispositionStatusBadge status={r.disposition_status} />{r.disposition && <DispositionBadge disposition={r.disposition} />}</span>
        {r.actions.length > 0 && <span className={s.actions}>
          {r.actions.includes("edit") && <Link href={`/quality-rejections/${r.id}/edit`} className={s.button}>{t("actions.edit")}</Link>}
          {r.actions.includes("decide") && <button type="button" className={`${s.button} ${s.primary}`} disabled={busy} onClick={() => setDialog("decide")}>
            {r.disposition ? t("actions.changeDecision") : t("actions.decide")}</button>}
          {r.actions.includes("execute") && <button type="button" className={`${s.button} ${s.primary}`} disabled={busy} onClick={() => setDialog("execute")}>{t("actions.markAsExecuted")}</button>}
        </span>}
      </div>
      <dl className={s.grid} style={{ margin: 0 }}>
        <Item label={t("fields.quantityRejected")}><bdi>{fmt.quantity(r.quantity_rejected, r.unit)}</bdi></Item>
        <Item label={t("fields.rejectionDate")}>{fmt.date(r.rejection_date)}</Item>
        <Item label={t("fields.productionOrder")}>{r.production_order_id ? <Link href={`/production-orders/${r.production_order_id}`}><bdi>{r.order_number ?? "—"}</bdi></Link> : "—"}</Item>
        <Item label={t("fields.line")}>{r.item_line_no ?? t("placeholders.wholeOrder")}</Item>
        <Item label={t("fields.qualityCheck")}>{r.quality_check_id ? <Link href={`/quality-checks/${r.quality_check_id}`}><bdi>{r.inspection_code ?? "—"}</bdi></Link> : "—"}</Item>
        <Item label={t("fields.rejectedBy")}>{r.rejected_by_name ?? "—"}</Item>
      </dl>
      <p style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}><span className={s.muted}>{t("fields.rejectionNotes")}: </span>{r.rejection_notes}</p>
    </section>
    {r.disposition && <section className={s.panel} aria-label={t("decisionSection")}>
      <h2 style={{ marginTop: 0 }}>{t("decisionSection")}</h2>
      <dl className={s.grid} style={{ margin: 0 }}>
        <Item label={t("fields.disposition")}>{enums(`disposition.${r.disposition}`)}</Item>
        <Item label={t("fields.decidedBy")}>{r.decided_by_name ?? "—"}{r.decided_at ? ` — ${fmt.dateTime(r.decided_at)}` : ""}</Item>
        {r.concession_approved_by && <Item label={t("fields.concessionApprovedBy")}>{r.concession_approved_by}</Item>}
        {r.disposition_status === "executed" && <Item label={t("fields.executedBy")}>{r.executed_by_name ?? "—"}{r.executed_at ? ` — ${fmt.dateTime(r.executed_at)}` : ""}</Item>}
      </dl>
      {r.decision_notes && <p style={{ whiteSpace: "pre-wrap" }}><span className={s.muted}>{t("fields.decisionNotes")}: </span>{r.decision_notes}</p>}
      {r.execution_notes && <p style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}><span className={s.muted}>{t("fields.executionNotes")}: </span>{r.execution_notes}</p>}
    </section>}
    <QualityHistory entries={r.history} statusLabel={v => enums.has(`dispositionStatus.${v}`) ? enums(`dispositionStatus.${v}`) : v} />
    {dialog === "decide" && <DecideDialog rejection={r} busy={busy} onClose={() => setDialog(null)} onConfirm={body => void act(() => decideQualityRejection(r.id, body))} />}
    {dialog === "execute" && <ReasonDialog title={t("executeDialog.title")} description={t("executeDialog.text", { disposition: r.disposition ? enums(`disposition.${r.disposition}`) : "" })}
      confirmLabel={t("actions.markAsExecuted")} busy={busy} reasonRequired={false} onClose={() => setDialog(null)}
      onConfirm={notes => void act(() => executeQualityRejection(r.id, notes))} />}
  </PageFrame>;
}

// The disposition; "use as is" needs who approved the concession and why.
function DecideDialog({ rejection, busy, onClose, onConfirm }: { rejection: QualityRejectionData; busy: boolean; onClose: () => void; onConfirm: (body: RejectionDecisionRequest) => void }) {
  const t = useTranslations("quality.qualityRejections");
  const dispositions = useTranslations("enums.qualityRejection.disposition");
  const common = useTranslations("common");
  const [disposition, setDisposition] = useState<Disposition | "">(rejection.disposition ?? "");
  const [notes, setNotes] = useState(rejection.decision_notes ?? "");
  const [approver, setApprover] = useState(rejection.concession_approved_by ?? "");
  const concession = disposition === "use_as_is";
  const valid = Boolean(disposition) && (!concession || (notes.trim() && approver.trim()));

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid || busy || !disposition) return;
    onConfirm({ disposition, decision_notes: notes.trim() || null, concession_approved_by: concession ? approver.trim() : null });
  }

  return <div className={s.overlay} onKeyDown={e => { if (e.key === "Escape" && !busy) onClose(); }}>
    <form role="dialog" aria-modal="true" aria-label={t("decideDialog.title")} className={`${s.panel} ${s.dialog}`} onSubmit={submit}>
      <h2 style={{ margin: 0 }}>{t("decideDialog.title")}</h2>
      <p className={s.muted} style={{ margin: 0 }}>{t("decideDialog.text")}</p>
      <label className={s.field}>{t("fields.disposition")}
        <select required value={disposition} disabled={busy} autoFocus onChange={e => setDisposition(e.target.value as Disposition)}>
          <option value="">{t("placeholders.selectDisposition")}</option>
          {DISPOSITIONS.map(v => <option key={v} value={v}>{dispositions(v)}</option>)}
        </select>
      </label>
      {disposition && <p className={s.muted} style={{ margin: 0 }}>{t(`dispositionHints.${disposition}`)}</p>}
      {concession && <label className={s.field}>{t("fields.concessionApprovedBy")}
        <input required maxLength={255} value={approver} disabled={busy} onChange={e => setApprover(e.target.value)} />
      </label>}
      <label className={s.field}>{concession ? t("fields.concessionJustification") : t("fields.decisionNotesOptional")}
        <textarea required={concession} maxLength={2000} value={notes} disabled={busy} onChange={e => setNotes(e.target.value)} />
      </label>
      <div className={s.actions}>
        <button type="button" className={s.button} disabled={busy} onClick={onClose}>{common("actions.close")}</button>
        <button type="submit" className={`${s.button} ${s.primary}`} disabled={!valid || busy}>{t("actions.saveDecision")}</button>
      </div>
    </form>
  </div>;
}
