"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { Pagination } from "@/components/pagination/Pagination";
import { usePagedFilters, type Page } from "@/lib/pagination";
import { useHasAnyPermission } from "@/features/auth/permission-hooks";
import { useFormatter } from "@/hooks/useFormatter";
import s from "@/features/production-demands/demands.module.css";
import { Q } from "@/lib/quality-permissions";
import { completeNcrAction, getCorrectiveActions, type ActionFilters } from "../api";
import { ncrErrorMessage } from "../ncr-errors";
import type { CapaAlerts, CorrectiveAction } from "../types";
import { refreshCapaAlerts, useCapaAlerts } from "../use-capa-alerts";
import { ActionsTable, TextDialog } from "./NcrReportDetail";

const EMPTY: Required<ActionFilters> = { status: "open", mine: false, overdue: false, search: "" };

// "الإجراءات التصحيحية": every corrective action across the reports — what is open, whose, and what is late.
export function CorrectiveActionsList() {
  const t = useTranslations("ncr");
  const capa = useTranslations("capa");
  const errors = useTranslations("ncr.errors");
  const messages = useTranslations("messages");
  const canComplete = useHasAnyPermission([Q.NCR_ACTIONS_COMPLETE]);
  const alerts = useCapaAlerts(true);
  // Filters and page live in the address (ARCH-PAGE-001); the list opens on the open actions.
  const paged = usePagedFilters(EMPTY);
  const filters = paged.filters;
  const [data, setData] = useState<Page<CorrectiveAction> | null>(null);
  const rows = data?.items ?? null;
  const [loading, setLoading] = useState(true);
  const [completing, setCompleting] = useState<CorrectiveAction | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const key = JSON.stringify(paged.query());
  const load = useCallback(async () => {
    setError(""); setLoading(true);
    try {
      const page = await getCorrectiveActions(paged.query());
      setData(page);
      // A filter left the page past the end: show the last page rather than an empty one.
      if (!page.items.length && page.total > 0 && paged.page > page.pages) paged.setPage(page.pages);
    } catch (e) { setError(ncrErrorMessage(e, errors)); }
    finally { setLoading(false); }
  }, [key, errors]); // eslint-disable-line react-hooks/exhaustive-deps -- paged changes every render; key is what matters
  useEffect(() => { const timer = setTimeout(() => void load(), 200); return () => clearTimeout(timer); }, [load]);
  const set = (field: keyof ActionFilters, value: string | boolean) => paged.set(field, value);

  async function complete(evidence: string) {
    if (!completing) return;
    setBusy(true); setError("");
    try { await completeNcrAction(completing.ncr_id, completing.id, evidence); setCompleting(null); await load(); void refreshCapaAlerts(); }
    catch (e) { setError(ncrErrorMessage(e, errors)); } finally { setBusy(false); }
  }

  return <PageFrame title={capa("title")} subtitle={capa("subtitle")}>
    {alerts && alerts.total > 0 && <AttentionPanel alerts={alerts} />}
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
    {data && <Pagination page={data.page} pageSize={data.page_size} total={data.total} pages={data.pages} disabled={loading}
      onPage={paged.setPage} onPageSize={paged.setPageSize} />}
  </PageFrame>;
}

// What needs the current user's attention: their actions late or due soon, their reports past due, reviews due (QUAL-CAPA-001).
function AttentionPanel({ alerts }: { alerts: CapaAlerts }) {
  const capa = useTranslations("capa");
  const fmt = useFormatter();
  return <section className={s.panel} aria-label={capa("attention.title")}>
    <div className={s.actions} style={{ justifyContent: "space-between" }}>
      <h2 style={{ margin: 0 }}>{capa("attention.title")}</h2>
      <span className={s.actions}>{(["overdue", "report_overdue", "review_due", "due_soon"] as const).filter(k => alerts[k] > 0).map(k =>
        <span key={k} className={`${s.badge} ${k === "due_soon" ? s.high : s.urgent}`}>{capa(`attention.counts.${k}`, { count: String(alerts[k]) })}</span>)}</span>
    </div>
    <ul style={{ listStyle: "none", padding: 0, margin: "10px 0 0", display: "grid", gap: 6 }}>
      {alerts.items.map((i, n) => <li key={`${i.kind}-${i.ncr_id}-${n}`} className={s.actions}>
        <span className={`${s.badge} ${i.kind === "due_soon" ? s.high : s.urgent}`}>{capa(`attention.kinds.${i.kind}`)}</span>
        <Link href={`/non-conformance-reports/${i.ncr_id}`}><bdi>{i.report_number}</bdi></Link>
        <span>{i.title}</span>
        {i.due_date && <span className={s.muted}>{fmt.date(i.due_date)}</span>}
      </li>)}
    </ul>
  </section>;
}
