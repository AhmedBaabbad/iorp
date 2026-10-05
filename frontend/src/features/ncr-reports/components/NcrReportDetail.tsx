"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";

import { UnitSelect } from "@/components/forms/UnitSelect";
import { PageFrame } from "@/components/layout/page-frame";
import { useHasAnyPermission, usePermission } from "@/features/auth/permission-hooks";
import { ReasonDialog } from "@/features/production-demands/reason-dialog";
import s from "@/features/production-demands/demands.module.css";
import { useFormatter } from "@/hooks/useFormatter";
import { Q } from "@/lib/quality-permissions";
import {
  addNcrAction, addNcrItem, cancelNcr, cancelNcrAction, completeNcrAction, containNcr, downloadNcrDocument, getNcrReport, getNcrUsers, investigateNcr,
  openNcrAttachment, removeNcrAttachment, removeNcrItem, submitNcr, updateNcrItem, uploadNcrAttachment, verifyNcr, type ActionBody, type InvestigateBody,
} from "../api";
import { DECIMAL, ncrErrorMessage } from "../ncr-errors";
import {
  ACTION_KINDS, COSTS, DISPOSITIONS, NCR_STAGES, ROOT_CAUSE_CATEGORIES, ROOT_CAUSE_METHODS, SUPPLIER_SOURCES,
  type CorrectiveAction, type NcrItem, type NcrItemInput, type NcrReport, type UserOption,
} from "../types";
import { NcrSeverityBadge, NcrStatusBadge } from "./NcrBadges";

function Item({ label, children }: { label: string; children: ReactNode }) {
  return <div><dt className={s.muted}>{label}</dt><dd style={{ margin: "4px 0 0", overflowWrap: "anywhere", whiteSpace: "pre-wrap" }}>{children}</dd></div>;
}

function Modal({ title, busy, onClose, onSubmit, children }: { title: string; busy: boolean; onClose: () => void; onSubmit: (e: FormEvent) => void; children: ReactNode }) {
  return <div className={s.overlay} onKeyDown={e => { if (e.key === "Escape" && !busy) onClose(); }}>
    <form role="dialog" aria-modal="true" aria-label={title} className={`${s.panel} ${s.dialog}`} onSubmit={onSubmit}>
      <h2 style={{ margin: 0 }}>{title}</h2>
      {children}
    </form>
  </div>;
}

type Dialog = { kind: "contain" | "investigate" | "verify" | "cancel" | "action" | "item" } | { kind: "editItem"; item: NcrItem }
  | { kind: "complete" | "cancelAction"; action: CorrectiveAction };

// One non-conformance report: where it stands, what it affects, containment, root cause, corrective actions, verification,
// the supplier, costs, files, the document and the history.
export function NcrReportDetail({ ncrReportId }: { ncrReportId: string }) {
  const t = useTranslations("ncr");
  const errors = useTranslations("ncr.errors");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const units = useTranslations("common.units.units");
  const unit = (code: string | null) => (code ? (units.has(code) ? units(code) : code) : "");
  const canFiles = useHasAnyPermission([Q.NCR_CREATE, Q.NCR_UPDATE]);
  const canUpdate = usePermission(Q.NCR_UPDATE);
  const [x, setX] = useState<NcrReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const picker = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try { setX(await getNcrReport(ncrReportId)); } catch (e) { setError(ncrErrorMessage(e, errors)); } finally { setLoading(false); }
  }, [ncrReportId, errors]);
  useEffect(() => { void load(); }, [load]);

  async function run(key: string, action: () => Promise<NcrReport | void>) {
    setBusy(key); setError("");
    try { const result = await action(); if (result) setX(result); setDialog(null); }
    catch (e) { setError(ncrErrorMessage(e, errors)); } finally { setBusy(null); }
  }

  const back = <Link href="/non-conformance-reports" className={s.button}>{t("backToList")}</Link>;
  if (loading) return <PageFrame title={t("detailTitle")} action={back}><p className={s.muted}>{messages("loading.default")}</p></PageFrame>;
  if (!x) return <PageFrame title={t("detailTitle")} action={back}><p role="alert" className={s.error}>{error || t("notFound")}</p></PageFrame>;
  const open = !["closed", "cancelled"].includes(x.status);
  const editableItems = open && canUpdate;
  const button = (action: "contain" | "investigate" | "verify" | "cancel", kind = s.primary) => x.actions.includes(action) &&
    <button type="button" className={`${s.button} ${kind}`} disabled={busy !== null} onClick={() => setDialog({ kind: action })}>{t(`actions.${action}`)}</button>;
  const stage = NCR_STAGES.indexOf(x.status);
  const costs = COSTS.filter(k => x[k] !== null);

  return <PageFrame title={x.report_number} subtitle={x.title} action={back}>
    {error && <p role="alert" className={s.error}>{error}</p>}
    {x.status === "cancelled" && <p role="status" className={s.error}>{t("cancelledHint", { reason: x.cancel_reason ?? "" })}</p>}
    <section className={s.panel}>
      <div className={s.actions} style={{ justifyContent: "space-between", marginBottom: 12 }}>
        <span className={s.actions}><NcrStatusBadge status={x.status} /><NcrSeverityBadge severity={x.severity} />
          {x.overdue && <span className={`${s.badge} ${s.urgent}`}>{t("overdue")}</span>}</span>
        <span className={s.actions}>
          {(["ar", "en"] as const).map(lang => <button key={lang} type="button" className={s.button} disabled={busy !== null}
            onClick={() => void run(`pdf-${lang}`, () => downloadNcrDocument(x.id, lang))}>{busy === `pdf-${lang}` ? t("preparing") : t(`download.${lang}`)}</button>)}
          {x.actions.includes("edit") && <Link href={`/non-conformance-reports/${x.id}/edit`} className={s.button}>{t("actions.edit")}</Link>}
          {button("contain")}{button("investigate")}
          {x.actions.includes("submit") && <button type="button" className={`${s.button} ${s.primary}`} disabled={busy !== null}
            onClick={() => void run("submit", () => submitNcr(x.id))}>{t("actions.submit")}</button>}
          {button("verify")}{button("cancel", s.danger)}
        </span>
      </div>
      {x.status !== "cancelled" && <ol aria-label={t("stagesAria")} style={{ display: "flex", flexWrap: "wrap", gap: 6, listStyle: "none", padding: 0, margin: "0 0 12px" }}>
        {NCR_STAGES.map((st, i) => <li key={st} className={`${s.badge} ${i < stage ? s.green : i === stage ? s.blue : ""}`}
          aria-current={i === stage ? "step" : undefined}>{i + 1}. {t(`stages.${st}`)}</li>)}
      </ol>}
      <p className={s.muted} style={{ marginTop: 0 }}>{t(`stageHints.${x.status}`)}</p>
      <dl className={s.grid} style={{ margin: 0 }}>
        <Item label={t("fields.date")}>{fmt.date(x.report_date)}</Item>
        <Item label={t("fields.source_type")}>{t(`sources.${x.source_type}`)}</Item>
        <Item label={t("fields.report_type")}>{t(`types.${x.report_type}`)}</Item>
        <Item label={t("fields.reference_code")}><bdi>{x.reference_code ?? "—"}</bdi></Item>
        <Item label={t("fields.owner")}>{x.owner_name ?? "—"}{x.due_date && <div className={x.overdue ? s.error : s.muted}>{t("dueOn", { date: fmt.date(x.due_date) })}</div>}</Item>
        <Item label={t("fields.detected_by")}>{x.detected_by_name ?? "—"}</Item>
        {SUPPLIER_SOURCES.includes(x.source_type) ? <>
          <Item label={t("fields.supplier_name")}>{x.supplier_id ? <Link href={`/suppliers/${x.supplier_id}`}>{x.supplier_name}</Link> : x.supplier_name ?? "—"}</Item>
          <Item label={t("fields.supplier_reference")}><bdi>{x.supplier_reference ?? "—"}</bdi></Item>
        </> : x.customer_name && <Item label={t("fields.customer_name")}>{x.customer_name}</Item>}
        {x.order_number && <Item label={t("fields.production_order")}><Link href={`/production-orders/${x.production_order_id}`}><bdi>{x.order_number}</bdi></Link></Item>}
        {x.return_no && <Item label={t("fields.return")}><Link href={`/shipment-returns/${x.return_id}`}><bdi>{x.return_no}</bdi></Link></Item>}
        {x.inspection_code && <Item label={t("fields.inspection")}><Link href={`/quality-checks/${x.quality_check_id}`}><bdi>{x.inspection_code}</bdi></Link></Item>}
        {x.rejection_code && <Item label={t("fields.rejection")}><Link href={`/quality-rejections/${x.quality_rejection_id}`}><bdi>{x.rejection_code}</bdi></Link></Item>}
      </dl>
      <p style={{ whiteSpace: "pre-wrap", marginBottom: 0 }}>{x.description}</p>
    </section>

    <section className={s.panel} aria-label={t("sections.items")}>
      <div className={s.actions} style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>{t("sections.items")}</h2>
        {editableItems && <button type="button" className={s.button} onClick={() => setDialog({ kind: "item" })}>{t("addItem")}</button>}
      </div>
      {x.items.length === 0 ? <p className={s.muted}>{t("noItems")}</p> : <div className={s.tableWrap}><table className={s.table}>
        <thead><tr><th>#</th><th>{t("itemFields.item_name")}</th><th>{t("itemFields.quantity_affected")}</th><th>{t("itemFields.issue_description")}</th>
          <th>{t("itemFields.disposition")}</th>{editableItems && <th />}</tr></thead>
        <tbody>{x.items.map(i => <tr key={i.id}>
          <td>{i.line_no}</td>
          <td>{i.item_name}{i.item_reference && <div className={s.muted}><bdi dir="ltr">{i.item_reference}</bdi></div>}</td>
          <td><bdi>{i.quantity_affected !== null ? fmt.quantity(i.quantity_affected, unit(i.unit)) : "—"}</bdi></td>
          <td style={{ whiteSpace: "pre-wrap" }}>{i.issue_description}</td>
          <td>{i.disposition ? t(`dispositions.${i.disposition}`) : <span className={s.error}>{t("placeholders.undecided")}</span>}
            {i.disposition_notes && <div className={s.muted}>{i.disposition_notes}</div>}</td>
          {editableItems && <td><span className={s.actions}>
            <button type="button" className={s.button} onClick={() => setDialog({ kind: "editItem", item: i })}>{t("actions.edit")}</button>
            <button type="button" className={`${s.button} ${s.danger}`} disabled={busy !== null}
              onClick={() => { if (window.confirm(t("removeItemConfirm", { name: i.item_name }))) void run("removeItem", () => removeNcrItem(x.id, i.id)); }}>{t("remove")}</button>
          </span></td>}
        </tr>)}</tbody>
      </table></div>}
    </section>

    {x.containment && <section className={s.panel} aria-label={t("sections.containment")}>
      <h2 style={{ marginTop: 0 }}>{t("sections.containment")}</h2>
      <p style={{ whiteSpace: "pre-wrap", marginTop: 0 }}>{x.containment}</p>
      <p className={s.muted} style={{ marginBottom: 0 }}>{x.contained_by_name} · {x.contained_at ? fmt.dateTime(x.contained_at) : ""}</p>
    </section>}

    {x.root_cause && <section className={s.panel} aria-label={t("sections.rootCause")}>
      <h2 style={{ marginTop: 0 }}>{t("sections.rootCause")}</h2>
      <dl className={s.grid} style={{ margin: 0 }}>
        <Item label={t("fields.root_cause_category")}>{x.root_cause_category ? t(`categories.${x.root_cause_category}`) : "—"}</Item>
        <Item label={t("fields.root_cause_method")}>{x.root_cause_method ? t(`methods.${x.root_cause_method}`) : "—"}</Item>
      </dl>
      <p style={{ whiteSpace: "pre-wrap" }}>{x.root_cause}</p>
      {x.no_action_justification && <p style={{ whiteSpace: "pre-wrap" }}><strong>{t("noActionNeeded")}:</strong> {x.no_action_justification}</p>}
      <p className={s.muted} style={{ marginBottom: 0 }}>{x.investigated_by_name} · {x.investigated_at ? fmt.dateTime(x.investigated_at) : ""}</p>
    </section>}

    {(x.corrective_actions.length > 0 || x.actions.includes("add_action")) && <section className={s.panel} aria-label={t("sections.actions")}>
      <div className={s.actions} style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>{t("sections.actions")}</h2>
        {x.actions.includes("add_action") && <button type="button" className={s.button} onClick={() => setDialog({ kind: "action" })}>{t("addAction")}</button>}
      </div>
      {x.corrective_actions.length === 0 ? <p className={s.muted}>{t("noActions")}</p> : <ActionsTable rows={x.corrective_actions} canComplete={x.can_complete_actions}
        canCancel={open && canUpdate} onComplete={a => setDialog({ kind: "complete", action: a })} onCancel={a => setDialog({ kind: "cancelAction", action: a })} />}
    </section>}

    {x.verified_at && <section className={s.panel} aria-label={t("sections.verification")}>
      <h2 style={{ marginTop: 0 }}>{t("sections.verification")}</h2>
      {x.status === "closed" && <p className={`${s.badge} ${s.green}`}>{t("effective")}</p>}
      {x.verification_notes && <p style={{ whiteSpace: "pre-wrap" }}>{x.verification_notes}</p>}
      <p className={s.muted} style={{ marginBottom: 0 }}>{x.verified_by_name} · {fmt.dateTime(x.verified_at)}
        {x.verification_attempts > 1 && ` · ${t("attempts", { count: String(x.verification_attempts) })}`}</p>
    </section>}

    {(x.supplier_action !== "none" || x.supplier_response || costs.length > 0 || x.claim_status !== "none") && <section className={s.panel} aria-label={t("sections.costs")}>
      <h2 style={{ marginTop: 0 }}>{t("sections.supplierAndCosts")}</h2>
      <dl className={s.grid} style={{ margin: 0 }}>
        {x.supplier_action !== "none" && <Item label={t("fields.supplier_action")}>{t(`supplierActions.${x.supplier_action}`)}</Item>}
        {x.supplier_response && <Item label={t("fields.supplier_response")}>{x.supplier_response}
          {x.supplier_responded_at && <div className={s.muted}>{fmt.date(x.supplier_responded_at)}</div>}</Item>}
        {costs.map(k => <Item key={k} label={t(`fields.${k}`)}><bdi>{fmt.number(x[k]!)}</bdi></Item>)}
        {x.total_cost && <Item label={t("fields.total_cost")}><strong><bdi>{fmt.number(x.total_cost)}</bdi></strong></Item>}
        {x.claim_status !== "none" && <Item label={t("fields.claim_status")}>{t(`claims.${x.claim_status}`)}
          {x.claim_amount && <div><bdi>{fmt.number(x.claim_amount)}</bdi></div>}</Item>}
      </dl>
    </section>}

    <section className={s.panel} aria-label={t("sections.files")}>
      <h2 style={{ marginTop: 0 }}>{t("sections.files")}</h2>
      {x.attachments.length === 0 ? <p className={s.muted}>{t("noFiles")}</p> : <ul style={{ listStyle: "none", padding: 0, margin: "0 0 10px", display: "grid", gap: 6 }}>
        {x.attachments.map(f => <li key={f.id} className={s.actions} style={{ justifyContent: "space-between" }}>
          <span><bdi>{f.file_name}</bdi> <span className={s.muted}>· {f.uploaded_by_name ?? "—"} · {fmt.dateTime(f.uploaded_at)}</span></span>
          <span className={s.actions}>
            <button type="button" className={s.button} onClick={() => void run("open", () => openNcrAttachment(x.id, f))}>{t("open")}</button>
            {open && canUpdate && <button type="button" className={`${s.button} ${s.danger}`} disabled={busy !== null}
              onClick={() => { if (window.confirm(t("removeFileConfirm", { name: f.file_name }))) void run("removeFile",
                async () => { const files = await removeNcrAttachment(x.id, f.id); setX(old => (old ? { ...old, attachments: files } : old)); }); }}>{t("remove")}</button>}
          </span>
        </li>)}
      </ul>}
      {open && canFiles && <div className={s.toolbar} style={{ marginBottom: 0 }}>
        <input ref={picker} type="file" hidden accept="image/png,image/jpeg,image/webp,application/pdf" aria-label={t("upload")} onChange={e => {
          const file = e.target.files?.[0];
          if (picker.current) picker.current.value = "";
          if (file) void run("upload", async () => { const files = await uploadNcrAttachment(x.id, file); setX(old => (old ? { ...old, attachments: files } : old)); });
        }} />
        <button type="button" className={s.button} disabled={busy !== null} onClick={() => picker.current?.click()}>{busy === "upload" ? t("uploading") : t("upload")}</button>
        <span className={s.muted}>{t("filesHint")}</span>
      </div>}
    </section>

    <section className={s.panel} aria-label={t("historyTitle")}>
      <h2 style={{ marginTop: 0 }}>{t("historyTitle")}</h2>
      <ol className={s.timeline}>{x.history.map((e, i) => <li key={`${e.at}-${i}`}>
        <strong>{t.has(`events.${e.action}`) ? t(`events.${e.action}`) : e.action}</strong>
        <span className={s.muted}>{e.actor_name ?? "—"} · {fmt.dateTime(e.at)}</span>
        {e.reason && <span style={{ whiteSpace: "pre-wrap" }}>{e.reason}</span>}
      </li>)}</ol>
    </section>

    {dialog?.kind === "contain" && <TextDialog title={t("containDialog.title")} text={t("containDialog.text")} label={t("fields.containment")}
      confirm={t("actions.contain")} busy={busy !== null} onClose={() => setDialog(null)} onConfirm={v => void run("contain", () => containNcr(x.id, v))} />}
    {dialog?.kind === "investigate" && <InvestigateDialog busy={busy !== null} onClose={() => setDialog(null)}
      onConfirm={body => void run("investigate", () => investigateNcr(x.id, body))} />}
    {dialog?.kind === "verify" && <VerifyDialog busy={busy !== null} onClose={() => setDialog(null)}
      onConfirm={(effective, notes) => void run("verify", () => verifyNcr(x.id, effective, notes))} />}
    {dialog?.kind === "cancel" && <ReasonDialog title={t("cancelDialog.title")} description={t("cancelDialog.text")} confirmLabel={t("actions.cancel")}
      danger busy={busy !== null} onClose={() => setDialog(null)} onConfirm={reason => void run("cancel", () => cancelNcr(x.id, reason))} />}
    {dialog?.kind === "action" && <ActionDialog busy={busy !== null} onClose={() => setDialog(null)} onConfirm={body => void run("action", () => addNcrAction(x.id, body))} />}
    {dialog?.kind === "complete" && <TextDialog title={t("completeDialog.title")} text={dialog.action.description} label={t("fields.evidence")}
      confirm={t("actions.complete")} busy={busy !== null} onClose={() => setDialog(null)}
      onConfirm={v => void run("complete", () => completeNcrAction(x.id, dialog.action.id, v))} />}
    {dialog?.kind === "cancelAction" && <ReasonDialog title={t("cancelActionDialog.title")} description={dialog.action.description}
      confirmLabel={t("actions.cancelAction")} danger busy={busy !== null} onClose={() => setDialog(null)}
      onConfirm={reason => void run("cancelAction", () => cancelNcrAction(x.id, dialog.action.id, reason))} />}
    {(dialog?.kind === "item" || dialog?.kind === "editItem") && <ItemDialog item={dialog.kind === "editItem" ? dialog.item : null} busy={busy !== null}
      onClose={() => setDialog(null)} onConfirm={body => void run("item", () => dialog.kind === "editItem" ? updateNcrItem(x.id, dialog.item.id, body) : addNcrItem(x.id, body))} />}
  </PageFrame>;
}

// Corrective actions: kind, what, who, by when, status and the evidence; finished ones stay as the record.
export function ActionsTable({ rows, canComplete, canCancel, onComplete, onCancel, showReport = false }: {
  rows: CorrectiveAction[]; canComplete: boolean; canCancel: boolean; onComplete: (a: CorrectiveAction) => void; onCancel?: (a: CorrectiveAction) => void;
  showReport?: boolean;
}) {
  const t = useTranslations("ncr");
  const fmt = useFormatter();
  return <div className={s.tableWrap}><table className={s.table}>
    <thead><tr>{showReport && <th>{t("fields.number")}</th>}<th>#</th><th>{t("fields.kind")}</th><th>{t("fields.action")}</th><th>{t("fields.owner")}</th>
      <th>{t("fields.due_date")}</th><th>{t("fields.status")}</th><th /></tr></thead>
    <tbody>{rows.map(a => <tr key={a.id}>
      {showReport && <td><Link href={`/non-conformance-reports/${a.ncr_id}`}><bdi>{a.report_number}</bdi></Link>
        {a.report_title && <div className={s.muted}>{a.report_title}</div>}</td>}
      <td>{a.line_no}</td>
      <td>{t(`kinds.${a.kind}`)}</td>
      <td style={{ whiteSpace: "pre-wrap" }}>{a.description}{(a.evidence || a.cancel_reason) && <div className={s.muted}>{a.evidence ?? a.cancel_reason}</div>}</td>
      <td>{a.owner_name ?? "—"}</td>
      <td className={a.overdue ? s.error : undefined}>{a.due_date ? fmt.date(a.due_date) : "—"}{a.overdue && <div>{t("overdue")}</div>}</td>
      <td>{t(`actionStatuses.${a.status}`)}{a.completed_at && <div className={s.muted}>{a.completed_by_name} · {fmt.date(a.completed_at)}</div>}</td>
      <td>{a.status === "open" && <span className={s.actions}>
        {canComplete && <button type="button" className={`${s.button} ${s.primary}`} onClick={() => onComplete(a)}>{t("actions.complete")}</button>}
        {canCancel && onCancel && <button type="button" className={s.button} onClick={() => onCancel(a)}>{t("actions.cancelAction")}</button>}
      </span>}</td>
    </tr>)}</tbody>
  </table></div>;
}

export function TextDialog({ title, text, label, confirm, busy, onClose, onConfirm }: { title: string; text: string; label: string; confirm: string;
  busy: boolean; onClose: () => void; onConfirm: (value: string) => void }) {
  const t = useTranslations("ncr");
  const [value, setValue] = useState("");
  return <Modal title={title} busy={busy} onClose={onClose} onSubmit={e => { e.preventDefault(); if (value.trim() && !busy) onConfirm(value.trim()); }}>
    <p className={s.muted} style={{ margin: 0, whiteSpace: "pre-wrap" }}>{text}</p>
    <label className={s.field}>{label}<textarea required autoFocus maxLength={4000} value={value} disabled={busy} onChange={e => setValue(e.target.value)} /></label>
    <div className={s.actions}>
      <button type="button" className={s.button} disabled={busy} onClick={onClose}>{t("cancel")}</button>
      <button type="submit" className={`${s.button} ${s.primary}`} disabled={busy || !value.trim()}>{confirm}</button>
    </div>
  </Modal>;
}

function InvestigateDialog({ busy, onClose, onConfirm }: { busy: boolean; onClose: () => void; onConfirm: (body: InvestigateBody) => void }) {
  const t = useTranslations("ncr");
  const [category, setCategory] = useState("");
  const [method, setMethod] = useState("");
  const [cause, setCause] = useState("");
  const [required, setRequired] = useState(true);
  const [why, setWhy] = useState("");
  const ok = Boolean(category && cause.trim()) && (required || Boolean(why.trim()));
  return <Modal title={t("investigateDialog.title")} busy={busy} onClose={onClose}
    onSubmit={e => { e.preventDefault(); if (ok && !busy) onConfirm({ root_cause_category: category, root_cause_method: method || null, root_cause: cause.trim(),
      action_required: required, no_action_justification: required ? null : why.trim() }); }}>
    <p className={s.muted} style={{ margin: 0 }}>{t("investigateDialog.text")}</p>
    <div className={s.grid}>
      <label className={s.field}>{t("fields.root_cause_category")}
        <select required autoFocus value={category} disabled={busy} onChange={e => setCategory(e.target.value)}>
          <option value="">—</option>{ROOT_CAUSE_CATEGORIES.map(c => <option key={c} value={c}>{t(`categories.${c}`)}</option>)}</select></label>
      <label className={s.field}>{t("fields.root_cause_method")}
        <select value={method} disabled={busy} onChange={e => setMethod(e.target.value)}>
          <option value="">—</option>{ROOT_CAUSE_METHODS.map(c => <option key={c} value={c}>{t(`methods.${c}`)}</option>)}</select></label>
    </div>
    <label className={s.field}>{t("fields.root_cause")}<textarea required maxLength={8000} value={cause} disabled={busy} onChange={e => setCause(e.target.value)} /></label>
    <label><input type="checkbox" checked={!required} disabled={busy} onChange={e => setRequired(!e.target.checked)} /> {t("investigateDialog.noAction")}</label>
    {!required && <label className={s.field}>{t("fields.no_action_justification")}<textarea required maxLength={4000} value={why} disabled={busy} onChange={e => setWhy(e.target.value)} /></label>}
    <div className={s.actions}>
      <button type="button" className={s.button} disabled={busy} onClick={onClose}>{t("cancel")}</button>
      <button type="submit" className={`${s.button} ${s.primary}`} disabled={busy || !ok}>{required ? t("investigateDialog.confirm") : t("investigateDialog.close")}</button>
    </div>
  </Modal>;
}

function VerifyDialog({ busy, onClose, onConfirm }: { busy: boolean; onClose: () => void; onConfirm: (effective: boolean, notes: string | null) => void }) {
  const t = useTranslations("ncr");
  const [effective, setEffective] = useState<"yes" | "no" | "">("");
  const [notes, setNotes] = useState("");
  const ok = effective === "yes" || (effective === "no" && Boolean(notes.trim()));
  return <Modal title={t("verifyDialog.title")} busy={busy} onClose={onClose}
    onSubmit={e => { e.preventDefault(); if (ok && !busy) onConfirm(effective === "yes", notes.trim() || null); }}>
    <p className={s.muted} style={{ margin: 0 }}>{t("verifyDialog.text")}</p>
    <div className={s.actions} role="radiogroup" aria-label={t("verifyDialog.title")}>
      <label><input type="radio" checked={effective === "yes"} disabled={busy} onChange={() => setEffective("yes")} /> {t("verifyDialog.effective")}</label>
      <label><input type="radio" checked={effective === "no"} disabled={busy} onChange={() => setEffective("no")} /> {t("verifyDialog.notEffective")}</label>
    </div>
    <label className={s.field}>{effective === "no" ? t("verifyDialog.notesRequired") : t("verifyDialog.notes")}
      <textarea maxLength={4000} required={effective === "no"} value={notes} disabled={busy} onChange={e => setNotes(e.target.value)} /></label>
    <div className={s.actions}>
      <button type="button" className={s.button} disabled={busy} onClick={onClose}>{t("cancel")}</button>
      <button type="submit" className={`${s.button} ${s.primary}`} disabled={busy || !ok}>{t("actions.verify")}</button>
    </div>
  </Modal>;
}

function ActionDialog({ busy, onClose, onConfirm }: { busy: boolean; onClose: () => void; onConfirm: (body: ActionBody) => void }) {
  const t = useTranslations("ncr");
  const [kind, setKind] = useState<string>("corrective");
  const [description, setDescription] = useState("");
  const [owner, setOwner] = useState("");
  const [outside, setOutside] = useState("");
  const [due, setDue] = useState("");
  const [users, setUsers] = useState<UserOption[]>([]);
  useEffect(() => { getNcrUsers().then(setUsers).catch(() => setUsers([])); }, []);
  const ok = Boolean(description.trim());
  return <Modal title={t("actionDialog.title")} busy={busy} onClose={onClose}
    onSubmit={e => { e.preventDefault(); if (ok && !busy) onConfirm({ kind, description: description.trim(), owner_user_id: owner || null,
      owner_name: owner ? null : outside.trim() || null, due_date: due || null }); }}>
    <p className={s.muted} style={{ margin: 0 }}>{t(`kindHints.${kind}`)}</p>
    <div className={s.grid}>
      <label className={s.field}>{t("fields.kind")}
        <select value={kind} disabled={busy} onChange={e => setKind(e.target.value)}>{ACTION_KINDS.map(k => <option key={k} value={k}>{t(`kinds.${k}`)}</option>)}</select></label>
      <label className={s.field}>{t("fields.owner")}
        <select value={owner} disabled={busy} onChange={e => setOwner(e.target.value)}>
          <option value="">{t("placeholders.outsideOwner")}</option>{users.map(u => <option key={u.id} value={u.id}>{u.name}</option>)}</select></label>
      {!owner && <label className={s.field}>{t("fields.owner_name")}<input maxLength={200} value={outside} disabled={busy} onChange={e => setOutside(e.target.value)} /></label>}
      <label className={s.field}>{t("fields.due_date")}<input type="date" value={due} disabled={busy} onChange={e => setDue(e.target.value)} /></label>
    </div>
    <label className={s.field}>{t("fields.action")}<textarea required autoFocus maxLength={4000} value={description} disabled={busy} onChange={e => setDescription(e.target.value)} /></label>
    <div className={s.actions}>
      <button type="button" className={s.button} disabled={busy} onClick={onClose}>{t("cancel")}</button>
      <button type="submit" className={`${s.button} ${s.primary}`} disabled={busy || !ok}>{t("addAction")}</button>
    </div>
  </Modal>;
}

function ItemDialog({ item, busy, onClose, onConfirm }: { item: NcrItem | null; busy: boolean; onClose: () => void; onConfirm: (body: NcrItemInput) => void }) {
  const t = useTranslations("ncr");
  const [v, setV] = useState({ item_name: item?.item_name ?? "", item_reference: item?.item_reference ?? "",
    quantity_affected: item?.quantity_affected !== null && item?.quantity_affected !== undefined ? String(Number(item.quantity_affected)) : "",
    unit: item?.unit ?? "", issue_description: item?.issue_description ?? "", disposition: item?.disposition ?? "", disposition_notes: item?.disposition_notes ?? "" });
  const set = (field: keyof typeof v, value: string) => setV(old => ({ ...old, [field]: value }));
  const ok = Boolean(v.item_name.trim() && v.issue_description.trim()) && (!v.quantity_affected.trim() || DECIMAL.test(v.quantity_affected.trim()));
  const title = item ? t("itemDialog.edit") : t("itemDialog.add");
  return <Modal title={title} busy={busy} onClose={onClose} onSubmit={e => {
    e.preventDefault();
    if (ok && !busy) onConfirm({ item_name: v.item_name.trim(), item_reference: v.item_reference.trim() || null, quantity_affected: v.quantity_affected.trim() || null,
      unit: v.unit || null, issue_description: v.issue_description.trim(), disposition: (v.disposition || null) as NcrItemInput["disposition"],
      disposition_notes: v.disposition_notes.trim() || null, notes: item?.notes ?? null });
  }}>
    <div className={s.grid}>
      <label className={s.field}>{t("itemFields.item_name")}<input required autoFocus maxLength={255} value={v.item_name} disabled={busy} onChange={e => set("item_name", e.target.value)} /></label>
      <label className={s.field}>{t("itemFields.item_reference")}<input maxLength={255} dir="auto" value={v.item_reference} disabled={busy} onChange={e => set("item_reference", e.target.value)} /></label>
      <label className={s.field}>{t("itemFields.quantity_affected")}<input inputMode="decimal" dir="ltr" value={v.quantity_affected} disabled={busy} onChange={e => set("quantity_affected", e.target.value)} /></label>
      <label className={s.field}>{t("itemFields.unit")}<UnitSelect value={v.unit} onChange={u => set("unit", u)} ariaLabel={t("itemFields.unit")} placeholder="—" required={false} /></label>
      <label className={s.field}>{t("itemFields.disposition")}
        <select value={v.disposition} disabled={busy} onChange={e => set("disposition", e.target.value)}>
          <option value="">{t("placeholders.undecided")}</option>{DISPOSITIONS.map(o => <option key={o} value={o}>{t(`dispositions.${o}`)}</option>)}</select></label>
    </div>
    <label className={s.field}>{t("itemFields.issue_description")}<textarea required maxLength={4000} value={v.issue_description} disabled={busy} onChange={e => set("issue_description", e.target.value)} /></label>
    <label className={s.field}>{t("itemFields.disposition_notes")}<textarea maxLength={4000} value={v.disposition_notes} disabled={busy} onChange={e => set("disposition_notes", e.target.value)} /></label>
    <div className={s.actions}>
      <button type="button" className={s.button} disabled={busy} onClick={onClose}>{t("cancel")}</button>
      <button type="submit" className={`${s.button} ${s.primary}`} disabled={busy || !ok}>{t("save")}</button>
    </div>
  </Modal>;
}
