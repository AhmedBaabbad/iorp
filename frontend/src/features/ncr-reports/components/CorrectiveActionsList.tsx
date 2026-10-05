"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { useHasAnyPermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { Q } from "@/lib/quality-permissions";
import { completeNcrAction, getCorrectiveActions, type ActionFilters } from "../api";
import { ncrErrorMessage } from "../ncr-errors";
import type { CorrectiveAction } from "../types";
import { ActionsTable, TextDialog } from "./NcrReportDetail";

const EMPTY: Required<ActionFilters> = { status: "open", mine: false, overdue: false, search: "" };

// "الإجراءات التصحيحية": every corrective action across the reports — what is open, whose, and what is late.
export function CorrectiveActionsList() {
  const t = useTranslations("ncr");
  const capa = useTranslations("capa");
  const errors = useTranslations("ncr.errors");
  const messages = useTranslations("messages");
  const canComplete = useHasAnyPermission([Q.NCR_ACTIONS_COMPLETE, Q.NCR_UPDATE]);
  const [filters, setFilters] = useState(EMPTY);
  const [rows, setRows] = useState<CorrectiveAction[] | null>(null);
  const [completing, setCompleting] = useState<CorrectiveAction | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try { setRows(await getCorrectiveActions(filters)); } catch (e) { setError(ncrErrorMessage(e, errors)); }
  }, [filters, errors]);
  useEffect(() => { const timer = setTimeout(() => void load(), 200); return () => clearTimeout(timer); }, [load]);
  const set = (field: keyof ActionFilters, value: string | boolean) => setFilters(old => ({ ...old, [field]: value }));

  async function complete(evidence: string) {
    if (!completing) return;
    setBusy(true); setError("");
    try { await completeNcrAction(completing.ncr_id, completing.id, evidence); setCompleting(null); await load(); }
    catch (e) { setError(ncrErrorMessage(e, errors)); } finally { setBusy(false); }
  }

  return <PageFrame title={capa("title")} subtitle={capa("subtitle")}>
    <section className={s.toolbar} aria-label={capa("filtersAria")}>
      <label className={s.field}>{t("filters.search")}<input type="search" value={filters.search} placeholder={capa("searchPlaceholder")}
        onChange={e => set("search", e.target.value)} /></label>
      <label className={s.field}>{t("fields.status")}
        <select value={filters.status} onChange={e => set("status", e.target.value)}>
          <option value="">{t("filters.all")}</option>{(["open", "done", "cancelled"] as const).map(v => <option key={v} value={v}>{t(`actionStatuses.${v}`)}</option>)}
        </select></label>
      <label><input type="checkbox" checked={filters.mine} onChange={e => set("mine", e.target.checked)} /> {capa("mine")}</label>
      <label><input type="checkbox" checked={filters.overdue} onChange={e => set("overdue", e.target.checked)} /> {capa("overdueOnly")}</label>
    </section>
    {error && <p role="alert" className={s.error}>{error}</p>}
    {rows === null && !error && <p className={s.muted}>{messages("loading.default")}</p>}
    {rows?.length === 0 && <section className={s.panel}><h2 style={{ marginTop: 0 }}>{capa("empty")}</h2><p className={s.muted} style={{ margin: 0 }}>{capa("emptyHint")}</p></section>}
    {rows && rows.length > 0 && <section className={s.panel}>
      <ActionsTable rows={rows} showReport canComplete={canComplete} canCancel={false} onComplete={setCompleting} />
    </section>}
    {completing && <TextDialog title={t("completeDialog.title")} text={completing.description} label={t("fields.evidence")} confirm={t("actions.complete")}
      busy={busy} onClose={() => setCompleting(null)} onConfirm={v => void complete(v)} />}
  </PageFrame>;
}
