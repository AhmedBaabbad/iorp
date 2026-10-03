"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState, type FormEvent } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import s from "@/features/production-demands/demands.module.css";
import { getInspectableOrders, getQualityCheckById } from "@/features/quality-checks/api/quality-checks-api";
import { QUANTITY, qualityErrorMessage, todayIso } from "@/features/quality-checks/components/quality-errors";
import type { InspectableOrder, QualityCheckData } from "@/features/quality-checks/types";
import { useFormatter } from "@/hooks/useFormatter";
import { createQualityRejection, getQualityRejectionById, updateQualityRejection } from "../api/quality-rejections-api";
import { REJECTION_REASONS, type QualityRejectionData, type RejectionReason } from "../types";

type Values = { order: string; item: string; date: string; reason: RejectionReason; quantity: string; notes: string };

// A rejection not opened by closing a check: more of a closed check's rejected lot (?check=) or a running order's;
// or edits one still awaiting its decision (rejectionId).
export function QualityRejectionForm({ rejectionId }: { rejectionId?: string }) {
  const t = useTranslations("quality.qualityRejections");
  const errors = useTranslations("quality.errors");
  const reasons = useTranslations("enums.qualityRejection.rejectionReason");
  const orderStatus = useTranslations("enums.productionOrder.status");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const router = useRouter();
  const params = useSearchParams();
  const checkId = params.get("check") ?? "";
  const editing = Boolean(rejectionId);
  const [values, setValues] = useState<Values>({ order: params.get("order") ?? "", item: "", date: todayIso(), reason: "failed_quality_check", quantity: "", notes: "" });
  const [existing, setExisting] = useState<QualityRejectionData | null>(null);
  const [check, setCheck] = useState<QualityCheckData | null>(null);
  const [orders, setOrders] = useState<InspectableOrder[]>([]);
  const [loading, setLoading] = useState(editing || Boolean(checkId));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!editing && !checkId) getInspectableOrders().then(setOrders).catch(() => setOrders([]));
  }, [editing, checkId]);
  useEffect(() => {
    if (!rejectionId && !checkId) return;
    let active = true;
    const request = rejectionId
      ? getQualityRejectionById(rejectionId).then(r => {
        if (!active) return;
        setExisting(r);
        setValues({ order: r.production_order_id ?? "", item: r.production_order_item_id ?? "", date: r.rejection_date, reason: r.rejection_reason,
          quantity: r.quantity_rejected, notes: r.rejection_notes });
      })
      : getQualityCheckById(checkId).then(c => { if (active) { setCheck(c); setValues(old => ({ ...old, notes: c.notes ?? "" })); } });
    request.catch(e => { if (active) setError(qualityErrorMessage(e, errors)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [rejectionId, checkId, errors]);

  const order = useMemo(() => orders.find(o => o.id === values.order) ?? null, [orders, values.order]);
  const unit = existing?.unit ?? check?.unit ?? order?.items.find(i => i.id === values.item)?.unit ?? order?.unit ?? "";
  const locked = Boolean(existing && !existing.actions.includes("edit"));
  const valid = Boolean((editing || checkId || values.order) && values.date && values.notes.trim() && QUANTITY.test(values.quantity) && Number(values.quantity) > 0);
  const set = <K extends keyof Values>(field: K, value: Values[K]) => setValues(old => ({ ...old, [field]: value, ...(field === "order" ? { item: "" } : {}) }));

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid || busy || locked) return;
    setBusy(true); setError("");
    const body = { rejection_date: values.date, rejection_reason: values.reason, quantity_rejected: values.quantity, rejection_notes: values.notes.trim() };
    try {
      const saved = rejectionId ? await updateQualityRejection(rejectionId, body)
        : await createQualityRejection({ ...body, ...(checkId ? { quality_check_id: checkId }
          : { production_order_id: values.order, production_order_item_id: values.item || null }) });
      router.push(`/quality-rejections/${saved.id}`);
    } catch (e) { setError(qualityErrorMessage(e, errors)); setBusy(false); }
  }

  const back = rejectionId ? `/quality-rejections/${rejectionId}` : checkId ? `/quality-checks/${checkId}` : "/quality-rejections";
  const source = existing ? (existing.inspection_code ?? existing.order_number ?? "—") : check?.inspection_code;
  return <PageFrame title={editing ? t("editTitle") : t("createTitle")} subtitle={editing ? existing?.rejection_code : t("createSubtitle")}
    action={<Link href={back} className={s.button}>{t("actions.back")}</Link>}>
    {loading ? <p className={s.muted}>{messages("loading.default")}</p> : <form className={s.panel} onSubmit={submit} aria-label={editing ? t("editTitle") : t("createTitle")}>
      {locked && <p role="status" className={s.error}>{t("hints.locked")}</p>}
      <div className={s.grid}>
        {source ? <label className={s.field}>{t("fields.source")}<input readOnly value={source} /></label> : <>
          <label className={s.field}>{t("fields.productionOrder")}
            <select required value={values.order} disabled={busy} onChange={e => set("order", e.target.value)}>
              <option value="">{orders.length ? t("placeholders.selectOrder") : t("placeholders.noOrders")}</option>
              {orders.map(o => <option key={o.id} value={o.id}>{o.number} — {o.product_type} ({orderStatus(o.status)})</option>)}
            </select>
          </label>
          {(order?.items.length ?? 0) > 0 && <label className={s.field}>{t("fields.lineOptional")}
            <select value={values.item} disabled={busy} onChange={e => set("item", e.target.value)}>
              <option value="">{t("placeholders.wholeOrder")}</option>
              {order!.items.map(l => <option key={l.id} value={l.id}>{t("lineOption", { no: String(l.line_no), quantity: fmt.quantity(l.planned_quantity, l.unit) })}</option>)}
            </select>
          </label>}
        </>}
        <label className={s.field}>{t("fields.rejectionDate")}<input type="date" required value={values.date} disabled={busy || locked} onChange={e => set("date", e.target.value)} /></label>
        <label className={s.field}>{t("fields.rejectionReason")}
          <select required value={values.reason} disabled={busy || locked} onChange={e => set("reason", e.target.value as RejectionReason)}>
            {REJECTION_REASONS.map(v => <option key={v} value={v}>{reasons(v)}</option>)}
          </select>
        </label>
        <label className={s.field}>{unit ? t("fields.quantityRejectedUnit", { unit }) : t("fields.quantityRejected")}
          <input type="number" required min="0.001" step="0.001" inputMode="decimal" value={values.quantity} disabled={busy || locked} onChange={e => set("quantity", e.target.value)} />
        </label>
      </div>
      {check && <p className={s.muted}>{t("hints.fromCheck", { quantity: fmt.quantity(check.qty_rejected, check.unit ?? "") })}</p>}
      {!check && !editing && <p className={s.muted}>{t("hints.manual")}</p>}
      <label className={s.field}>{t("fields.rejectionNotes")}
        <textarea required maxLength={2000} value={values.notes} placeholder={t("placeholders.rejectionNotes")} disabled={busy || locked} onChange={e => set("notes", e.target.value)} />
      </label>
      {error && <p role="alert" className={s.error}>{error}</p>}
      <div className={s.actions} style={{ marginTop: 16 }}>
        <button type="submit" className={`${s.button} ${s.primary}`} disabled={!valid || busy || locked}>{editing ? t("actions.save") : t("createButton")}</button>
        <Link href={back} className={s.button}>{t("actions.cancel")}</Link>
      </div>
    </form>}
  </PageFrame>;
}
