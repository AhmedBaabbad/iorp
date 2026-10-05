"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState, type FormEvent } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import s from "@/features/production-demands/demands.module.css";
import { useFormatter } from "@/hooks/useFormatter";
import { createQualityCheck, getInspectableOrders, getInspectableSamples, getQualityCheckById, updateQualityCheck } from "../api/quality-checks-api";
import { CHECK_TYPES, ORDER_CHECK_TYPES, type InspectableOrder, type QualityCheckData, type QualityCheckType, type SampleOption } from "../types";
import { localDateTime, QUANTITY, qualityErrorMessage } from "./quality-errors";

type Values = { type: QualityCheckType; order: string; item: string; sample: string; datetime: string; quantity: string; notes: string };

// Opens an inspection of a production lot (order and line) or of a commercial sample; or edits one still open (checkId).
export function QualityCheckForm({ checkId }: { checkId?: string }) {
  const t = useTranslations("quality.qualityChecks");
  const errors = useTranslations("quality.errors");
  const types = useTranslations("enums.qualityCheck.checkType");
  const orderStatus = useTranslations("enums.productionOrder.status");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const router = useRouter();
  const params = useSearchParams();
  const editing = Boolean(checkId);
  const [values, setValues] = useState<Values>({ type: "in_process_inspection", order: params.get("order") ?? "", item: "", sample: "",
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
    getInspectableOrders("", reinspection ? "reinspection" : undefined).then(setOrders).catch(() => setOrders([]));
  }, [reinspection]);
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
  const allowedTypes = !existing ? CHECK_TYPES
    : existing.sample_id ? ["sample_inspection" as const]
    : existing.production_order_id ? CHECK_TYPES.filter(v => v !== "sample_inspection")
    : CHECK_TYPES.filter(v => !ORDER_CHECK_TYPES.includes(v));
  const locked = Boolean(existing && !existing.actions.includes("edit"));
  const quantityOk = values.quantity === "" || QUANTITY.test(values.quantity);
  const valid = Boolean(values.datetime && quantityOk && (isSample ? values.sample : !orderRequired || values.order));
  const set = <K extends keyof Values>(field: K, value: Values[K]) => setValues(old => ({ ...old, [field]: value, ...(field === "order" ? { item: "" } : {}) }));

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid || busy || locked) return;
    setBusy(true); setError("");
    const common = {
      check_type: values.type, check_datetime: new Date(values.datetime).toISOString(),
      production_order_item_id: isSample ? null : values.item || null, sample_id: isSample ? values.sample : null,
      qty_inspected: values.quantity || "0", notes: values.notes.trim() || null,
    };
    try {
      const saved = checkId ? await updateQualityCheck(checkId, common)
        : await createQualityCheck({ ...common, production_order_id: isSample ? null : values.order || null });
      router.push(`/quality-checks/${saved.id}`);
    } catch (e) { setError(qualityErrorMessage(e, errors)); setBusy(false); }
  }

  const back = checkId ? `/quality-checks/${checkId}` : values.order ? `/quality-checks?order=${values.order}` : "/quality-checks";
  const unit = isSample ? samples.find(x => x.id === values.sample)?.unit : line?.unit ?? order?.unit;
  return <PageFrame title={editing ? t("editTitle") : t("createTitle")} subtitle={editing ? existing?.inspection_code : t("createSubtitle")}
    action={<Link href={back} className={s.button}>{t("actions.back")}</Link>}>
    {loading ? <p className={s.muted}>{messages("loading.default")}</p> : <form className={s.panel} onSubmit={submit} aria-label={editing ? t("editTitle") : t("createTitle")}>
      {locked && <p role="status" className={s.error}>{t("hints.locked")}</p>}
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
          <select required value={values.sample} disabled={busy || locked} onChange={e => set("sample", e.target.value)}>
            <option value="">{samples.length ? t("placeholders.selectSample") : t("placeholders.noSamples")}</option>
            {samples.map(x => <option key={x.id} value={x.id}>{x.code} — {x.customer} — {x.product_type}</option>)}
          </select>
        </label> : <>
          <label className={s.field}>{orderRequired ? t("fields.productionOrder") : t("fields.productionOrderOptional")}
            {editing ? <input readOnly value={existing?.order_number ?? "—"} />
              : <select required={orderRequired} value={values.order} disabled={busy} onChange={e => set("order", e.target.value)}>
                <option value="">{orders.length ? t("placeholders.selectOrder") : t("placeholders.noOrders")}</option>
                {orders.map(o => <option key={o.id} value={o.id}>{o.number} — {o.product_type} ({orderStatus(o.status)})</option>)}
              </select>}
          </label>
          {(order?.items.length ?? 0) > 0 && <label className={s.field}>{t("fields.lineOptional")}
            <select value={values.item} disabled={busy || locked} onChange={e => set("item", e.target.value)}>
              <option value="">{t("placeholders.wholeOrder")}</option>
              {order!.items.map(l => <option key={l.id} value={l.id}>{t("lineOption", { no: String(l.line_no), quantity: fmt.quantity(l.planned_quantity, l.unit) })}</option>)}
            </select>
          </label>}
        </>}
        <label className={s.field}>{unit ? t("fields.qtyInspectedUnit", { unit }) : t("fields.qtyInspected")}
          <input type="number" min="0" step="0.001" inputMode="decimal" value={values.quantity} disabled={busy || locked} onChange={e => set("quantity", e.target.value)} />
        </label>
      </div>
      <p className={s.muted}>{isSample ? t("hints.sample") : reinspection ? t("hints.reinspection") : orderRequired ? t("hints.orderStatuses") : t("hints.optionalOrder")} {t("hints.quantityLater")}</p>
      <label className={s.field}>{t("fields.notes")}<textarea maxLength={2000} value={values.notes} disabled={busy || locked} onChange={e => set("notes", e.target.value)} /></label>
      {error && <p role="alert" className={s.error}>{error}</p>}
      <div className={s.actions} style={{ marginTop: 16 }}>
        <button type="submit" className={`${s.button} ${s.primary}`} disabled={!valid || busy || locked}>{editing ? t("actions.save") : t("createButton")}</button>
        <Link href={back} className={s.button}>{t("actions.cancel")}</Link>
      </div>
    </form>}
  </PageFrame>;
}
