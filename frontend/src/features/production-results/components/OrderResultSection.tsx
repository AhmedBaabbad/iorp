"use client";

import {useUnitLabel} from "@/components/UnitLabel";
import { UnitLabel } from "@/components/UnitLabel";
import { Fragment, useCallback, useEffect, useState, type ReactNode } from "react";
import { useTranslations } from "next-intl";
import { usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { useFormatter } from "@/hooks/useFormatter";
import { correctResultEntry, createResultEntry, deleteResultEntry, getOrderResult, updateResultEntry } from "../api";
import { RESULT_PENDING_STATUSES } from "../result-rules";
import type { OrderResult, ResultEntry, ResultOriginal, ResultSummary } from "../types";
import { CorrectionDialog } from "./CorrectionDialog";
import { ResultEntryDialog } from "./ResultEntryDialog";
import { resultErrorMessage } from "./result-errors";
import { P } from "@/lib/production-permissions";

type Dialog = { kind: "add" } | { kind: "edit" | "delete" | "correct"; entry: ResultOriginal } | null;
const pct = (value: string | null) => (value === null ? "—" : `${value}%`);

// "النتيجة النهائية للإنتاج": shown for completed and closed orders; what can be done comes from the server.
export function OrderResultSection({ order, revision = 0, onChanged }: {
  order: { id: string; status: string }; revision?: number; onChanged?: () => void;
}) {
  const unitText = useUnitLabel();
  const t = useTranslations("production.results");
  const canRead = usePermission(P.RESULTS_READ);
  const available = order.status === "completed" || order.status === "closed";
  const [view, setView] = useState<OrderResult | null>(null);
  const [loadError, setLoadError] = useState("");
  const [dialog, setDialog] = useState<Dialog>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoadError("");
    try { setView(await getOrderResult(order.id)); } catch (e) { setLoadError(resultErrorMessage(e, t)); }
  }, [order.id, t]);
  useEffect(() => { if (canRead && available) void load(); }, [canRead, available, load, revision, order.status]);
  // Opened from the results screen (…#result): bring the section into view once it has loaded.
  const loaded = Boolean(view);
  useEffect(() => {
    if (loaded && typeof window !== "undefined" && window.location.hash === "#result") document.getElementById("result")?.scrollIntoView({ block: "start" });
  }, [loaded]);

  async function run(action: () => Promise<OrderResult | void>) {
    setBusy(true); setError("");
    try {
      const next = await action();
      if (next) setView(next); else await load();
      setDialog(null);
      onChanged?.();
    } catch (e) { setError(resultErrorMessage(e, t)); }
    finally { setBusy(false); }
  }
  const close = () => { setDialog(null); setError(""); };

  if (!canRead || order.status === "cancelled") return null;
  if (!available) {
    return RESULT_PENDING_STATUSES.includes(order.status)
      ? <section className={s.panel} aria-label={t("title")}><h2 style={{ marginTop: 0 }}>{t("title")}</h2><p className={s.muted} style={{ margin: 0 }}>{t("pendingHint")}</p></section>
      : null;
  }

  return <section id="result" className={s.panel} aria-label={t("title")}>
    <div className={s.actions} style={{ justifyContent: "space-between" }}>
      <h2 style={{ margin: 0 }}>{t("title")}</h2>
      {view?.actions.includes("create") && <button type="button" className={`${s.button} ${s.primary}`} disabled={busy} onClick={() => setDialog({ kind: "add" })}>{t("actions.add")}</button>}
    </div>
    <p className={s.muted}>{view?.locked ? t("lockedHint") : t("editableHint")}</p>
    {loadError && <p role="alert" className={s.error}>{loadError}</p>}
    {error && !dialog && <p role="alert" className={s.error}>{error}</p>}
    {view && <>
      {view.totals.map(total => <SummaryCards key={total.unit} summary={total} unit={total.unit} showUnit={view.totals.length > 1} />)}
      {view.allocation_level === "none" && <p className={s.muted}>{t("noAllocationHint")}</p>}
      <EntriesTable view={view} busy={busy} onAction={(kind, entry) => setDialog({ kind, entry })} />
    </>}
    {view && dialog?.kind === "add" && <ResultEntryDialog view={view} entry={null} busy={busy} error={error} onClose={close}
      onSave={body => run(() => createResultEntry(order.id, body))} />}
    {view && dialog?.kind === "edit" && <ResultEntryDialog view={view} entry={dialog.entry} busy={busy} error={error} onClose={close}
      onSave={body => run(() => updateResultEntry(order.id, dialog.entry.id, body))} />}
    {dialog?.kind === "correct" && <CorrectionDialog entry={dialog.entry} busy={busy} error={error} onClose={close}
      onSave={body => run(() => correctResultEntry(order.id, dialog.entry.id, body))} />}
    {dialog?.kind === "delete" && <div className={s.overlay} onKeyDown={e => { if (e.key === "Escape" && !busy) close(); }}>
      <div role="dialog" aria-modal="true" aria-label={t("delete.title")} className={`${s.panel} ${s.dialog}`}>
        <h2>{t("delete.title")}</h2>
        <p className={s.muted}>{t("delete.text", { disposition: t(`dispositions.${dialog.entry.disposition}`), quantity: dialog.entry.quantity, unit: dialog.entry.unit })}</p>
        {error && <p role="alert" className={s.error}>{error}</p>}
        <div className={s.actions}>
          <button type="button" className={s.button} disabled={busy} onClick={close} autoFocus>{t("actions.cancel")}</button>
          <button type="button" className={`${s.button} ${s.danger}`} disabled={busy} onClick={() => run(() => deleteResultEntry(order.id, dialog.entry.id))}>{t("actions.delete")}</button>
        </div>
      </div>
    </div>}
  </section>;
}

export function SummaryCards({ summary, unit, showUnit }: { summary: ResultSummary; unit: string; showUnit?: boolean }) {
  const unitText = useUnitLabel();
  const t = useTranslations("production.results");
  const fmt = useFormatter();
  const q = (value: string) => <bdi>{fmt.quantity(value, unit)}</bdi>;
  const cards: [string, ReactNode][] = [
    ["planned", q(summary.planned_qty)], ["customerGood", q(summary.customer_good)], ["stockGood", q(summary.stock_good)],
    ["samples", q(summary.samples_total)], ["scrap", q(summary.scrap_total)], ["rework", q(summary.rework_total)],
    ["fulfillment", pct(summary.fulfillment_pct)], ["lossPct", pct(summary.loss_pct)],
  ];
  return <div style={{ marginBottom: 16 }}>
    {showUnit && <h3 style={{ margin: "0 0 8px" }}>{t("summary.unitGroup", { unit })}</h3>}
    <dl className={s.grid} style={{ margin: 0 }} aria-label={t("summary.label", { unit })}>
      {cards.map(([key, value]) => <div key={key} className={s.panel} style={{ margin: 0, padding: 14 }}>
        <dt className={s.muted}>{t(`summary.${key}`)}</dt><dd style={{ margin: "6px 0 0", fontSize: 20, fontWeight: 700 }}>{value}</dd>
      </div>)}
    </dl>
    <p className={s.muted}>
      {t("summary.details", { good: summary.good_total, samplesLoss: summary.samples_loss, loss: summary.loss_total, total: summary.total_output, unit })}
      {" · "}{t("summary.yield")}: {pct(summary.yield_pct)}{" · "}{t("summary.variance")}: <bdi>{fmt.quantity(summary.variance_qty, unit)}</bdi>
      {summary.secondary_totals.map(sec => <span key={sec.unit}>{" · "}{t("summary.secondary")}: <bdi>{fmt.quantity(sec.quantity, sec.unit)}</bdi></span>)}
    </p>
  </div>;
}

function EntriesTable({ view, busy, onAction }: { view: OrderResult; busy: boolean; onAction: (kind: "edit" | "delete" | "correct", entry: ResultOriginal) => void }) {
  const unitText = useUnitLabel();
  const t = useTranslations("production.results");
  const fmt = useFormatter();
  if (!view.entries.length) return <p className={s.muted}>{t("empty")}</p>;
  const row = (e: ResultEntry, correction: boolean) => <>
    <td>{correction ? <span className={s.muted}>↳ </span> : null}{t(`dispositions.${e.disposition}`)}</td>
    <td>{e.line_no ?? "—"}</td>
    <td><bdi>{correction && Number(e.quantity) > 0 ? "+" : ""}{fmt.number(e.quantity)}</bdi></td>
    <td><UnitLabel value={e.unit}/></td>
    <td>{e.secondary_quantity !== null ? <bdi>{fmt.quantity(e.secondary_quantity, e.secondary_unit)}</bdi> : "—"}</td>
    <td>{e.counts_as_loss ? t("yes") : t("no")}</td>
    <td>{correction ? e.correction_reason : (e.reason_code ?? "—")}</td>
    <td>{e.notes ?? "—"}</td>
    <td><span className={`${s.badge} ${correction ? s.high : ""}`}>{t(`entryTypes.${e.entry_type}`)}</span></td>
    <td>{e.created_by_name ?? "—"}</td>
    <td>{fmt.dateTime(e.created_at)}</td>
  </>;
  return <div className={s.tableWrap}><table className={s.table} aria-label={t("entriesLabel")}>
    <thead><tr>
      {["disposition", "item", "quantity", "unit", "secondary", "countsAsLoss", "reason", "notes", "type", "by", "date"].map(c => <th key={c}>{t(`columns.${c}`)}</th>)}
      <th>{t("columns.actions")}</th>
    </tr></thead>
    <tbody>{view.entries.map(e => <Fragment key={e.id}>
      <tr>{row(e, false)}<td className={s.actions}>
        {e.actions.includes("edit") && <button type="button" className={s.button} disabled={busy} onClick={() => onAction("edit", e)}>{t("actions.edit")}</button>}
        {e.actions.includes("delete") && <button type="button" className={s.button} disabled={busy} onClick={() => onAction("delete", e)}>{t("actions.delete")}</button>}
        {e.actions.includes("correct") && <button type="button" className={s.button} disabled={busy} onClick={() => onAction("correct", e)}>{t("actions.correct")}</button>}
      </td></tr>
      {e.corrections.map(c => <tr key={c.id} className={s.muted}>{row(c, true)}<td /></tr>)}
      {e.corrections.length > 0 && <tr><td /><td colSpan={11} className={s.muted}>{t("effective", { value: e.effective_quantity, unit: unitText(e.unit) })}</td></tr>}
    </Fragment>)}</tbody>
  </table></div>;
}
