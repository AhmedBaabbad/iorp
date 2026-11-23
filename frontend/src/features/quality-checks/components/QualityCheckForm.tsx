"use client";
import {RecordCombobox} from "@/components/ui/RecordCombobox";

import {EditorSurface} from "@/components/forms/EditorSurface";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";


import s from "@/features/production-demands/demands.module.css";
import { useFormatter } from "@/hooks/useFormatter";
import { createQualityCheck, getInspectableOrders, getInspectableSamples, getQualityCheckById, updateQualityCheck } from "../api/quality-checks-api";
import { CHECK_TYPES, ORDER_CHECK_TYPES, type InspectableOrder, type QualityCheckData, type QualityCheckType, type SampleOption } from "../types";
import { localDateTime, QUANTITY, qualityErrorMessage } from "./quality-errors";

type Values = { type: QualityCheckType; order: string; item: string; sample: string; datetime: string; quantity: string; notes: string };

// Opens an inspection of a production lot (order and line) or of a commercial sample; or edits one still open (checkId).
function useQualityCheckEditor({checkId,orderId,orderNumber}:{checkId?:string;orderId?:string;orderNumber?:string}){
  const t = useTranslations("quality.qualityChecks");
  const errors = useTranslations("quality.errors");
  const types = useTranslations("enums.qualityCheck.checkType");
  const orderStatus = useTranslations("enums.productionOrder.status");
  const fmt = useFormatter();
  const params = useSearchParams();
  const editing = Boolean(checkId);
  const [values, setValues] = useState<Values>({ type: "in_process_inspection", order: orderId ?? params.get("order") ?? "", item: "", sample: "",
    datetime: localDateTime(), quantity: "", notes: "" });
  const [existing, setExisting] = useState<QualityCheckData | null>(null);
  const [orders, setOrders] = useState<InspectableOrder[]>([]);
  const [samples, setSamples] = useState<SampleOption[]>([]);
  const [loading, setLoading] = useState(editing);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // A reinspection may also be made on a closed order (its retained samples), so it lists those too.
  const reinspection = values.type === "reinspection";
  useEffect(() => {
    getInspectableOrders(orderNumber??"", reinspection ? "reinspection" : undefined).then(setOrders).catch(() => setOrders([]));
  }, [reinspection,orderNumber]);
  useEffect(() => {
    if (values.type !== "sample_inspection" || samples.length) return;
    getInspectableSamples().then(setSamples).catch(() => setSamples([]));
  }, [values.type, samples.length]);
  useEffect(() => {
    if (!checkId) return;
    let active = true;
    getQualityCheckById(checkId).then(c => {
      if (!active) return;
      setExisting(c);
      setValues({ type: c.check_type, order: c.production_order_id ?? "", item: c.production_order_item_id ?? "", sample: c.sample_id ?? "",
        datetime: localDateTime(c.check_datetime), quantity: c.qty_inspected, notes: c.notes ?? "" });
    }).catch(e => { if (active) setError(qualityErrorMessage(e, errors)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [checkId, errors]);

  const isSample = values.type === "sample_inspection";
  const orderRequired = ORDER_CHECK_TYPES.includes(values.type);
  const order = useMemo(() => orders.find(o => o.id === values.order) ?? null, [orders, values.order]);
  const line = order?.items.find(i => i.id === values.item) ?? null;
  // The order is fixed once the check exists, so editing only offers types that fit what it inspects.
  const allowedTypes = !existing ? (orderId ? CHECK_TYPES.filter(v=>v!=="sample_inspection") : CHECK_TYPES)
    : existing.sample_id ? ["sample_inspection" as const]
    : existing.production_order_id ? CHECK_TYPES.filter(v => v !== "sample_inspection")
    : CHECK_TYPES.filter(v => !ORDER_CHECK_TYPES.includes(v));
  const locked = Boolean(existing && !existing.actions.includes("edit"));
  const quantityOk = values.quantity === "" || QUANTITY.test(values.quantity);
  const valid = Boolean(values.datetime && quantityOk && (isSample ? values.sample : !orderRequired || values.order));
  const set = <K extends keyof Values>(field: K, value: Values[K]) => setValues(old => ({ ...old, [field]: value, ...(field === "order" ? { item: "" } : {}) }));

  async function save() {
    if (!valid || busy || locked) return null;
    setBusy(true); setError("");
    const common = {
      check_type: values.type, check_datetime: new Date(values.datetime).toISOString(),
      production_order_item_id: isSample ? null : values.item || null, sample_id: isSample ? values.sample : null,
      qty_inspected: values.quantity || "0", notes: values.notes.trim() || null,
    };
    try {
      const saved = checkId ? await updateQualityCheck(checkId, common)
        : await createQualityCheck({ ...common, production_order_id: isSample ? null : values.order || null });
      setBusy(false);return saved;
    } catch (e) { setError(qualityErrorMessage(e, errors)); setBusy(false); return null; }
  }

  const back = checkId ? `/quality-checks/${checkId}` : values.order ? `/quality-checks?order=${values.order}` : "/quality-checks";
  const unit = isSample ? samples.find(x => x.id === values.sample)?.unit : line?.unit ?? order?.unit;
  return {t,types,orderStatus,busy,locked,values,set,allowedTypes,isSample,samples,editing,existing,orderRequired,orders,order,fmt,unit,orderId,reinspection,checkId,loading,error,valid,save,back};
}
export function QualityCheckForm({checkId,orderId,orderNumber,onSaved,onClose}:{checkId?:string;orderId?:string;orderNumber?:string;onSaved?:(record:QualityCheckData)=>void;onClose?:()=>void}){
  const editor=useQualityCheckEditor({checkId,orderId,orderNumber}),router=useRouter();
  const {t,editing,existing,back,loading,busy,locked,valid,error}=editor;
  return <EditorSurface title={editing?t("editTitle"):t("createTitle")} subtitle={editing?existing?.inspection_code:t("createSubtitle")}
    back={back} backLabel={t("actions.back")} cancelLabel={t("actions.cancel")} saveLabel={editing?t("actions.save"):t("createButton")}
    loading={loading} busy={busy} disabled={!valid||locked} error={error} onClose={onClose}
    onSave={async()=>{const saved=await editor.save();if(!saved)return false;if(onSaved)onSaved(saved);else router.push(`/quality-checks/${saved.id}`);return true;}}>
    <QualityCheckFields editor={editor}/>
  </EditorSurface>;
}
export function QualityCheckFields({editor}:{editor:ReturnType<typeof useQualityCheckEditor>}){
  const {t,types,orderStatus,busy,locked,values,set,allowedTypes,isSample,samples,editing,existing,orderRequired,orders,order,fmt,unit,orderId,reinspection}=editor;
  return <>      {locked && <p role="status" className={s.error}>{t("hints.locked")}</p>}
      <div className={s.grid}>
        <label className={s.field}>{t("fields.checkType")}
          <select required value={values.type} disabled={busy || locked || allowedTypes.length === 1} onChange={e => set("type", e.target.value as QualityCheckType)}>
            {allowedTypes.map(v => <option key={v} value={v}>{types(v)}</option>)}
          </select>
        </label>
        <label className={s.field}>{t("fields.checkDate")}
          <input type="datetime-local" required value={values.datetime} disabled={busy || locked} onChange={e => set("datetime", e.target.value)} />
        </label>
        {isSample ? <label className={s.field}>{t("fields.sample")}
          <RecordCombobox aria-label={t("fields.sample")} required value={values.sample} disabled={busy || locked} onChange={e => set("sample", e)}>
            <option value="">{samples.length ? t("placeholders.selectSample") : t("placeholders.noSamples")}</option>
            {samples.map(x => <option key={x.id} value={x.id}>{x.code} — {x.customer} — {x.product_type}</option>)}
          </RecordCombobox>
        </label> : <>
          <label className={s.field}>{orderRequired ? t("fields.productionOrder") : t("fields.productionOrderOptional")}
            {editing ? <input readOnly value={existing?.order_number ?? "—"} />
              : <RecordCombobox aria-label={orderRequired ? t("fields.productionOrder") : t("fields.productionOrderOptional")} required={orderRequired} value={values.order} disabled={busy || Boolean(orderId)} onChange={e => set("order", e)}>
                <option value="">{orders.length ? t("placeholders.selectOrder") : t("placeholders.noOrders")}</option>
                {orders.map(o => <option key={o.id} value={o.id}>{o.number} — {o.product_type} ({orderStatus(o.status)})</option>)}
              </RecordCombobox>}
          </label>
          {(order?.items.length ?? 0) > 0 && <label className={s.field}>{t("fields.lineOptional")}
            <RecordCombobox aria-label={t("fields.lineOptional")} value={values.item} disabled={busy || locked} onChange={e => set("item", e)}>
              <option value="">{t("placeholders.wholeOrder")}</option>
              {order!.items.map(l => <option key={l.id} value={l.id}>{t("lineOption", { no: String(l.line_no), quantity: fmt.quantity(l.planned_quantity, l.unit) })}</option>)}
            </RecordCombobox>
          </label>}
        </>}
        <label className={s.field}>{unit ? t("fields.qtyInspectedUnit", { unit }) : t("fields.qtyInspected")}
          <input type="number" min="0" step="0.001" inputMode="decimal" value={values.quantity} disabled={busy || locked} onChange={e => set("quantity", e.target.value)} />
        </label>
      </div>
      <p className={s.muted}>{isSample ? t("hints.sample") : reinspection ? t("hints.reinspection") : orderRequired ? t("hints.orderStatuses") : t("hints.optionalOrder")} {t("hints.quantityLater")}</p>
      <label className={s.field}>{t("fields.notes")}<textarea maxLength={2000} value={values.notes} disabled={busy || locked} onChange={e => set("notes", e.target.value)} /></label>
</>;
}
