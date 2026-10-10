"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";

import { UnitSelect } from "@/components/forms/UnitSelect";
import { Money } from "@/components/money/Money";
import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import { useBusinessSettings } from "@/features/masterdata";
import { ReasonDialog } from "@/features/production-demands/reason-dialog";
import s from "@/features/production-demands/demands.module.css";
import { useFormatter } from "@/hooks/useFormatter";
import { PR } from "@/lib/procurement-permissions";
import {
  approveOrder, cancelOrder, closeOrder, createOrder, downloadOrder, getMaterials, getOrder, getOrders, getProcurementSettings, getSupplierOptions,
  sendOrder, updateOrder, updateProcurementSettings, type OrderFilters,
} from "../api";
import { DECIMAL, procurementErrorMessage, todayIso } from "../procurement-errors";
import {
  CURRENCIES, INCOTERMS, ORDER_STATUSES, PAYMENT_TERMS, type Currency, type Material, type Order, type OrderInput, type OrderListItem,
  type OrderStatus, type ProcurementSettings, type SupplierOption,
} from "../types";
import { SupplierStatusBadge } from "./Suppliers";

const STATUS_CLASS: Record<OrderStatus, string> = { draft: "", approved: s.blue, sent: s.blue, partially_received: s.overdue, received: s.green,
  closed: s.green, cancelled: s.cancelled };
const PRICE = /^\d+(\.\d{1,4})?$/;
const MONEY = /^\d+(\.\d{1,2})?$/;
const cents = (value: number) => Math.round(value * 100);
// Unit prices keep up to four decimals (resin is priced per kilogram), never fewer than two.
const priceplaces = (value: string) => Math.min(4, Math.max(2, (value.split(".")[1] ?? "").replace(/0+$/, "").length));

export function OrderStatusBadge({ status }: { status: OrderStatus }) {
  const t = useTranslations("procurement.orderStatuses");
  return <span className={`${s.badge} ${STATUS_CLASS[status]}`}>{t(status)}</span>;
}

function Item({ label, children }: { label: string; children: ReactNode }) {
  return <div><dt className={s.muted}>{label}</dt><dd style={{ margin: "4px 0 0", overflowWrap: "anywhere", whiteSpace: "pre-wrap" }}>{children}</dd></div>;
}

// "أوامر الشراء": what was ordered from each supplier, its value, and how much of it has arrived.
export function OrdersList() {
  const t = useTranslations("procurement");
  const errors = useTranslations("procurement.errors");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const canCreate = usePermission(PR.PO_CREATE);
  const [filters, setFilters] = useState<Required<Omit<OrderFilters, "supplier_id">>>({ status: "", date_from: "", date_to: "", search: "" });
  const [rows, setRows] = useState<OrderListItem[] | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setError("");
    try { setRows(await getOrders(filters)); } catch (e) { setError(procurementErrorMessage(e, errors)); }
  }, [filters, errors]);
  useEffect(() => { const timer = setTimeout(() => void load(), 200); return () => clearTimeout(timer); }, [load]);
  const set = (field: keyof typeof filters, value: string) => setFilters(old => ({ ...old, [field]: value }));

  return <PageFrame title={t("orders.title")} subtitle={t("orders.subtitle")}
    action={canCreate ? <Link href="/purchase-orders/new" className={`${s.button} ${s.primary}`}>{t("orders.new")}</Link> : undefined}>
    <section className={s.toolbar} aria-label={t("filtersAria")}>
      <label className={s.field}>{t("search")}<input type="search" value={filters.search} placeholder={t("orders.searchPlaceholder")} onChange={e => set("search", e.target.value)} /></label>
      <label className={s.field}>{t("fields.status")}
        <select value={filters.status} onChange={e => set("status", e.target.value)}>
          <option value="">{t("all")}</option>{ORDER_STATUSES.map(v => <option key={v} value={v}>{t(`orderStatuses.${v}`)}</option>)}</select></label>
      <label className={s.field}>{t("dateFrom")}<input type="date" value={filters.date_from} onChange={e => set("date_from", e.target.value)} /></label>
      <label className={s.field}>{t("dateTo")}<input type="date" value={filters.date_to} onChange={e => set("date_to", e.target.value)} /></label>
    </section>
    {error && <p role="alert" className={s.error}>{error}</p>}
    {rows === null && !error && <p className={s.muted}>{messages("loading.default")}</p>}
    {rows?.length === 0 && <section className={s.panel}><h2 style={{ marginTop: 0 }}>{t("orders.empty")}</h2><p className={s.muted} style={{ margin: 0 }}>{t("orders.emptyHint")}</p></section>}
    {rows && rows.length > 0 && <section className={s.panel}><div className={s.tableWrap}><table className={s.table} aria-label={t("orders.title")}>
      <thead><tr>{["number", "date", "supplier", "subject", "total", "receivedPct", "status"].map(c => <th key={c}>{t(`orders.columns.${c}`)}</th>)}</tr></thead>
      <tbody>{rows.map(o => <tr key={o.id}>
        <td><Link href={`/purchase-orders/${o.id}`}><bdi>{o.po_number}</bdi></Link></td>
        <td>{fmt.date(o.order_date)}{o.required_date && <div className={s.muted}>{t("orders.requiredBy", { date: fmt.date(o.required_date) })}</div>}</td>
        <td>{o.supplier_name}</td>
        <td>{o.subject ?? "—"}{o.supplier_quote_ref && <div className={s.muted}><bdi dir="ltr">{o.supplier_quote_ref}</bdi></div>}</td>
        <td><Money amount={o.total_amount} currency={o.currency} />
          <div className={s.muted}>{Number(o.tax_rate) > 0 ? t("orders.withVat") : t("orders.noVat")}</div></td>
        <td>{["draft", "cancelled"].includes(o.status) ? "—" : `${Number(o.received_pct)}%`}</td>
        <td><OrderStatusBadge status={o.status} /></td>
      </tr>)}</tbody>
    </table></div></section>}
    <OrderSettings />
  </PageFrame>;
}

// The purchase order number prefix and the general terms printed on every order (one per line, in each language).
function OrderSettings() {
  const t = useTranslations("procurement.orderSettings");
  const errors = useTranslations("procurement.errors");
  const canEdit = usePermission(PR.SETTINGS_UPDATE);
  const [v, setV] = useState<ProcurementSettings | null>(null);
  const [message, setMessage] = useState("");
  useEffect(() => { if (canEdit) getProcurementSettings().then(setV).catch(() => setV(null)); }, [canEdit]);
  if (!canEdit || v === null) return null;
  return <form className={s.panel} aria-label={t("title")} onSubmit={async e => {
    e.preventDefault(); setMessage("");
    try { setV(await updateProcurementSettings({ po_prefix: v.po_prefix, po_terms_ar: v.po_terms_ar ?? "", po_terms_en: v.po_terms_en ?? "" })); setMessage(t("saved")); }
    catch (err) { setMessage(procurementErrorMessage(err, errors)); }
  }}>
    <h2 style={{ marginTop: 0 }}>{t("title")}</h2>
    <div className={s.grid}>
      <label className={s.field}>{t("prefix")}<input dir="ltr" required maxLength={20} pattern="[A-Za-z0-9_\-/]+" value={v.po_prefix}
        onChange={e => setV({ ...v, po_prefix: e.target.value })} />
        <span className={s.muted}>{t("example", { number: `${v.po_prefix}${new Date().getFullYear()}-0001` })}</span></label>
    </div>
    <div className={s.grid}>
      <label className={s.field}>{t("termsAr")}<textarea dir="rtl" rows={5} maxLength={8000} value={v.po_terms_ar ?? ""} onChange={e => setV({ ...v, po_terms_ar: e.target.value })} /></label>
      <label className={s.field}>{t("termsEn")}<textarea dir="ltr" rows={5} maxLength={8000} value={v.po_terms_en ?? ""} onChange={e => setV({ ...v, po_terms_en: e.target.value })} /></label>
    </div>
    <p className={s.muted}>{t("termsHint")}</p>
    <div className={s.actions}>
      <button type="submit" className={s.button}>{t("save")}</button>
      {message && <span role="status" className={s.muted}>{message}</span>}
    </div>
  </form>;
}

type Line = { material_id: string; description: string; notes: string; quantity: string; unit: string; unit_price: string };
const EMPTY_LINE: Line = { material_id: "", description: "", notes: "", quantity: "", unit: "kg", unit_price: "" };
type Header = { [K in "required_date" | "attention" | "supplier_quote_ref" | "subject" | "payment_terms" | "payment_terms_note" | "incoterm"
  | "delivery_place" | "notes" | "discount_amount"]: string };
const EMPTY_HEADER: Header = { required_date: "", attention: "", supplier_quote_ref: "", subject: "", payment_terms: "", payment_terms_note: "", incoterm: "",
  delivery_place: "", notes: "", discount_amount: "" };
const blank = (v: string) => v.trim() || null;
const plain = (v: string | null) => (v === null ? "" : String(Number(v)));

// A purchase order: written as a draft, edited until it is approved. The amounts shown are a preview; the server computes them.
export function OrderForm({ orderId, supplierId }: { orderId?: string; supplierId?: string }) {
  const t = useTranslations("procurement");
  const errors = useTranslations("procurement.errors");
  const messages = useTranslations("messages");
  const currencies = useTranslations("common.currencies");
  const router = useRouter();
  const [supplier, setSupplier] = useState(supplierId ?? "");
  const [query, setQuery] = useState("");
  const [suppliers, setSuppliers] = useState<SupplierOption[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [date, setDate] = useState(todayIso());
  // MD-001: the organization's VAT rate and default currency; an order keeps the rate it was written with.
  const general = useBusinessSettings();
  const [savedRate, setSavedRate] = useState<number | null>(null);
  const vatRate = savedRate ?? general.vatRate;
  const [currency, setCurrency] = useState<Currency>("SAR");
  const [touched, setTouched] = useState(Boolean(orderId));
  const [vat, setVat] = useState(true);
  useEffect(() => {  // a new order starts in the organization's currency (with VAT for riyals)
    if (!touched && general.loaded) { setCurrency(general.currency); setVat(general.currency === "SAR"); }
  }, [touched, general.loaded, general.currency]);
  const [h, setH] = useState<Header>(EMPTY_HEADER);
  const [lines, setLines] = useState<Line[]>([{ ...EMPTY_LINE }]);
  const [loading, setLoading] = useState(Boolean(orderId));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { getMaterials({ active_only: true }).then(setMaterials).catch(() => setMaterials([])); }, []);
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => getSupplierOptions(query).then(found => { if (active) setSuppliers(old => [...found, ...old.filter(o => o.id === supplier && !found.some(f => f.id === o.id))]); })
      .catch(() => undefined), 200);
    return () => { active = false; clearTimeout(timer); };
  }, [query, supplier]);
  useEffect(() => {
    if (!orderId) return;
    let active = true;
    getOrder(orderId).then(o => {
      if (!active) return;
      setSupplier(o.supplier_id); setDate(o.order_date); setCurrency(o.currency); setVat(Number(o.tax_rate) > 0);
      setSavedRate(Number(o.tax_rate) > 0 ? Number(o.tax_rate) : null);
      setSuppliers(old => [...old, { id: o.supplier_id, supplier_code: "", name: o.supplier_name, status: o.supplier_status ?? "approved" }]);
      setH({ ...Object.fromEntries(Object.keys(EMPTY_HEADER).map(k => [k, (o[k as keyof Order] as string | null) ?? ""])) as Header,
        discount_amount: Number(o.discount_amount) ? plain(o.discount_amount) : "" });
      setLines(o.lines.map(l => ({ material_id: l.material_id ?? "", description: l.description, notes: l.notes ?? "", quantity: plain(l.quantity), unit: l.unit,
        unit_price: plain(l.unit_price) })));
    }).catch(e => { if (active) setError(procurementErrorMessage(e, errors)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [orderId, errors]);

  const byId = useMemo(() => new Map(materials.map(m => [m.id, m])), [materials]);
  const setLine = (i: number, field: keyof Line, value: string) => setLines(old => old.map((l, n) => {
    if (n !== i) return l;
    const next = { ...l, [field]: value };
    if (field === "material_id" && byId.get(value)) { next.unit = byId.get(value)!.unit; next.description = byId.get(value)!.name; }
    return next;
  }));
  // A local supplier is charged VAT; an import from abroad (usually in dollars) is not. The choice stays the user's.
  const chooseCurrency = (next: Currency) => { setTouched(true); setCurrency(next); setVat(next === "SAR"); };
  const linesOk = lines.every(l => l.description.trim() && DECIMAL.test(l.quantity.trim()) && Number(l.quantity) > 0 && l.unit && PRICE.test(l.unit_price.trim()));
  const subtotal = lines.reduce((sum, l) => sum + (linesOk ? cents(Number(l.quantity) * Number(l.unit_price)) : 0), 0);
  const discountOk = !h.discount_amount.trim() || MONEY.test(h.discount_amount.trim());
  const discount = discountOk ? cents(Number(h.discount_amount || 0)) : 0;
  const taxable = Math.max(0, subtotal - discount);
  const tax = vat ? Math.round(taxable * vatRate / 100) : 0;
  const valid = Boolean(supplier && date) && linesOk && discountOk && discount <= subtotal;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid || busy) return;
    setBusy(true); setError("");
    const header = Object.fromEntries(Object.entries(h).map(([k, v]) => [k, blank(v)])) as Record<keyof Header, string | null>;
    const body: OrderInput = { supplier_id: supplier, order_date: date, currency, tax_rate: vat ? vatRate : 0, ...header,
      payment_terms: header.payment_terms as OrderInput["payment_terms"], incoterm: header.incoterm as OrderInput["incoterm"],
      discount_amount: header.discount_amount ?? "0",
      lines: lines.map(l => ({ material_id: l.material_id || null, description: l.description.trim(), notes: blank(l.notes), quantity: l.quantity.trim(), unit: l.unit,
        unit_price: l.unit_price.trim() })) };
    try {
      const saved = orderId ? await updateOrder(orderId, body) : await createOrder(body);
      router.push(`/purchase-orders/${saved.id}`);
    } catch (e) { setError(procurementErrorMessage(e, errors)); setBusy(false); }
  }
  const input = (field: keyof Header, extra: Record<string, unknown> = {}) =>
    <label className={s.field}>{t(`orders.fields.${field}`)}<input value={h[field]} onChange={e => setH(old => ({ ...old, [field]: e.target.value }))} {...extra} /></label>;
  const title = orderId ? t("orders.editTitle") : t("orders.createTitle");
  const back = orderId ? `/purchase-orders/${orderId}` : "/purchase-orders";
  const chosen = suppliers.find(o => o.id === supplier);
  const money = (value: number) => <Money amount={value / 100} currency={currency} />;

  return <PageFrame title={title} subtitle={t("orders.formSubtitle")} action={<Link href={back} className={s.button}>{t("back")}</Link>}>
    {loading ? <p className={s.muted}>{messages("loading.default")}</p> : <form onSubmit={submit} aria-label={title}>
      <fieldset disabled={busy} style={{ border: 0, padding: 0, margin: 0 }}>
        <section className={s.panel} aria-label={t("orders.sections.supplier")}>
          <h2 style={{ marginTop: 0 }}>{t("orders.sections.supplier")}</h2>
          <div className={s.grid}>
            <label className={s.field}>{t("receipts.findSupplier")}<input value={query} placeholder={t("suppliers.searchPlaceholder")} onChange={e => setQuery(e.target.value)} /></label>
            <label className={s.field}>{t("fields.supplier")}
              <select required value={supplier} onChange={e => setSupplier(e.target.value)}>
                <option value="">{t("receipts.chooseSupplier")}</option>
                {suppliers.map(o => <option key={o.id} value={o.id}>{o.name}{o.supplier_code ? ` — ${o.supplier_code}` : ""}</option>)}</select></label>
            {input("attention", { maxLength: 200, placeholder: t("orders.attentionPlaceholder") })}
            {input("supplier_quote_ref", { maxLength: 80, dir: "ltr" })}
          </div>
          {chosen && chosen.status !== "approved" && <p className={s.error} role="status" style={{ marginBottom: 0 }}>
            {t("orders.supplierNotApproved")} <SupplierStatusBadge status={chosen.status} /></p>}
        </section>

        <section className={s.panel} aria-label={t("orders.sections.order")}>
          <h2 style={{ marginTop: 0 }}>{t("orders.sections.order")}</h2>
          <div className={s.grid}>
            <label className={s.field}>{t("orders.fields.order_date")}<input type="date" required value={date} onChange={e => setDate(e.target.value)} /></label>
            {input("required_date", { type: "date" })}
            <label className={s.field}>{t("orders.fields.currency")}
              <select value={currency} onChange={e => chooseCurrency(e.target.value as Currency)}>
                {CURRENCIES.map(c => <option key={c} value={c}>{currencies(c)} ({c})</option>)}</select></label>
            {input("subject", { maxLength: 255 })}
          </div>
          <label style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8 }}>
            <input type="checkbox" checked={vat} onChange={e => { setTouched(true); setVat(e.target.checked); }} /> {t("orders.applyVat", { rate: String(vatRate) })}</label>
          <p className={s.muted} style={{ marginBottom: 0 }}>{vat ? t("orders.vatHint") : t("orders.noVatHint")}</p>
        </section>

        <section className={s.panel} aria-label={t("orders.sections.lines")}>
          <h2 style={{ marginTop: 0 }}>{t("orders.sections.lines")}</h2>
          {lines.map((l, i) => <div key={i} className={s.panel} style={{ margin: "0 0 10px", padding: 14 }}>
            <div className={s.actions} style={{ justifyContent: "space-between", marginBottom: 8 }}>
              <strong>{t("receipts.lineNo", { no: String(i + 1) })}</strong>
              <span className={s.actions}>
                {linesOk && <span className={s.muted}>{t("orders.lineTotal")}: {money(cents(Number(l.quantity) * Number(l.unit_price)))}</span>}
                {lines.length > 1 && <button type="button" className={`${s.button} ${s.danger}`} onClick={() => setLines(old => old.filter((_, n) => n !== i))}>{t("remove")}</button>}
              </span>
            </div>
            <div className={s.grid}>
              <label className={s.field}>{t("fields.material")}
                <select value={l.material_id} onChange={e => setLine(i, "material_id", e.target.value)}>
                  <option value="">{t("orders.otherItem")}</option>{materials.map(m => <option key={m.id} value={m.id}>{m.name} — {m.material_code}</option>)}</select></label>
              <label className={s.field}>{t("fields.description")}<input required maxLength={500} value={l.description} onChange={e => setLine(i, "description", e.target.value)} /></label>
              <label className={s.field}>{t("fields.quantity")}<input required inputMode="decimal" dir="ltr" value={l.quantity} onChange={e => setLine(i, "quantity", e.target.value)} /></label>
              <label className={s.field}>{t("orders.fields.unit")}<UnitSelect value={l.unit} onChange={u => setLine(i, "unit", u)} ariaLabel={t("orders.fields.unit")} /></label>
              <label className={s.field}>{t("orders.fields.unit_price", { currency })}<input required inputMode="decimal" dir="ltr" value={l.unit_price}
                onChange={e => setLine(i, "unit_price", e.target.value)} /></label>
            </div>
            <label className={s.field}>{t("orders.fields.line_notes")}<input maxLength={500} value={l.notes} placeholder={t("orders.lineNotesPlaceholder")}
              onChange={e => setLine(i, "notes", e.target.value)} /></label>
          </div>)}
          <button type="button" className={s.button} onClick={() => setLines(old => [...old, { ...EMPTY_LINE }])}>{t("receipts.addLine")}</button>
          {!linesOk && <p className={s.muted}>{t("orders.linesHint")}</p>}
        </section>

        <section className={s.panel} aria-label={t("orders.sections.totals")}>
          <h2 style={{ marginTop: 0 }}>{t("orders.sections.totals")}</h2>
          <div className={s.grid}>{input("discount_amount", { inputMode: "decimal", dir: "ltr" })}</div>
          {!discountOk || discount > subtotal ? <p role="alert" className={s.error}>{t("orders.discountInvalid")}</p> : null}
          <dl className={s.grid} style={{ margin: "8px 0 0" }}>
            <Item label={t("orders.totals.subtotal")}>{money(subtotal)}</Item>
            {discount > 0 && <Item label={t("orders.totals.discount")}>{money(discount)}</Item>}
            <Item label={vat ? t("orders.totals.vat", { rate: String(vatRate) }) : t("orders.totals.noVat")}>{money(tax)}</Item>
            <Item label={vat ? t("orders.totals.totalWithVat") : t("orders.totals.total")}><strong>{money(taxable + tax)}</strong></Item>
          </dl>
          <p className={s.muted} style={{ marginBottom: 0 }}>{t("orders.previewHint")}</p>
        </section>

        <section className={s.panel} aria-label={t("orders.sections.terms")}>
          <h2 style={{ marginTop: 0 }}>{t("orders.sections.terms")}</h2>
          <div className={s.grid}>
            <label className={s.field}>{t("orders.fields.payment_terms")}
              <select value={h.payment_terms} onChange={e => setH(old => ({ ...old, payment_terms: e.target.value }))}>
                <option value="">—</option>{PAYMENT_TERMS.map(p => <option key={p} value={p}>{t(`paymentTerms.${p}`)}</option>)}</select></label>
            {input("payment_terms_note", { maxLength: 255 })}
            <label className={s.field}>{t("orders.fields.incoterm")}
              <select value={h.incoterm} onChange={e => setH(old => ({ ...old, incoterm: e.target.value }))}>
                <option value="">{t("orders.noIncoterm")}</option>{INCOTERMS.map(p => <option key={p} value={p}>{p} — {t(`incoterms.${p}`)}</option>)}</select></label>
            {input("delivery_place", { maxLength: 500 })}
          </div>
          <label className={s.field}>{t("fields.notes")}<textarea maxLength={4000} value={h.notes} onChange={e => setH(old => ({ ...old, notes: e.target.value }))} /></label>
          <p className={s.muted} style={{ marginBottom: 0 }}>{t("orders.termsFromSettings")}</p>
        </section>
      </fieldset>
      {error && <p role="alert" className={s.error}>{error}</p>}
      <div className={s.actions}>
        <button type="submit" className={`${s.button} ${s.primary}`} disabled={!valid || busy}>{orderId ? t("save") : t("orders.create")}</button>
        <Link href={back} className={s.button}>{t("cancel")}</Link>
      </div>
    </form>}
  </PageFrame>;
}

// One purchase order: the supplier, the delivery and payment, the items with what has arrived, the totals, the next step,
// the document in Arabic or English, the goods receipts against it and the history.
export function OrderDetail({ orderId }: { orderId: string }) {
  const t = useTranslations("procurement");
  const errors = useTranslations("procurement.errors");
  const messages = useTranslations("messages");
  const currencies = useTranslations("common.currencies");
  const fmt = useFormatter();
  const units = useTranslations("common.units.units");
  const unit = (code: string) => (units.has(code) ? units(code) : code);
  const [x, setX] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState<"close" | "cancel" | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try { setX(await getOrder(orderId)); } catch (e) { setError(procurementErrorMessage(e, errors)); } finally { setLoading(false); }
  }, [orderId, errors]);
  useEffect(() => { void load(); }, [load]);
  async function run(key: string, action: () => Promise<Order | void>) {
    setBusy(key); setError("");
    try { const result = await action(); if (result) setX(result); setDialog(null); } catch (e) { setError(procurementErrorMessage(e, errors)); } finally { setBusy(null); }
  }
  const back = <Link href="/purchase-orders" className={s.button}>{t("orders.back")}</Link>;
  if (loading) return <PageFrame title={t("orders.detailTitle")} action={back}><p className={s.muted}>{messages("loading.default")}</p></PageFrame>;
  if (!x) return <PageFrame title={t("orders.detailTitle")} action={back}><p role="alert" className={s.error}>{error || t("orders.notFound")}</p></PageFrame>;
  const taxed = Number(x.tax_rate) > 0;
  const step = (action: "approve" | "send", call: () => Promise<Order>) => x.actions.includes(action) &&
    <button type="button" className={`${s.button} ${s.primary}`} disabled={busy !== null} onClick={() => void run(action, call)}>{t(`orders.actions.${action}`)}</button>;

  return <PageFrame title={x.po_number} subtitle={x.supplier_name} action={back}>
    {error && <p role="alert" className={s.error}>{error}</p>}
    {x.status === "cancelled" && <p role="status" className={s.error}>{t("orders.cancelledHint", { reason: x.cancel_reason ?? "" })}</p>}
    {x.status === "closed" && x.close_reason && <p role="status" className={s.muted}>{t("orders.closedHint", { reason: x.close_reason })}</p>}
    <section className={s.panel}>
      <div className={s.actions} style={{ justifyContent: "space-between", marginBottom: 12 }}>
        <span className={s.actions}><OrderStatusBadge status={x.status} />
          {!["draft", "cancelled"].includes(x.status) && <span className={s.muted}>{t("orders.receivedPct", { pct: String(Number(x.received_pct)) })}</span>}</span>
        <span className={s.actions}>
          {(["ar", "en"] as const).map(lang => <button key={lang} type="button" className={s.button} disabled={busy !== null}
            onClick={() => void run(`pdf-${lang}`, () => downloadOrder(x.id, lang))}>{busy === `pdf-${lang}` ? t("preparing") : t(`download.${lang}`)}</button>)}
          {x.actions.includes("edit") && <Link href={`/purchase-orders/${x.id}/edit`} className={s.button}>{t("edit")}</Link>}
          {step("approve", () => approveOrder(x.id))}{step("send", () => sendOrder(x.id))}
          {x.actions.includes("receive") && <Link href={`/goods-receipts/new?supplier=${x.supplier_id}&order=${x.id}`} className={`${s.button} ${s.primary}`}>
            {t("orders.actions.receive")}</Link>}
          {x.actions.includes("close") && <button type="button" className={s.button} disabled={busy !== null} onClick={() => setDialog("close")}>{t("orders.actions.close")}</button>}
          {x.actions.includes("cancel") && <button type="button" className={`${s.button} ${s.danger}`} disabled={busy !== null} onClick={() => setDialog("cancel")}>{t("orders.actions.cancel")}</button>}
        </span>
      </div>
      {x.status === "draft" && <p className={s.muted} style={{ marginTop: 0 }}>{t("orders.draftHint")}</p>}
      <dl className={s.grid} style={{ margin: 0 }}>
        <Item label={t("orders.fields.order_date")}>{fmt.date(x.order_date)}</Item>
        <Item label={t("orders.fields.required_date")}>{x.required_date ? fmt.date(x.required_date) : "—"}</Item>
        <Item label={t("fields.supplier")}><Link href={`/suppliers/${x.supplier_id}`}>{x.supplier_name}</Link>
          {x.supplier_status && x.supplier_status !== "approved" && <div><SupplierStatusBadge status={x.supplier_status} /></div>}</Item>
        <Item label={t("orders.fields.attention")}>{x.attention ?? "—"}</Item>
        <Item label={t("orders.fields.supplier_quote_ref")}><bdi>{x.supplier_quote_ref ?? "—"}</bdi></Item>
        <Item label={t("orders.fields.currency")}>{currencies(x.currency)} · {taxed ? t("orders.withVat") : t("orders.noVat")}</Item>
        <Item label={t("orders.fields.payment_terms")}>{[x.payment_terms ? t(`paymentTerms.${x.payment_terms}`) : null, x.payment_terms_note].filter(Boolean).join(" — ") || "—"}</Item>
        <Item label={t("orders.fields.incoterm")}>{x.incoterm ? `${x.incoterm} — ${t(`incoterms.${x.incoterm}`)}` : "—"}</Item>
        <Item label={t("orders.fields.delivery_place")}>{x.delivery_place ?? "—"}</Item>
        <Item label={t("orders.approvedBy")}>{x.approved_by_name ? `${x.approved_by_name} — ${fmt.dateTime(x.approved_at!)}` : "—"}</Item>
      </dl>
      {x.subject && <p style={{ marginBottom: 0 }}><strong>{t("orders.fields.subject")}:</strong> {x.subject}</p>}
    </section>

    <section className={s.panel} aria-label={t("orders.sections.lines")}>
      <h2 style={{ marginTop: 0 }}>{t("orders.sections.lines")}</h2>
      <div className={s.tableWrap}><table className={s.table}>
        <thead><tr><th>#</th><th>{t("fields.description")}</th><th>{t("fields.quantity")}</th><th>{t("orders.columns.unitPrice")}</th><th>{t("orders.columns.amount")}</th>
          {x.status !== "draft" && <><th>{t("orders.columns.received")}</th><th>{t("orders.columns.remaining")}</th></>}</tr></thead>
        <tbody>{x.lines.map(l => <tr key={l.id}>
          <td>{l.line_no}</td>
          <td>{l.description}{l.notes && <div className={s.muted}>{l.notes}</div>}</td>
          <td><bdi>{fmt.quantity(l.quantity, unit(l.unit))}</bdi></td>
          <td><Money amount={l.unit_price} currency={x.currency} places={priceplaces(l.unit_price)} /></td>
          <td><Money amount={l.line_total} currency={x.currency} /></td>
          {x.status !== "draft" && <>
            <td><bdi>{fmt.quantity(x.line_received[l.id]?.received ?? "0", unit(l.unit))}</bdi></td>
            <td className={Number(x.line_received[l.id]?.remaining ?? 0) > 0 ? undefined : s.muted}><bdi>{fmt.quantity(x.line_received[l.id]?.remaining ?? l.quantity, unit(l.unit))}</bdi></td>
          </>}
        </tr>)}</tbody>
      </table></div>
      <dl className={s.grid} style={{ margin: "12px 0 0" }} aria-label={t("orders.sections.totals")}>
        <Item label={t("orders.totals.subtotal")}><Money amount={x.subtotal_amount} currency={x.currency} /></Item>
        {Number(x.discount_amount) > 0 && <Item label={t("orders.totals.discount")}><Money amount={x.discount_amount} currency={x.currency} /></Item>}
        <Item label={taxed ? t("orders.totals.vat", { rate: String(Number(x.tax_rate)) }) : t("orders.totals.noVat")}><Money amount={x.tax_amount} currency={x.currency} /></Item>
        <Item label={taxed ? t("orders.totals.totalWithVat") : t("orders.totals.total")}><strong><Money amount={x.total_amount} currency={x.currency} /></strong></Item>
      </dl>
    </section>

    {x.receipts.length > 0 && <section className={s.panel} aria-label={t("orders.sections.receipts")}>
      <h2 style={{ marginTop: 0 }}>{t("orders.sections.receipts")}</h2>
      <ul style={{ margin: 0, paddingInlineStart: 18 }}>{x.receipts.map(r => <li key={r.id}>
        <Link href={`/goods-receipts/${r.id}`}><bdi>{r.receipt_no}</bdi></Link> · {fmt.date(r.receipt_date)} · {t(`receiptStatuses.${r.status}`)}</li>)}</ul>
    </section>}
    {x.notes && <section className={s.panel}><p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{x.notes}</p></section>}
    <section className={s.panel} aria-label={t("historyTitle")}>
      <h2 style={{ marginTop: 0 }}>{t("historyTitle")}</h2>
      <ol className={s.timeline}>{x.history.map((e, i) => <li key={`${e.at}-${i}`}>
        <strong>{t.has(`orders.events.${e.action}`) ? t(`orders.events.${e.action}`) : e.action}</strong>
        <span className={s.muted}>{e.actor_name ?? "—"} · {fmt.dateTime(e.at)}</span>
        {e.reason && <span style={{ whiteSpace: "pre-wrap" }}>{e.reason}</span>}
      </li>)}</ol>
    </section>
    {dialog === "close" && <ReasonDialog title={t("orders.closeTitle")} description={t("orders.closeText")} confirmLabel={t("orders.actions.close")} busy={busy !== null}
      onClose={() => setDialog(null)} onConfirm={reason => void run("close", () => closeOrder(x.id, reason))} />}
    {dialog === "cancel" && <ReasonDialog title={t("orders.cancelTitle")} description={t("orders.cancelText")} confirmLabel={t("orders.actions.cancel")} danger
      busy={busy !== null} onClose={() => setDialog(null)} onConfirm={reason => void run("cancel", () => cancelOrder(x.id, reason))} />}
  </PageFrame>;
}
