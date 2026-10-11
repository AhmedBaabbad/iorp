"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState, type FormEvent } from "react";

import { UnitSelect } from "@/components/forms/UnitSelect";
import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { getProductionOrderById } from "@/features/production-orders/api/production-orders-api";
import { ProductionOrderPicker } from "@/features/production-orders/components/ProductionOrderPicker";
import type { ProductionOrderData } from "@/features/production-orders/types";
import { getWorkCenters } from "@/features/work-centers";
import { useFormatter } from "@/hooks/useFormatter";
import { createWasteRecord, getOrderRuns, getWasteRecordById, updateWasteRecord, type RunOption } from "../api";
import type { WasteCategory, WasteRecordData } from "../types";
import { splitCheck } from "../waste-rules";
import { QUANTITY, todayIso, WASTE_CATEGORIES, WASTE_ORDER_STATUSES } from "../waste-rules";
import { wasteErrorMessage } from "./waste-errors";
import { P } from "@/lib/production-permissions";
import { UNITS } from "@/lib/units";

type Share = { category: WasteCategory; quantity: string };
type Values = { order: string; item: string; run: string; center: string; date: string; quantity: string; unit: string; shares: Share[]; reason: string; notes: string };

// Records waste against a production order (required), optionally one of its runs; or edits a record (recordId).
export function WasteRecordForm({ recordId }: { recordId?: string }) {
  const t = useTranslations("production.wasteRecords");
  const categories = useTranslations("enums.wasteRecord.wasteCategory");
  const hints = useTranslations("production.wasteRecords.categoryHints");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const router = useRouter();
  const params = useSearchParams();
  const canReadRuns = usePermission(P.RUNS_READ);
  const editing = Boolean(recordId);
  const [values, setValues] = useState<Values>({ order: params.get("order") ?? "", item: "", run: "", center: "", date: todayIso(), quantity: "", unit: "kg", shares: [{ category: "process", quantity: "" }], reason: "", notes: "" });
  const [existing, setExisting] = useState<WasteRecordData | null>(null);
  const [order, setOrder] = useState<ProductionOrderData | null>(null);
  const [runs, setRuns] = useState<RunOption[]>([]);
  const [centers, setCenters] = useState<{ id: string; code: string; name: string }[]>([]);
  const [loading, setLoading] = useState(editing);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getWorkCenters().then(setCenters).catch(() => setCenters([]));
  }, []);
  useEffect(() => {
    if (!recordId) return;
    let active = true;
    getWasteRecordById(recordId).then(r => {
      if (!active) return;
      setExisting(r);
      setValues({ order: r.production_order_id, item: r.production_order_item_id ?? "", run: r.production_run_id ?? "", center: r.production_run_id ? "" : r.work_center_id,
        // A unit awaiting review is not offered again: a unit from the list has to be chosen before saving.
        date: r.waste_date, quantity: r.quantity_wasted, unit: r.unit_needs_review || !UNITS.includes(r.unit) ? "" : r.unit, shares: r.categories.map(c => ({ category: c.category, quantity: c.quantity })), reason: r.reason_code ?? "", notes: r.notes ?? "" });
    }).catch(e => { if (active) setError(wasteErrorMessage(e, t)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [recordId, t]);
  // The chosen order's items and runs.
  useEffect(() => {
    if (!values.order) { setOrder(null); setRuns([]); return; }
    let active = true;
    getProductionOrderById(values.order).then(o => { if (active) setOrder(o); }).catch(() => { if (active) setOrder(null); });
    if (canReadRuns) getOrderRuns(values.order).then(list => { if (active) setRuns(list.filter(r => r.status !== "cancelled")); }).catch(() => { if (active) setRuns([]); });
    return () => { active = false; };
  }, [values.order, canReadRuns]);

  const locked = Boolean(existing && !existing.labels?.actions.includes("edit"));
  const run = useMemo(() => runs.find(r => r.id === values.run) ?? null, [runs, values.run]);
  // One category takes the whole quantity; several need shares that add up to it (the server checks the same).
  const split = splitCheck(values.quantity, values.shares);
  const valid = Boolean(values.order && values.date && UNITS.includes(values.unit) && QUANTITY.test(values.quantity) && Number(values.quantity) > 0 && split.ok);
  const toggle = (category: WasteCategory, on: boolean) => setValues(old => ({ ...old,
    shares: on ? [...old.shares, { category, quantity: "" }] : old.shares.filter(x => x.category !== category) }));
  const share = (category: WasteCategory, quantity: string) => setValues(old => ({ ...old, shares: old.shares.map(x => x.category === category ? { ...x, quantity } : x) }));
  const set = <K extends keyof Values>(field: K, value: Values[K]) => setValues(old => ({ ...old, [field]: value, ...(field === "order" ? { item: "", run: "" } : {}) }));

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid || busy || locked) return;
    setBusy(true); setError("");
    const body = {
      production_order_item_id: values.item || null, production_run_id: values.run || null,
      // A run decides the work center; otherwise the one chosen, else the order's.
      work_center_id: values.run ? null : values.center || null,
      waste_date: values.date, quantity_wasted: values.quantity, unit: values.unit,
      categories: values.shares.length === 1 ? [{ category: values.shares[0].category }] : values.shares.map(x => ({ category: x.category, quantity: x.quantity })),
      reason_code: values.reason.trim() || null, notes: values.notes.trim() || null,
    };
    try {
      const saved = recordId ? await updateWasteRecord(recordId, body) : await createWasteRecord({ production_order_id: values.order, ...body });
      router.push(`/waste-records/${saved.id}`);
    } catch (e) { setError(wasteErrorMessage(e, t)); setBusy(false); }
  }

  const back = recordId ? `/waste-records/${recordId}` : values.order ? `/waste-records?order=${values.order}` : "/waste-records";
  return <PageFrame title={editing ? t("editTitle") : t("createTitle")} subtitle={t("createSubtitle")}
    action={<Link href={back} className={s.button}>{t("actions.back")}</Link>}>
    {loading ? <p className={s.muted}>{messages("loading.default")}</p> : <form className={s.panel} onSubmit={submit} aria-label={editing ? t("editTitle") : t("createTitle")}>
      {locked && <p role="status" className={s.error}>{t("hints.locked")}</p>}
      <p className={s.muted} style={{ marginTop: 0 }}>{t("hints.notScrap")}</p>
      <div className={s.grid}>
        <label className={s.field}>{t("fields.productionOrder")}
          {editing ? <input readOnly value={order?.production_order_number ?? existing?.labels?.order_number ?? ""} />
            // Searched on the server among the orders waste can be recorded on (running, held, completed).
            : <ProductionOrderPicker value={values.order} onChange={id => set("order", id)} statuses={WASTE_ORDER_STATUSES} required disabled={busy}
              emptyLabel={t("placeholders.selectOrder")} ariaLabel={t("fields.productionOrder")} />}
        </label>

        {(order?.lines?.length ?? 0) > 0 && <label className={s.field}>{t("fields.lineOptional")}
          <select value={values.item} disabled={busy || locked} onChange={e => set("item", e.target.value)}>
            <option value="">{t("placeholders.wholeOrder")}</option>
            {order!.lines!.map(l => <option key={l.id} value={l.id}>{t("lineOption", { no: String(l.line_no), unit: l.unit })}</option>)}
          </select>
        </label>}
        {canReadRuns && <label className={s.field}>{t("fields.runOptional")}
          <select value={values.run} disabled={busy || locked || !values.order} onChange={e => set("run", e.target.value)}>
            <option value="">{runs.length ? t("placeholders.noRun") : t("placeholders.noRuns")}</option>
            {runs.map(r => <option key={r.id} value={r.id}>{t("runOption", { date: fmt.date(r.run_date), center: centers.find(c => c.id === r.work_center_id)?.name ?? "—" })}</option>)}
          </select>
        </label>}
        <label className={s.field}>{t("fields.workCenter")}
          <select value={run ? run.work_center_id : values.center} disabled={busy || locked || Boolean(run)} onChange={e => set("center", e.target.value)}>
            <option value="">{t("placeholders.orderWorkCenter")}</option>
            {centers.map(c => <option key={c.id} value={c.id}>{c.code} — {c.name}</option>)}
          </select>
        </label>
        <label className={s.field}>{t("fields.wasteDate")}<input type="date" required value={values.date} disabled={busy || locked} onChange={e => set("date", e.target.value)} /></label>
        <label className={s.field}>{t("fields.quantityWasted")}
          <input type="number" required min="0.001" step="0.001" inputMode="decimal" value={values.quantity} disabled={busy || locked} onChange={e => set("quantity", e.target.value)} />
        </label>
        <label className={s.field}>{t("fields.unit")}
          <UnitSelect className="unit-select" value={values.unit} disabled={busy || locked} onChange={value => set("unit", value)} ariaLabel={t("fields.unit")} />
          {existing?.unit_needs_review && <small role="status" className={s.error}>{t("hints.unitReview", { unit: existing.legacy_unit_text ?? existing.unit })}</small>}
        </label>
        <label className={s.field}>{t("fields.reasonCode")}<input maxLength={255} value={values.reason} disabled={busy || locked} onChange={e => set("reason", e.target.value)} /></label>
      </div>
      <fieldset className={s.panel} disabled={busy || locked} style={{ margin: "16px 0" }}>
        <legend>{t("fields.wasteCategories")}</legend>
        <p className={s.muted} style={{ marginTop: 0 }}>{t("hints.categories")}</p>
        <div className={s.actions} style={{ flexWrap: "wrap" }}>
          {WASTE_CATEGORIES.map(c => <label key={c} className={s.badge} style={{ cursor: "pointer" }}>
            <input type="checkbox" checked={values.shares.some(x => x.category === c)} onChange={e => toggle(c, e.target.checked)} /> {categories(c)}
          </label>)}
        </div>
        {values.shares.length > 1 && <div className={s.tableWrap} style={{ marginTop: 12 }}><table className={s.table} aria-label={t("fields.categoryShares")}>
          <thead><tr><th>{t("fields.wasteCategory")}</th><th>{t("fields.share")}</th></tr></thead>
          <tbody>{values.shares.map(x => <tr key={x.category}><td>{categories(x.category)}</td>
            <td><input type="number" min="0.001" step="0.001" inputMode="decimal" aria-label={`${t("fields.share")} ${categories(x.category)}`} value={x.quantity}
              onChange={e => share(x.category, e.target.value)} /> {values.unit}</td></tr>)}</tbody>
        </table></div>}
        {values.shares.length > 1 && <p role="status" className={split.ok ? s.muted : s.error}>
          {t("hints.sharesTotal", { total: split.total, quantity: values.quantity || "0", remaining: split.remaining })}</p>}
        {!values.shares.length && <p role="alert" className={s.error}>{t("hints.categoryRequired")}</p>}
        {values.shares.map(x => <p key={x.category} className={s.muted}>{categories(x.category)}: {hints(x.category)}</p>)}
      </fieldset>
      {run && <p className={s.muted}>{t("hints.runWorkCenter")}</p>}
      <label className={s.field}>{t("fields.notes")}<textarea maxLength={2000} value={values.notes} disabled={busy || locked} onChange={e => set("notes", e.target.value)} /></label>
      {error && <p role="alert" className={s.error}>{error}</p>}
      <div className={s.actions} style={{ marginTop: 16 }}>
        <button type="submit" className={`${s.button} ${s.primary}`} disabled={!valid || busy || locked}>{editing ? t("actions.save") : t("actions.record")}</button>
        <Link href={back} className={s.button}>{t("actions.cancel")}</Link>
      </div>
    </form>}
  </PageFrame>;
}
