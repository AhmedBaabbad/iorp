"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { useLocale, useTranslations } from "next-intl";
import { PageFrame } from "@/components/layout/page-frame";
import { ProductSelect, useProductName, useProducts } from "@/features/masterdata";
import { SpecList } from "@/features/commercial-orders/components/sales-lifecycle";
import { usePermission } from "@/features/auth/permission-hooks";
import { demandsApi, type Customer, type Item, type DemandPriority, type DemandStatus } from "./api";
import { ErrorMessage, errorKey, priorities, today } from "./shared";
import s from "./demands.module.css";
import { P } from "@/lib/production-permissions";

type Row = Item & { key: string; specText: string };
const newRow = (item?: Item): Row => ({ product_type: "", target_spec_json: null, required_quantity: "", unit: "", notes: "", ...item, key: crypto.randomUUID(), specText: JSON.stringify(item?.target_spec_json ?? {}, null, 2) });

export function DemandForm({ id, onBack }: { id?: string; onBack?: () => void }) {
  const t = useTranslations("production.demands");
  const locale = useLocale();
  const units = useTranslations("common.units.units");
  const products = useProducts();  // MD-001: product types and their specification templates come from master data
  const router = useRouter();
  const canRelease = usePermission(P.DEMANDS_RELEASE);
  const [savedId, setSavedId] = useState<string | undefined>(id);
  const [customerId, setCustomer] = useState("");
  const [salesOrder, setSalesOrder] = useState<{ id: string; number: string | null } | null>(null);
  const productName = useProductName();
  const [search, setSearch] = useState("");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [requestDate, setRequestDate] = useState(today());
  const [delivery, setDelivery] = useState("");
  const [priority, setPriority] = useState<DemandPriority>("normal");
  const [notes, setNotes] = useState("");
  const [status, setStatus] = useState<DemandStatus>("draft");
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(!!id);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => demandsApi.customers(search).then(v => { if (active) setCustomers(v); }).catch(e => { if (active) setError(errorKey(e)); }), 200);
    return () => { active = false; clearTimeout(timer); };
  }, [search]);
  useEffect(() => {
    if (!id) return;
    let active = true;
    demandsApi.get(id).then(d => {
      if (!active) return;
      setCustomer(d.customer.id); setSelectedCustomer(d.customer); setSalesOrder(d.sales_order ?? null); setRequestDate(d.request_date); setDelivery(d.requested_delivery_date ?? ""); setPriority(d.priority); setNotes(d.notes ?? ""); setStatus(d.status); setRows(d.items.map(newRow));
    }).catch(e => { if (active) setError(errorKey(e)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [id]);
  function update(key: string, values: Partial<Row>) { setRows(old => old.map(row => row.key === key ? { ...row, ...values } : row)); }
  function specValue(row: Row, key: string) { try { return JSON.parse(row.specText)[key] ?? ""; } catch { return ""; } }
  function updateSpec(row: Row, key: string, value: string, numeric = false) {
    try {
      const specs = JSON.parse(row.specText);
      if (!value) delete specs[key]; else specs[key] = numeric ? Number(value) : value;
      update(row.key, { specText: JSON.stringify(specs, null, 2) });
    } catch { setError("invalid_specs"); }
  }
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setNotice("");
    const ready = (event.nativeEvent as SubmitEvent).submitter?.getAttribute("value") === "ready";
    if (!customerId) { setError("customer_required"); return; }
    if (!rows.length) { setError("items_required"); return; }
    if (salesOrder && savedId) {
      // From a sales order: the header, and each line's quantity (never above what the order still has).
      setBusy(true);
      try {
        for (const row of rows) {
          if (!(Number(row.required_quantity) > 0)) { setError("invalid_item"); setBusy(false); return; }
          await demandsApi.setItemQuantity(savedId, row.id!, row.required_quantity, row.notes || null);
        }
        const d = await demandsApi.saveHeader(savedId, { request_date: requestDate, requested_delivery_date: delivery || null, priority, notes: notes || null });
        if (ready && d.status === "draft") await demandsApi.status(d.id, "ready_for_planning");
        router.push(`/production/demands/${d.id}`);
      } catch (e) { setError(errorKey(e)); setBusy(false); }
      return;
    }
    const items: Item[] = [];
    try {
      for (const [index, row] of rows.entries()) {
        const spec: unknown = JSON.parse(row.specText);
        if (!spec || Array.isArray(spec) || typeof spec !== "object") throw new Error();
        if (!(Number(row.required_quantity) > 0) || !row.unit.trim() || !row.product_type?.trim()) { setError("invalid_item"); return; }
        items.push({ line_no: index + 1, product_type: row.product_type || null, target_spec_json: spec as Record<string, unknown>, required_quantity: row.required_quantity, unit: row.unit, notes: row.notes || null });
      }
    } catch { setError("invalid_specs"); return; }
    setBusy(true);
    try {
      const d = await demandsApi.save({ customer_id: customerId, quote_id: null, request_date: requestDate, requested_delivery_date: delivery || null, priority, notes: notes || null, items }, savedId);
      setSavedId(d.id);
      if (ready && d.status === "draft") {
        try { await demandsApi.status(d.id, "ready_for_planning"); }
        catch (e) { setNotice(t("savedDraftReadyFailed")); setError(errorKey(e)); return; }
      }
      router.push(`/production/demands/${d.id}`);
    } catch (e) { setError(errorKey(e)); } finally { setBusy(false); }
  }
  const customerOptions = selectedCustomer && !customers.some(c => c.id === selectedCustomer.id) ? [selectedCustomer, ...customers] : customers;
  const editable = ["draft", "ready_for_planning"].includes(status);
  return <PageFrame title={id ? t("editTitle") : t("createTitle")} subtitle={t("listSubtitle")}>
    <div className={s.toolbar}><Link href="/production/demands" className={s.button}>{t("backToList")}</Link>
      {onBack && <button type="button" className={s.linkButton} onClick={onBack}>{t("fromSalesOrder.fromOrderInstead")}</button>}</div>
    <ErrorMessage code={error} />
    {notice && <p className={s.success} role="status">{notice}</p>}
    {loading ? <p>{t("loading")}</p> : !editable ? <ErrorMessage code="demand_not_editable" /> : <form onSubmit={save}>
      <fieldset disabled={busy} className={s.panel}><legend>{t("details")}</legend><div className={s.grid}>
        <label className={s.field}>{t("searchCustomer")}<input disabled={status !== "draft"} value={search} onChange={e => setSearch(e.target.value)} /></label>
        <label className={s.field}>{t("customer")}<select required disabled={status !== "draft" || !!salesOrder} value={customerId} onChange={e => { setCustomer(e.target.value); setSelectedCustomer(customers.find(c => c.id === e.target.value) ?? null); }}><option value="">{t("selectCustomer")}</option>{customerOptions.map(c => <option key={c.id} value={c.id}>{c.code} · {c.name}</option>)}</select></label>
        {salesOrder && <div className={s.field}>{t("fromSalesOrder.salesOrder")}<a href={`/commercial-orders/${salesOrder.id}`}><bdi>{salesOrder.number}</bdi></a></div>}
        <label className={s.field}>{t("requestDate")}<input type="date" required value={requestDate} onChange={e => setRequestDate(e.target.value)} /></label>
        <label className={s.field}>{t("requestedDeliveryDate")}<input type="date" value={delivery} onChange={e => setDelivery(e.target.value)} /></label>
        <label className={s.field}>{t("priority")}<select value={priority} onChange={e => setPriority(e.target.value as DemandPriority)}>{priorities.map(v => <option key={v} value={v}>{t(`priorities.${v}`)}</option>)}</select></label>
        <label className={s.field}>{t("notes")}<textarea value={notes} onChange={e => setNotes(e.target.value)} /></label>
      </div></fieldset>
      {salesOrder ? <fieldset disabled={busy} className={s.panel}><legend>{t("items")}</legend>
        <p className={s.muted}>{t("fromSalesOrder.lockedLinesHint")}</p>
        {rows.map((row, index) => <section className={s.panel} key={row.key}><h3>{t("itemTitle", { number: index + 1 })}</h3>
          <div>{productName(row.product_type)}<SpecList productKey={row.product_type ?? ""} spec={row.target_spec_json} /></div>
          <div className={s.grid} style={{ marginTop: 12 }}>
            <label className={s.field}>{t("quantity")} ({units.has(row.unit) ? units(row.unit) : row.unit})<input required type="number" min="0.001" step="0.001" value={row.required_quantity} onChange={e => update(row.key, { required_quantity: e.target.value })} /></label>
            <label className={s.field}>{t("itemNotes")}<textarea value={row.notes ?? ""} onChange={e => update(row.key, { notes: e.target.value })} /></label>
          </div></section>)}
      </fieldset> : <fieldset disabled={busy} className={s.panel}><legend>{t("items")}</legend><div className={s.toolbar}>
        <button type="button" className={s.button} onClick={() => setRows(old => [...old, newRow()])}>{t("addItem")}</button>
      </div>
      {rows.map((row, index) => <section className={s.panel} key={row.key}><h3>{t("itemTitle", { number: index + 1 })}</h3><div className={s.grid}>
        <label className={s.field}>{t("productType")}<ProductSelect ariaLabel={t("productType")} value={row.product_type ?? ""}
          onChange={(key, product) => update(row.key, { product_type: key, ...(product?.default_unit && !row.unit ? { unit: product.default_unit } : {}) })} /></label>
        <label className={s.field}>{t("quantity")}<input required type="number" min="0.001" step="0.001" value={row.required_quantity} onChange={e => update(row.key, { required_quantity: e.target.value })} /></label>
        <label className={s.field}>{t("unit")}<input list="demand-units" required maxLength={20} value={row.unit} onChange={e => update(row.key, { unit: e.target.value })} /></label>
        {(products?.find(x => x.key === row.product_type)?.properties ?? []).map(q => <label key={q.key} className={s.field}>
          {locale === "ar" ? q.name_ar : q.name_en}{q.unit ? ` (${units.has(q.unit) ? units(q.unit) : q.unit})` : ""}
          {q.kind === "choice" ? <select value={specValue(row, q.key)} onChange={e => updateSpec(row, q.key, e.target.value)}><option value="">—</option>
            {(q.options ?? []).map(o => <option key={o.value} value={o.value}>{locale === "ar" ? o.label_ar : o.label_en}</option>)}</select>
            : <input type={q.kind === "number" ? "number" : "text"} step="any" value={specValue(row, q.key)} onChange={e => updateSpec(row, q.key, e.target.value, q.kind === "number")} />}</label>)}
        <label className={s.field}>{t("specifications")}<textarea dir="ltr" value={row.specText} onChange={e => update(row.key, { specText: e.target.value })} /></label>
        <label className={s.field}>{t("itemNotes")}<textarea value={row.notes ?? ""} onChange={e => update(row.key, { notes: e.target.value })} /></label>
      </div><button type="button" className={s.button} onClick={() => setRows(old => old.filter(r => r.key !== row.key))}>{t("removeItem")}</button></section>)}
      </fieldset>}
      <datalist id="demand-units">{["kg", "roll", "pcs", "m"].map(v => <option key={v} value={v}>{t(`units.${v}`)}</option>)}</datalist>
      <div className={s.toolbar}><button disabled={busy} className={`${s.button} ${s.primary}`} type="submit" value="draft">{id || savedId ? t("saveChanges") : t("saveDraft")}</button>{canRelease && status === "draft" && <button disabled={busy} className={s.button} type="submit" value="ready">{t("saveAndReady")}</button>}</div>
    </form>}
  </PageFrame>;
}
