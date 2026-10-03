"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import { demandsApi, type Customer, type Quote, type Item, type DemandPriority, type DemandStatus } from "./api";
import { ErrorMessage, errorKey, priorities, today } from "./shared";
import s from "./demands.module.css";
import { P } from "@/lib/production-permissions";

type Row = Item & { key: string; specText: string };
const newRow = (item?: Item): Row => ({ product_type: "", target_spec_json: null, required_quantity: "", unit: "", notes: "", ...item, key: crypto.randomUUID(), specText: JSON.stringify(item?.target_spec_json ?? {}, null, 2) });
const knownSpecs = ["width_mm", "thickness_mm", "color", "roll_weight_kg"];

export function DemandForm({ id }: { id?: string }) {
  const t = useTranslations("production.demands");
  const p = useTranslations("production.planning");
  const router = useRouter();
  const canUpdate = usePermission(P.DEMANDS_UPDATE);
  const [savedId, setSavedId] = useState<string | undefined>(id);
  const [customerId, setCustomer] = useState("");
  const [quoteId, setQuote] = useState("");
  const [search, setSearch] = useState("");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [quotes, setQuotes] = useState<Quote[]>([]);
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
      setCustomer(d.customer.id); setSelectedCustomer(d.customer); setQuote(d.quote?.id ?? ""); setRequestDate(d.request_date); setDelivery(d.requested_delivery_date ?? ""); setPriority(d.priority); setNotes(d.notes ?? ""); setStatus(d.status); setRows(d.items.map(newRow));
    }).catch(e => { if (active) setError(errorKey(e)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [id]);
  useEffect(() => {
    let active = true; setQuotes([]);
    if (customerId) demandsApi.quotes(customerId).then(v => { if (active) setQuotes(v); }).catch(e => { if (active) setError(errorKey(e)); });
    return () => { active = false; };
  }, [customerId]);
  function update(key: string, values: Partial<Row>) { setRows(old => old.map(row => row.key === key ? { ...row, ...values } : row)); }
  function specValue(row: Row, key: string) { try { return JSON.parse(row.specText)[key] ?? ""; } catch { return ""; } }
  function updateSpec(row: Row, key: string, value: string) {
    try {
      const specs = JSON.parse(row.specText);
      if (!value) delete specs[key]; else specs[key] = key === "color" ? value : Number(value);
      update(row.key, { specText: JSON.stringify(specs, null, 2) });
    } catch { setError("invalid_specs"); }
  }
  async function importItems() {
    setBusy(true); setError("");
    try { const items = await demandsApi.quoteItems(quoteId, customerId); setRows(old => [...old, ...items.map(i => newRow({ ...i, line_no: undefined }))]); setNotice(t("importSuccess", { count: items.length })); }
    catch (e) { setError(errorKey(e)); } finally { setBusy(false); }
  }
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setNotice("");
    const ready = (event.nativeEvent as SubmitEvent).submitter?.getAttribute("value") === "ready";
    if (!customerId) { setError("customer_required"); return; }
    if (!rows.length) { setError("items_required"); return; }
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
      const d = await demandsApi.save({ customer_id: customerId, quote_id: quoteId || null, request_date: requestDate, requested_delivery_date: delivery || null, priority, notes: notes || null, items }, savedId);
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
    <Link href="/production/demands" className={s.button}>{t("backToList")}</Link><ErrorMessage code={error} />
    {notice && <p className={s.success} role="status">{notice}</p>}
    {loading ? <p>{t("loading")}</p> : !editable ? <ErrorMessage code="demand_not_editable" /> : <form onSubmit={save}>
      <fieldset disabled={busy} className={s.panel}><legend>{t("details")}</legend><div className={s.grid}>
        <label className={s.field}>{t("searchCustomer")}<input disabled={status !== "draft"} value={search} onChange={e => setSearch(e.target.value)} /></label>
        <label className={s.field}>{t("customer")}<select required disabled={status !== "draft"} value={customerId} onChange={e => { setCustomer(e.target.value); setSelectedCustomer(customers.find(c => c.id === e.target.value) ?? null); setQuote(""); }}><option value="">{t("selectCustomer")}</option>{customerOptions.map(c => <option key={c.id} value={c.id}>{c.code} · {c.name}</option>)}</select></label>
        {customerId && <label className={s.field}>{t("quote")}<select value={quoteId} onChange={e => setQuote(e.target.value)}><option value="">{t("selectQuote")}</option>{quotes.map(q => <option key={q.id} value={q.id}>{q.number}</option>)}</select><span className={s.muted}>{t("quoteOptional")}</span>{!quotes.length && <span className={s.muted}>{t("noQuotesForCustomer")}</span>}</label>}
        <label className={s.field}>{t("requestDate")}<input type="date" required value={requestDate} onChange={e => setRequestDate(e.target.value)} /></label>
        <label className={s.field}>{t("requestedDeliveryDate")}<input type="date" value={delivery} onChange={e => setDelivery(e.target.value)} /></label>
        <label className={s.field}>{t("priority")}<select value={priority} onChange={e => setPriority(e.target.value as DemandPriority)}>{priorities.map(v => <option key={v} value={v}>{t(`priorities.${v}`)}</option>)}</select></label>
        <label className={s.field}>{t("notes")}<textarea value={notes} onChange={e => setNotes(e.target.value)} /></label>
      </div></fieldset>
      <fieldset disabled={busy} className={s.panel}><legend>{t("items")}</legend><div className={s.toolbar}>
        {quoteId && <button type="button" className={s.button} onClick={importItems}>{t("importQuoteItems")}</button>}
        <button type="button" className={s.button} onClick={() => setRows(old => [...old, newRow()])}>{t("addItem")}</button>
      </div>{quoteId && <p className={s.muted}>{t("snapshotNote")}</p>}
      {rows.map((row, index) => <section className={s.panel} key={row.key}><h3>{t("itemTitle", { number: index + 1 })}</h3><div className={s.grid}>
        <label className={s.field}>{t("productType")}<input required list="demand-product-types" maxLength={100} value={row.product_type ?? ""} onChange={e => update(row.key, { product_type: e.target.value })} /></label>
        <label className={s.field}>{t("quantity")}<input required type="number" min="0.001" step="0.001" value={row.required_quantity} onChange={e => update(row.key, { required_quantity: e.target.value })} /></label>
        <label className={s.field}>{t("unit")}<input list="demand-units" required maxLength={20} value={row.unit} onChange={e => update(row.key, { unit: e.target.value })} /></label>
        {row.product_type === "pp_strap" && knownSpecs.map(key => <label key={key} className={s.field}>{p(`specColumns.${key}`)}<input type={key === "color" ? "text" : "number"} step="any" value={specValue(row, key)} onChange={e => updateSpec(row, key, e.target.value)} /></label>)}
        <label className={s.field}>{t("specifications")}<textarea dir="ltr" value={row.specText} onChange={e => update(row.key, { specText: e.target.value })} /></label>
        <label className={s.field}>{t("itemNotes")}<textarea value={row.notes ?? ""} onChange={e => update(row.key, { notes: e.target.value })} /></label>
      </div><button type="button" className={s.button} onClick={() => setRows(old => old.filter(r => r.key !== row.key))}>{t("removeItem")}</button></section>)}
      </fieldset>
      <datalist id="demand-product-types">{["pp_strap", "carton_box"].map(v => <option key={v} value={v}>{t(`products.${v}`)}</option>)}</datalist>
      <datalist id="demand-units">{["kg", "roll", "pcs", "m"].map(v => <option key={v} value={v}>{t(`units.${v}`)}</option>)}</datalist>
      <div className={s.toolbar}><button disabled={busy} className={`${s.button} ${s.primary}`} type="submit" value="draft">{id || savedId ? t("saveChanges") : t("saveDraft")}</button>{canUpdate && status === "draft" && <button disabled={busy} className={s.button} type="submit" value="ready">{t("saveAndReady")}</button>}</div>
    </form>}
  </PageFrame>;
}
