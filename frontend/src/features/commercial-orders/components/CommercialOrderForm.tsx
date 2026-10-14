"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState, type FormEvent } from "react";

import { PageFrame } from "@/components/layout/page-frame";
import { SpecEditor } from "@/components/forms/SpecEditor";
import { UnitSelect } from "@/components/forms/UnitSelect";
import { Money } from "@/components/money/Money";
import { CustomerPicker, customersByIds } from "@/features/customers";
import { ProductSelect, useBusinessSettings, useProducts } from "@/features/masterdata";
import { getQuoteById, listQuotesForCustomer } from "@/features/quotes";
import s from "@/features/production-demands/demands.module.css";
import { toDatetimeLocalValue } from "@/lib/utils";
import { createCommercialOrder, updateCommercialOrder } from "../api/commercial-orders-api";
import type { CommercialOrderData, CreateCommercialOrderItemRequest } from "../types";
import { salesErrorMessage } from "./sales-lifecycle";

type Line = { product_type: string; quantity: string; unit: string; unit_price: string; spec: string };
type Values = {
  customer_id: string;
  source: "quote" | "direct";
  quote_id: string;
  customer_reference: string;
  currency: "SAR" | "USD";
  order_date: string;
  requested_delivery_date: string;
  notes: string;
  lines: Line[];
};
type QuoteOption = { id: string; quote_number: string; status: string };

const emptyLine = (): Line => ({ product_type: "", quantity: "", unit: "", unit_price: "", spec: "" });
const specString = (spec: Record<string, unknown> | null | undefined) => (spec && Object.keys(spec).length ? JSON.stringify(spec) : "");

function fromOrder(order: CommercialOrderData): Values {
  return {
    customer_id: order.customer_id,
    source: order.quote_id ? "quote" : "direct",
    quote_id: order.quote_id ?? "",
    customer_reference: order.customer_reference ?? "",
    currency: order.currency === "USD" ? "USD" : "SAR",
    order_date: toDatetimeLocalValue(new Date(order.order_date)),
    requested_delivery_date: order.requested_delivery_date ? toDatetimeLocalValue(new Date(order.requested_delivery_date)) : "",
    notes: order.notes ?? "",
    lines: [...order.items].sort((a, b) => a.line_no - b.line_no).map((i) => ({
      product_type: i.product_type, quantity: String(Number(i.quantity)), unit: i.unit,
      unit_price: i.agreed_unit_price != null ? String(Number(i.agreed_unit_price)) : "", spec: specString(i.requested_spec_json),
    })),
  };
}

/**
 * The internal sales order (أمر البيع الداخلي, SALES-001): the customer's request with its products, quantities and
 * specifications. From an accepted quotation (its lines are copied, then the two are independent) or a direct order with
 * the customer's own reference. Prices are optional; editing is for drafts only — confirming locks the order.
 */
export function CommercialOrderForm({ order }: { order?: CommercialOrderData }) {
  const router = useRouter();
  const t = useTranslations("commercial.commercialOrders");
  const errors = useTranslations("commercial.salesErrors");
  const messages = useTranslations("messages");
  const common = useTranslations("common");
  const currencies = useTranslations("common.currencies");
  const settings = useBusinessSettings();
  const products = useProducts();
  const editing = Boolean(order);
  const [values, setValues] = useState<Values>(() => order ? fromOrder(order) : {
    customer_id: "", source: "quote", quote_id: "", customer_reference: "", currency: "SAR",
    order_date: toDatetimeLocalValue(new Date()), requested_delivery_date: "", notes: "", lines: [emptyLine()],
  });
  const [customerName, setCustomerName] = useState("");
  const [quotes, setQuotes] = useState<QuoteOption[]>([]);
  const [busy, setBusy] = useState(false);
  const [loadingQuote, setLoadingQuote] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!editing && settings.loaded) setValues((v) => (v.quote_id ? v : { ...v, currency: settings.currency }));
  }, [editing, settings.loaded, settings.currency]);

  useEffect(() => {
    // Editing: the order's customer is fixed and shown by name (the customer is chosen with a search when creating).
    if (!order) return;
    let active = true;
    customersByIds([order.customer_id]).then((rows) => { if (active && rows[0]) setCustomerName(`${rows[0].name} (${rows[0].customer_code})`); })
      .catch(() => undefined);
    return () => { active = false; };
  }, [order]);

  useEffect(() => {
    let active = true;
    if (!values.customer_id) { setQuotes([]); return; }
    listQuotesForCustomer(values.customer_id)
      .then((rows) => active && setQuotes(rows.filter((q) => q.status === "accepted" || q.id === order?.quote_id)))
      .catch(() => active && setQuotes([]));
    return () => { active = false; };
  }, [values.customer_id, order?.quote_id]);

  const set = <K extends keyof Values>(key: K, value: Values[K]) => setValues((v) => ({ ...v, [key]: value }));
  const setLine = (index: number, patch: Partial<Line>) =>
    setValues((v) => ({ ...v, lines: v.lines.map((l, i) => (i === index ? { ...l, ...patch } : l)) }));

  function chooseProduct(index: number, key: string) {
    const unit = products?.find((p) => p.key === key)?.default_unit;
    setValues((v) => ({ ...v, lines: v.lines.map((l, i) => (i === index ? { ...l, product_type: key, spec: "", unit: l.unit || unit || "" } : l)) }));
  }

  async function chooseQuote(quoteId: string) {
    set("quote_id", quoteId);
    if (!quoteId) return;
    setLoadingQuote(true); setError("");
    try {
      const q = await getQuoteById(quoteId);
      setValues((v) => ({
        ...v, quote_id: q.id, currency: q.currency === "USD" ? "USD" : "SAR",
        lines: [...q.items].sort((a, b) => a.line_no - b.line_no).map((i) => ({
          product_type: i.product_type, quantity: String(Number(i.quantity)), unit: i.unit,
          unit_price: String(Number(i.unit_price)), spec: specString(i.requested_spec_json),
        })),
      }));
    } catch (e) { setError(salesErrorMessage(e, errors, messages)); } finally { setLoadingQuote(false); }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (values.source === "quote" && !values.quote_id) { setError(errors("ORDER_QUOTE_REQUIRED")); return; }
    if (values.source === "direct" && !values.customer_reference.trim()) { setError(errors("ORDER_SOURCE_REQUIRED")); return; }
    const items: CreateCommercialOrderItemRequest[] = values.lines.map((l, index) => ({
      line_no: index + 1, product_type: l.product_type, quantity: Number(l.quantity), unit: l.unit,
      requested_spec_json: l.spec ? (JSON.parse(l.spec) as Record<string, unknown>) : null,
      agreed_unit_price: l.unit_price.trim() === "" ? null : Number(l.unit_price),
    }));
    const body = {
      quote_id: values.source === "quote" ? values.quote_id : null,
      customer_reference: values.customer_reference.trim() || null,
      currency: values.currency,
      order_date: new Date(values.order_date).toISOString(),
      requested_delivery_date: values.requested_delivery_date ? new Date(values.requested_delivery_date).toISOString() : null,
      notes: values.notes.trim() || null,
      items,
    };
    setBusy(true);
    try {
      const saved = order ? await updateCommercialOrder(order.id, body) : await createCommercialOrder({ customer_id: values.customer_id, ...body });
      router.push(`/commercial-orders/${saved.id}`);
    } catch (e) { setError(salesErrorMessage(e, errors, messages)); setBusy(false); }
  }

  const priced = values.lines.some((l) => l.unit_price.trim() !== "");
  const total = values.lines.reduce((sum, l) => sum + Number(l.quantity || 0) * Number(l.unit_price || 0), 0);
  const back = order ? `/commercial-orders/${order.id}` : "/commercial-orders";

  return (
    <PageFrame title={editing ? `${t("editTitle")} — ${order!.order_number}` : t("createTitle")} subtitle={t("createSubtitle")}
      action={<Link href={back} className={s.button}>{editing ? t("backToDetail") : t("backToList")}</Link>}>
      <form onSubmit={submit}>
        <section className={s.panel} aria-label={t("sections.header")}>
          <h2 style={{ marginTop: 0 }}>{t("sections.header")}</h2>
          <div className={s.grid}>
            <label className={s.field}>{t("fields.customer")} *
              {editing ? <input value={customerName} disabled readOnly /> : (
                <CustomerPicker value={values.customer_id} disabled={busy} ariaLabel={t("fields.customer")}
                  onChange={(id) => setValues((v) => ({ ...v, customer_id: id, quote_id: "" }))} />
              )}
            </label>
            <fieldset className={s.field} style={{ border: 0, padding: 0, margin: 0 }}>
              <legend style={{ padding: 0, marginBottom: 6 }}>{t("fields.source")} *</legend>
              <div className={s.actions}>
                {(["quote", "direct"] as const).map((src) => (
                  <label key={src} className={s.actions} style={{ gap: 6 }}>
                    <input type="radio" name="source" value={src} checked={values.source === src} disabled={busy}
                      onChange={() => setValues((v) => ({ ...v, source: src, quote_id: src === "direct" ? "" : v.quote_id }))} />
                    {t(`sources.${src}`)}
                  </label>
                ))}
              </div>
            </fieldset>
            {values.source === "quote" && (
              <label className={s.field}>{t("fields.quote")} *
                <select value={values.quote_id} disabled={busy || loadingQuote || !values.customer_id} onChange={(e) => void chooseQuote(e.target.value)}>
                  <option value="">{quotes.length ? t("fields.selectQuote") : t("fields.noAcceptedQuotes")}</option>
                  {quotes.map((q) => <option key={q.id} value={q.id}>{q.quote_number}</option>)}
                </select>
                {loadingQuote && <span className={s.muted}>{messages("loading.fetching")}</span>}
              </label>
            )}
            <label className={s.field}>{t("fields.customerReference")}{values.source === "direct" ? " *" : ""}
              <input value={values.customer_reference} maxLength={120} required={values.source === "direct"} disabled={busy}
                placeholder={t("fields.customerReferenceHint")} onChange={(e) => set("customer_reference", e.target.value)} />
            </label>
            <label className={s.field}>{t("fields.orderDate")} *
              <input type="datetime-local" value={values.order_date} required disabled={busy} onChange={(e) => set("order_date", e.target.value)} />
            </label>
            <label className={s.field}>{t("fields.requestedDelivery")}
              <input type="datetime-local" value={values.requested_delivery_date} disabled={busy}
                onChange={(e) => set("requested_delivery_date", e.target.value)} />
            </label>
            <label className={s.field}>{t("fields.currency")}{priced ? " *" : ""}
              <select value={values.currency} disabled={busy} onChange={(e) => set("currency", e.target.value as Values["currency"])}>
                {(["SAR", "USD"] as const).map((c) => <option key={c} value={c}>{currencies(c)}</option>)}
              </select>
            </label>
          </div>
          {values.source === "quote" && <p className={s.muted} style={{ marginBottom: 0 }}>{t("quoteCopyHint")}</p>}
        </section>

        <section className={s.panel} aria-label={t("items.sectionTitle")}>
          <div className={s.actions} style={{ justifyContent: "space-between", marginBottom: 12 }}>
            <h2 style={{ margin: 0 }}>{t("items.sectionTitle")}</h2>
            <button type="button" className={s.button} disabled={busy} onClick={() => set("lines", [...values.lines, emptyLine()])}>
              {t("items.addButton")}
            </button>
          </div>
          <p className={s.muted} style={{ marginTop: 0 }}>{t("pricesOptionalHint")}</p>
          {values.lines.map((line, index) => (
            <section key={index} className={s.panel} style={{ marginBottom: 12 }} aria-label={t("items.lineTitle", { number: index + 1 })}>
              <div className={s.actions} style={{ justifyContent: "space-between", marginBottom: 12 }}>
                <h3 style={{ margin: 0, fontSize: 16 }}>{t("items.lineTitle", { number: index + 1 })}</h3>
                <button type="button" className={s.button} disabled={busy || values.lines.length === 1}
                  onClick={() => set("lines", values.lines.filter((_, i) => i !== index))}>{t("items.removeButton")}</button>
              </div>
              <div className={s.grid}>
                <label className={s.field}>{t("items.fields.productType")} *
                  <ProductSelect value={line.product_type} disabled={busy} ariaLabel={t("items.fields.productType")}
                    onChange={(key) => chooseProduct(index, key)} />
                </label>
                <label className={s.field}>{t("items.fields.quantity")} *
                  <input type="number" step="0.01" min="0.01" value={line.quantity} required disabled={busy}
                    onChange={(e) => setLine(index, { quantity: e.target.value })} />
                </label>
                <label className={s.field}>{t("items.fields.unit")} *
                  <UnitSelect className="" value={line.unit} disabled={busy} ariaLabel={t("items.fields.unit")} onChange={(unit) => setLine(index, { unit })} />
                </label>
                <label className={s.field}>{t("items.fields.unitPriceOptional")}
                  <input type="number" step="0.0001" min="0" value={line.unit_price} disabled={busy}
                    onChange={(e) => setLine(index, { unit_price: e.target.value })} />
                </label>
                <div className={s.field}>{t("items.fields.lineTotal")}
                  <strong>{line.unit_price.trim() ? <Money amount={Number(line.quantity || 0) * Number(line.unit_price || 0)} currency={values.currency} /> : "—"}</strong>
                </div>
              </div>
              <div style={{ marginTop: 12 }}>
                <span className={s.muted}>{t("items.fields.specification")}</span>
                <SpecEditor value={line.spec} disabled={busy} template={products?.find((p) => p.key === line.product_type)?.properties}
                  onChange={(json) => setLine(index, { spec: json })} />
              </div>
            </section>
          ))}
          {priced && <p style={{ marginBottom: 0 }}><strong>{t("fields.total")}:</strong> <Money amount={total} currency={values.currency} /></p>}
        </section>

        <section className={s.panel}>
          <label className={s.field}>{t("fields.notes")}
            <textarea value={values.notes} disabled={busy} onChange={(e) => set("notes", e.target.value)} />
          </label>
        </section>

        {error && <p role="alert" className={s.error}>{error}</p>}
        <div className={s.actions}>
          <button type="submit" className={`${s.button} ${s.primary}`} disabled={busy || !values.customer_id}>
            {busy ? messages("loading.saving") : editing ? t("updateButton") : t("saveDraft")}
          </button>
          <Link href={back} className={s.button}>{common("actions.cancel")}</Link>
          <span className={s.muted}>* {common("labels.required")} · {t("draftHint")}</span>
        </div>
      </form>
    </PageFrame>
  );
}
