"use client";
import {RecordCombobox} from "@/components/ui/RecordCombobox";

import { ReferenceTextSelect } from "@/features/reference-directory/ReferenceTextSelect";
import {EditorSurface} from "@/components/forms/EditorSurface";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";


import { usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { ProductionOrderPicker } from "@/features/production-orders/components/ProductionOrderPicker";
import { getWorkCenters } from "@/features/work-centers";
import { useFormatter } from "@/hooks/useFormatter";
import { createDowntimeEvent, getDowntimeEventById, getOrderRuns, updateDowntimeEvent, type RunOption } from "../api";
import { fromLocalInput, isPlanned, LINKABLE_ORDER_STATUSES, LOSS_CATEGORIES, nowLocalInput, PLANNED_CATEGORIES, toLocalInput } from "../downtime-rules";
import type { DowntimeCategory, DowntimeEvent } from "../types";
import { downtimeErrorMessage } from "./downtime-errors";
import { P } from "@/lib/production-permissions";
import { OptionalDateInput } from "@/components/forms/OptionalDateInput";

type Values = { center: string; order: string; run: string; start: string; end: string; category: DowntimeCategory; reason: string; notes: string };

// Records a stop on a machine (open until closed, or with its end), or edits one (eventId).
function useDowntimeEventEditor({eventId,orderId}:{eventId?:string;orderId?:string}){
  const t = useTranslations("production.downtimeEvents");
  const categories = useTranslations("enums.downtimeEvent.category");
  const hints = useTranslations("production.downtimeEvents.categoryHints");
  const fmt = useFormatter();
  const params = useSearchParams();
  const canReadRuns = usePermission(P.RUNS_READ);
  const editing = Boolean(eventId);
  const [values, setValues] = useState<Values>({ center: params.get("work_center") ?? "", order: orderId ?? params.get("order") ?? "", run: "", start: nowLocalInput(), end: "",
    category: "breakdown", reason: "", notes: "" });
  const [existing, setExisting] = useState<DowntimeEvent | null>(null);
  const [runs, setRuns] = useState<RunOption[]>([]);
  const [centers, setCenters] = useState<{ id: string; code: string; name: string }[]>([]);
  const [loading, setLoading] = useState(editing);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getWorkCenters().then(setCenters).catch(() => setCenters([]));
  }, []);
  useEffect(() => {
    if (!eventId) return;
    let active = true;
    getDowntimeEventById(eventId).then(e => {
      if (!active) return;
      setExisting(e);
      setValues({ center: e.work_center_id, order: e.production_order_id ?? "", run: e.production_run_id ?? "", start: toLocalInput(e.start_time), end: toLocalInput(e.end_time),
        category: e.category, reason: e.reason_code ?? "", notes: e.notes ?? "" });
    }).catch(e => { if (active) setError(downtimeErrorMessage(e, t)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [eventId, t]);
  useEffect(() => {
    if (!values.order || !canReadRuns) { setRuns([]); return; }
    let active = true;
    getOrderRuns(values.order).then(list => { if (active) setRuns(list.filter(r => r.status !== "cancelled")); }).catch(() => { if (active) setRuns([]); });
    return () => { active = false; };
  }, [values.order, canReadRuns]);

  const run = useMemo(() => runs.find(r => r.id === values.run) ?? null, [runs, values.run]);
  const locked = Boolean(existing && !existing.labels?.actions.includes("edit"));
  const center = run ? run.work_center_id : values.center;
  const endBeforeStart = Boolean(values.end && values.start && values.end <= values.start);
  const valid = Boolean(center && values.start && !endBeforeStart);
  const set = <K extends keyof Values>(field: K, value: Values[K]) => setValues(old => ({ ...old, [field]: value, ...(field === "order" ? { run: "" } : {}) }));

  async function save() {
    if (!valid || busy || locked) return null;
    setBusy(true); setError("");
    const body = {
      // A run carries the machine and the order; otherwise both come from the form.
      work_center_id: run ? null : values.center, production_order_id: run ? null : values.order || null, production_run_id: values.run || null,
      start_time: fromLocalInput(values.start)!, end_time: fromLocalInput(values.end), category: values.category,
      reason_code: values.reason.trim() || null, notes: values.notes.trim() || null,
    };
    try {
      const saved = eventId ? await updateDowntimeEvent(eventId, body) : await createDowntimeEvent(body);
      setBusy(false);return saved;
    } catch (e) { setError(downtimeErrorMessage(e, t)); setBusy(false); return null; }
  }

  const back = eventId ? `/downtime-events/${eventId}` : "/downtime-events";
  return {t,categories,hints,busy,locked,values,set,canReadRuns,runs,fmt,centers,center,run,endBeforeStart,orderId,eventId,existing,loading,error,valid,save,back,editing};
}
export function DowntimeEventForm({eventId,orderId,onSaved,onClose}:{eventId?:string;orderId?:string;onSaved?:(record:DowntimeEvent)=>void;onClose?:()=>void}){
  const editor=useDowntimeEventEditor({eventId,orderId}),router=useRouter();
  const {t,editing,back,loading,busy,locked,valid,error}=editor;
  return <EditorSurface title={editing?t("editTitle"):t("createTitle")} subtitle={t("createSubtitle")}
    back={back} backLabel={t("actions.back")} cancelLabel={t("actions.cancel")} saveLabel={editing?t("actions.save"):t("actions.record")}
    loading={loading} busy={busy} disabled={!valid||locked} error={error} onClose={onClose}
    onSave={async()=>{const saved=await editor.save();if(!saved)return false;if(onSaved)onSaved(saved);else router.push(`/downtime-events/${saved.id}`);return true;}}>
    <DowntimeEventFields editor={editor}/>
  </EditorSurface>;
}
export function DowntimeEventFields({editor}:{editor:ReturnType<typeof useDowntimeEventEditor>}){
  const {t,categories,hints,busy,locked,values,set,canReadRuns,runs,fmt,centers,center,run,endBeforeStart,orderId}=editor;
  return <>      {locked && <p role="status" className={s.error}>{t("hints.locked")}</p>}
      <div className={s.grid}>
        <label className={s.field}>{t("fields.category")}
          <select required value={values.category} disabled={busy || locked} onChange={e => set("category", e.target.value as DowntimeCategory)}>
            <optgroup label={t("types.loss")}>{LOSS_CATEGORIES.map(c => <option key={c} value={c}>{categories(c)}</option>)}</optgroup>
            <optgroup label={t("types.planned")}>{PLANNED_CATEGORIES.map(c => <option key={c} value={c}>{categories(c)}</option>)}</optgroup>
          </select>
        </label>
        <label className={s.field}>{t("fields.orderOptional")}
          {/* Searched on the server among the orders a stop can be linked to; an order chosen earlier stays shown. */}
          <ProductionOrderPicker value={values.order} onChange={id => set("order", id)} statuses={LINKABLE_ORDER_STATUSES} disabled={busy || locked || Boolean(orderId)}
            emptyLabel={t("placeholders.noOrder")} ariaLabel={t("fields.orderOptional")} />
        </label>
        {canReadRuns && <label className={s.field}>{t("fields.runOptional")}
          <RecordCombobox aria-label={t("fields.runOptional")} value={values.run} disabled={busy || locked || !values.order} onChange={e => set("run", e)}>
            <option value="">{runs.length ? t("placeholders.noRun") : t("placeholders.noRuns")}</option>
            {runs.map(r => <option key={r.id} value={r.id}>{t("runOption", { date: fmt.date(r.run_date), center: centers.find(c => c.id === r.work_center_id)?.name ?? "—" })}</option>)}
          </RecordCombobox>
        </label>}
        <label className={s.field}>{t("fields.workCenter")}
          <RecordCombobox aria-label={t("fields.workCenter")} required value={center} disabled={busy || locked || Boolean(run)} onChange={e => set("center", e)}>
            <option value="">{t("placeholders.selectWorkCenter")}</option>
            {centers.map(c => <option key={c.id} value={c.id}>{c.code} — {c.name}</option>)}
          </RecordCombobox>
        </label>
        <label className={s.field}>{t("fields.startTime")}<input type="datetime-local" required value={values.start} disabled={busy || locked} onChange={e => set("start", e.target.value)} /></label>
        <div className={s.field} role="group" aria-label={t("fields.endTimeOptional")}><span>{t("fields.endTimeOptional")}</span><OptionalDateInput type="datetime-local" label={t("fields.endTimeOptional")} value={values.end} min={values.start || undefined} disabled={busy || locked} onChange={v => set("end", v)} /></div>
        <label className={s.field}>{t("fields.reasonCode")}<ReferenceTextSelect list="downtime_reason" value={values.reason} disabled={busy || locked} onChange={v => set("reason", v)} /></label>
      </div>
      <p className={s.muted}>{hints(values.category)} {isPlanned(values.category) ? t("hints.plannedType") : t("hints.lossType")}</p>
      {!values.end && <p className={s.muted}>{t("hints.openStop")}</p>}
      {endBeforeStart && <p role="status" className={s.error}>{t("errors.END_BEFORE_START")}</p>}
      {run && <p className={s.muted}>{t("hints.runWorkCenter")}</p>}
      <label className={s.field}>{t("fields.notes")}<textarea maxLength={2000} value={values.notes} disabled={busy || locked} onChange={e => set("notes", e.target.value)} /></label>
</>;
}
