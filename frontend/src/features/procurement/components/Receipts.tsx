"use client";

import { TransportSelection, DriverAffiliation, type TransportValues } from "@/features/reference-directory/DirectorySelect";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";

import { UnitSelect } from "@/components/forms/UnitSelect";
import { PageFrame } from "@/components/layout/page-frame";
import { usePermission } from "@/features/auth/permission-hooks";
import { ReasonDialog } from "@/features/production-demands/reason-dialog";
import s from "@/features/production-demands/demands.module.css";
import { useFormatter } from "@/hooks/useFormatter";
import { PR } from "@/lib/procurement-permissions";
import { Q } from "@/lib/quality-permissions";
import {
  cancelReceipt, createReceipt, downloadReceiptNote, getMaterials, getOpenOrders, getProcurementSettings, getReceipt, getReceipts, getSupplierOptions,
  receiveReceipt, updateProcurementSettings, updateReceipt, type ReceiptFilters,
} from "../api";
import { DECIMAL, procurementErrorMessage, todayIso } from "../procurement-errors";
import { RECEIPT_STATUSES, type LotStatus, type Material, type OpenOrder, type Receipt, type ReceiptInput, type ReceiptListItem, type ReceiptStatus,
  type SupplierOption } from "../types";
import { SupplierStatusBadge } from "./Suppliers";

const STATUS_CLASS: Record<ReceiptStatus, string> = { draft: "", received: s.green, cancelled: s.cancelled };

const LOT_CLASS: Record<LotStatus, string> = { not_required: "", awaiting: s.high, inspecting: s.blue, released: s.green, partly_released: s.overdue,
  rejected: s.cancelled };

export function LotStatusBadge({ status }: { status: LotStatus }) {
  const t = useTranslations("procurement.lotStatuses");
  return <span className={`${s.badge} ${LOT_CLASS[status]}`}>{t(status)}</span>;
}

export function ReceiptStatusBadge({ status }: { status: ReceiptStatus }) {
  const t = useTranslations("procurement.receiptStatuses");
  return <span className={`${s.badge} ${STATUS_CLASS[status]}`}>{t(status)}</span>;
}

function Item({ label, children }: { label: string; children: ReactNode }) {
  return <div><dt className={s.muted}>{label}</dt><dd style={{ margin: "4px 0 0", overflowWrap: "anywhere" }}>{children}</dd></div>;
}

// "استلام المواد": deliveries received from suppliers, with the supplier's references and lots.
export function ReceiptsList() {
  const t = useTranslations("procurement");
  const errors = useTranslations("procurement.errors");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const units = useTranslations("common.units.units");
  const unit = (code: string) => (units.has(code) ? units(code) : code);
  const canCreate = usePermission(PR.RECEIPTS_CREATE);
  const [filters, setFilters] = useState<Required<Omit<ReceiptFilters, "supplier_id">>>({ status: "", date_from: "", date_to: "", search: "" });
  const [rows, setRows] = useState<ReceiptListItem[] | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setError("");
    try { setRows(await getReceipts(filters)); } catch (e) { setError(procurementErrorMessage(e, errors)); }
  }, [filters, errors]);
  useEffect(() => { const timer = setTimeout(() => void load(), 200); return () => clearTimeout(timer); }, [load]);
  const set = (field: keyof typeof filters, value: string) => setFilters(old => ({ ...old, [field]: value }));

  return <PageFrame title={t("receipts.title")} subtitle={t("receipts.subtitle")}
    action={canCreate ? <Link href="/goods-receipts/new" className={`${s.button} ${s.primary}`}>{t("receipts.new")}</Link> : undefined}>
    <section className={s.toolbar} aria-label={t("filtersAria")}>
      <label className={s.field}>{t("search")}<input type="search" value={filters.search} placeholder={t("receipts.searchPlaceholder")} onChange={e => set("search", e.target.value)} /></label>
      <label className={s.field}>{t("fields.status")}
        <select value={filters.status} onChange={e => set("status", e.target.value)}>
          <option value="">{t("all")}</option>{RECEIPT_STATUSES.map(v => <option key={v} value={v}>{t(`receiptStatuses.${v}`)}</option>)}</select></label>
      <label className={s.field}>{t("dateFrom")}<input type="date" value={filters.date_from} onChange={e => set("date_from", e.target.value)} /></label>
      <label className={s.field}>{t("dateTo")}<input type="date" value={filters.date_to} onChange={e => set("date_to", e.target.value)} /></label>
    </section>
    {error && <p role="alert" className={s.error}>{error}</p>}
    {rows === null && !error && <p className={s.muted}>{messages("loading.default")}</p>}
    {rows?.length === 0 && <section className={s.panel}><h2 style={{ marginTop: 0 }}>{t("receipts.empty")}</h2><p className={s.muted} style={{ margin: 0 }}>{t("receipts.emptyHint")}</p></section>}
    {rows && rows.length > 0 && <section className={s.panel}><div className={s.tableWrap}><table className={s.table} aria-label={t("receipts.title")}>
      <thead><tr>{["number", "date", "supplier", "references", "quantity", "status"].map(c => <th key={c}>{t(`fields.${c}`)}</th>)}</tr></thead>
      <tbody>{rows.map(r => <tr key={r.id}>
        <td><Link href={`/goods-receipts/${r.id}`}><bdi>{r.receipt_no}</bdi></Link></td>
        <td>{fmt.date(r.receipt_date)}</td>
        <td>{r.supplier_name}</td>
        <td><bdi>{[r.supplier_delivery_no, r.supplier_invoice_no, r.po_number ?? r.purchase_reference].filter(Boolean).join(" · ") || "—"}</bdi></td>
        <td><bdi>{r.quantities.map(q => fmt.quantity(q.quantity, unit(q.unit))).join(" · ") || "—"}</bdi>
          {r.lots_pending > 0 && <div className={s.error}>{t("receipts.awaitingQuality", { count: String(r.lots_pending) })}</div>}</td>
        <td><ReceiptStatusBadge status={r.status} /></td>
      </tr>)}</tbody>
    </table></div></section>}
    <PrefixSettings />
  </PageFrame>;
}

function PrefixSettings() {
  const t = useTranslations("procurement.settings");
  const errors = useTranslations("procurement.errors");
  const canEdit = usePermission(PR.SETTINGS_UPDATE);
  const [prefix, setPrefix] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  useEffect(() => { if (canEdit) getProcurementSettings().then(v => setPrefix(v.receipt_prefix)).catch(() => setPrefix(null)); }, [canEdit]);
  if (!canEdit || prefix === null) return null;
  return <form className={s.panel} aria-label={t("title")} onSubmit={async e => {
    e.preventDefault(); setMessage("");
    try { setPrefix((await updateProcurementSettings({ receipt_prefix: prefix })).receipt_prefix); setMessage(t("saved")); }
    catch (err) { setMessage(procurementErrorMessage(err, errors)); }
  }}>
    <h2 style={{ marginTop: 0 }}>{t("title")}</h2>
    <div className={s.toolbar} style={{ marginBottom: 0 }}>
      <label className={s.field}>{t("prefix")}<input dir="ltr" required maxLength={20} pattern="[A-Za-z0-9_\-/]+" value={prefix} onChange={e => setPrefix(e.target.value)} /></label>
      <button type="submit" className={s.button}>{t("save")}</button>
      <span className={s.muted}>{t("example", { number: `${prefix}${new Date().getFullYear()}-0001` })}</span>
      {message && <span role="status" className={s.muted}>{message}</span>}
    </div>
  </form>;
}

type Line = { material_id: string; description: string; supplier_lot: string; quantity: string; unit: string; package_count: string; weight: string;
  weight_unit: string; po_line_id: string };
const EMPTY_LINE: Line = { material_id: "", description: "", supplier_lot: "", quantity: "", unit: "kg", package_count: "", weight: "", weight_unit: "kg",
  po_line_id: "" };
type Header = { [K in "supplier_delivery_no" | "supplier_invoice_no" | "purchase_reference" | "vehicle_plate" | "driver_name" | "notes"]: string };
const EMPTY_HEADER: Header = { supplier_delivery_no: "", supplier_invoice_no: "", purchase_reference: "", vehicle_plate: "", driver_name: "", notes: "" };
const blank = (v: string) => v.trim() || null;
const text = (v: string | null) => (v === null ? "" : String(Number(v)));

// A goods receipt: record a delivery (draft), or edit it until it is received. It may deliver against a purchase order
// (PROC-003): its lines are then filled with what each order line still expects.
export function ReceiptForm({ receiptId, supplierId, orderId }: { receiptId?: string; supplierId?: string; orderId?: string }) {
  const t = useTranslations("procurement");
  const errors = useTranslations("procurement.errors");
  const messages = useTranslations("messages");
  const units = useTranslations("common.units.units");
  const unit = (code: string) => (units.has(code) ? units(code) : code);
  const router = useRouter();
  const [supplier, setSupplier] = useState(supplierId ?? "");
  const [query, setQuery] = useState("");
  const [suppliers, setSuppliers] = useState<SupplierOption[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [date, setDate] = useState(todayIso());
  const [h, setH] = useState<Header>(EMPTY_HEADER);
  const [transport,setTransport]=useState<TransportValues>({});
  const [lines, setLines] = useState<Line[]>([{ ...EMPTY_LINE }]);
  const [order, setOrder] = useState(orderId ?? "");
  const [orders, setOrders] = useState<OpenOrder[]>([]);
  const [prefilled, setPrefilled] = useState(!orderId);
  const [loading, setLoading] = useState(Boolean(receiptId));
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
    if (!supplier) { setOrders([]); return; }
    let active = true;
    getOpenOrders(supplier).then(found => { if (active) setOrders(found); }).catch(() => { if (active) setOrders([]); });
    return () => { active = false; };
  }, [supplier]);
  const fillFrom = useCallback((chosen: OpenOrder) => {
    const open = chosen.lines.filter(l => Number(l.remaining) > 0);
    setLines(open.length ? open.map(l => ({ ...EMPTY_LINE, material_id: l.material_id ?? "", description: l.material_id ? "" : l.description,
      quantity: String(Number(l.remaining)), unit: l.unit, po_line_id: l.id })) : [{ ...EMPTY_LINE }]);
  }, []);
  useEffect(() => {  // opened from an order (?order=<id>): its remaining lines, once
    if (prefilled) return;
    const chosen = orders.find(o => o.id === order);
    if (chosen) { fillFrom(chosen); setPrefilled(true); }
  }, [orders, order, prefilled, fillFrom]);
  function chooseOrder(id: string) {
    setOrder(id);
    const chosen = orders.find(o => o.id === id);
    if (chosen) fillFrom(chosen);
    else setLines(old => old.map(l => ({ ...l, po_line_id: "" })));
  }
  useEffect(() => {
    if (!receiptId) return;
    let active = true;
    getReceipt(receiptId).then(r => {
      if (!active) return;
      setTransport({driver_id:r.driver_id,vehicle_id:r.vehicle_id,driver_affiliation:r.driver_affiliation});
      setSupplier(r.supplier_id); setDate(r.receipt_date); setOrder(r.purchase_order_id ?? "");
      setSuppliers(old => [...old, { id: r.supplier_id, supplier_code: "", name: r.supplier_name, status: r.supplier_status ?? "approved" }]);
      setH(Object.fromEntries(Object.keys(EMPTY_HEADER).map(k => [k, (r[k as keyof Header] as string | null) ?? ""])) as Header);
      setLines(r.lines.map(l => ({ material_id: l.material_id ?? "", description: l.material_id ? "" : l.description, supplier_lot: l.supplier_lot ?? "",
        quantity: text(l.quantity), unit: l.unit, package_count: l.package_count === null ? "" : String(l.package_count), weight: text(l.weight), weight_unit: l.weight_unit,
        po_line_id: l.po_line_id ?? "" })));
    }).catch(e => { if (active) setError(procurementErrorMessage(e, errors)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [receiptId, errors]);

  const byId = useMemo(() => new Map(materials.map(m => [m.id, m])), [materials]);
  const setLine = (i: number, field: keyof Line, value: string) => setLines(old => old.map((l, n) => {
    if (n !== i) return l;
    const next = { ...l, [field]: value };
    if (field === "material_id" && byId.get(value)) next.unit = byId.get(value)!.unit;  // the material's default unit
    return next;
  }));
  const linesOk = lines.every(l => (l.material_id || l.description.trim()) && DECIMAL.test(l.quantity.trim()) && Number(l.quantity) > 0 && l.unit
    && (!l.weight.trim() || DECIMAL.test(l.weight.trim())) && (!l.package_count.trim() || /^\d+$/.test(l.package_count.trim())));
  const valid = Boolean(supplier && date) && linesOk;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid || busy) return;
    setBusy(true); setError("");
    const body: ReceiptInput = { ...transport, supplier_id: supplier, receipt_date: date, ...(Object.fromEntries(Object.entries(h).map(([k, v]) => [k, blank(v)])) as Record<keyof Header, string | null>),
      purchase_order_id: order || null,
      lines: lines.map(l => ({ material_id: l.material_id || null, description: blank(l.description), supplier_lot: blank(l.supplier_lot), quantity: l.quantity.trim(),
        unit: l.unit, package_count: l.package_count.trim() ? Number(l.package_count) : null, weight: blank(l.weight), weight_unit: l.weight_unit, notes: null,
        po_line_id: order && l.po_line_id ? l.po_line_id : null })) };
    try {
      const saved = receiptId ? await updateReceipt(receiptId, body) : await createReceipt(body);
      router.push(`/goods-receipts/${saved.id}`);
    } catch (e) { setError(procurementErrorMessage(e, errors)); setBusy(false); }
  }
  const input = (field: keyof Header, extra: Record<string, unknown> = {}) =>
    <label className={s.field}>{t(`fields.${field}`)}<input value={h[field]} onChange={e => setH(old => ({ ...old, [field]: e.target.value }))} {...extra} /></label>;
  const title = receiptId ? t("receipts.editTitle") : t("receipts.createTitle");
  const back = receiptId ? `/goods-receipts/${receiptId}` : orderId ? `/purchase-orders/${orderId}` : "/goods-receipts";
  const chosen = suppliers.find(o => o.id === supplier);

  return <PageFrame title={title} subtitle={t("receipts.formSubtitle")} action={<Link href={back} className={s.button}>{t("back")}</Link>}>
    {loading ? <p className={s.muted}>{messages("loading.default")}</p> : <form onSubmit={submit} aria-label={title}>
      <fieldset disabled={busy} style={{ border: 0, padding: 0, margin: 0 }}>
        <section className={s.panel}>
          <div className={s.grid}>
            <label className={s.field}>{t("receipts.findSupplier")}<input value={query} placeholder={t("suppliers.searchPlaceholder")} onChange={e => setQuery(e.target.value)} /></label>
            <label className={s.field}>{t("fields.supplier")}
              <select required value={supplier} onChange={e => { setSupplier(e.target.value); setOrder(""); }}>
                <option value="">{t("receipts.chooseSupplier")}</option>
                {suppliers.map(o => <option key={o.id} value={o.id}>{o.name}{o.supplier_code ? ` — ${o.supplier_code}` : ""}</option>)}</select></label>
            <label className={s.field}>{t("fields.date")}<input type="date" required value={date} onChange={e => setDate(e.target.value)} /></label>
            {(orders.length > 0 || order) && <label className={s.field}>{t("receipts.purchaseOrder")}
              <select value={order} onChange={e => chooseOrder(e.target.value)}>
                <option value="">{t("receipts.noOrder")}</option>
                {orders.map(o => <option key={o.id} value={o.id}>{o.po_number}</option>)}</select></label>}
            {input("supplier_delivery_no", { maxLength: 80, dir: "ltr" })}
            {input("supplier_invoice_no", { maxLength: 80, dir: "ltr" })}
            {!order && input("purchase_reference", { maxLength: 80, dir: "ltr" })}
            {input("vehicle_plate", { maxLength: 40 })}
            <TransportSelection value={transport} onChange={setTransport}/>{input("driver_name", { maxLength: 200, disabled:!!transport.driver_id })}
          </div>
          {chosen && chosen.status !== "approved" && <p className={s.error} role="status" style={{ marginBottom: 0 }}>
            {t("receipts.supplierNotApproved")} <SupplierStatusBadge status={chosen.status} /></p>}
        </section>
        <section className={s.panel} aria-label={t("receipts.lines")}>
          <h2 style={{ marginTop: 0 }}>{t("receipts.lines")}</h2>
          {order && <p className={s.muted} style={{ marginTop: 0 }}>{t("receipts.fromOrderHint")}</p>}
          {lines.map((l, i) => <div key={i} className={s.panel} style={{ margin: "0 0 10px", padding: 14 }}>
            <div className={s.actions} style={{ justifyContent: "space-between", marginBottom: 8 }}>
              <strong>{t("receipts.lineNo", { no: String(i + 1) })}{order && l.po_line_id && <span className={s.muted}> · {t("receipts.orderLine", {
                no: String(orders.find(o => o.id === order)?.lines.find(x => x.id === l.po_line_id)?.line_no ?? "") })}</span>}</strong>
              {lines.length > 1 && <button type="button" className={`${s.button} ${s.danger}`} onClick={() => setLines(old => old.filter((_, n) => n !== i))}>{t("remove")}</button>}
            </div>
            <div className={s.grid}>
              <label className={s.field}>{t("fields.material")}
                <select value={l.material_id} onChange={e => setLine(i, "material_id", e.target.value)}>
                  <option value="">{t("receipts.otherItem")}</option>{materials.map(m => <option key={m.id} value={m.id}>{m.name} — {m.material_code}</option>)}</select></label>
              {!l.material_id && <label className={s.field}>{t("fields.description")}<input maxLength={255} value={l.description} onChange={e => setLine(i, "description", e.target.value)} /></label>}
              <label className={s.field}>{t("fields.supplier_lot")}<input dir="ltr" maxLength={80} value={l.supplier_lot} onChange={e => setLine(i, "supplier_lot", e.target.value)} /></label>
              <label className={s.field}>{t("fields.quantity")}<input required inputMode="decimal" dir="ltr" value={l.quantity} onChange={e => setLine(i, "quantity", e.target.value)} /></label>
              <label className={s.field}>{t("fields.unit")}{order && l.po_line_id ? <input value={unit(l.unit)} readOnly aria-label={t("fields.unit")} />
                : <UnitSelect value={l.unit} onChange={u => setLine(i, "unit", u)} ariaLabel={t("fields.unit")} />}</label>
              <label className={s.field}>{t("fields.package_count")}<input inputMode="numeric" dir="ltr" value={l.package_count} onChange={e => setLine(i, "package_count", e.target.value)} /></label>
              <label className={s.field}>{t("fields.weight")}<input inputMode="decimal" dir="ltr" value={l.weight} onChange={e => setLine(i, "weight", e.target.value)} /></label>
              <label className={s.field}>{t("fields.weight_unit")}
                <UnitSelect value={l.weight_unit} onChange={u => setLine(i, "weight_unit", u || "kg")} groups={["weight"]} ariaLabel={t("fields.weight_unit")} /></label>
            </div>
            {l.material_id && byId.get(l.material_id)?.inspection_required && <p className={s.muted} style={{ marginBottom: 0 }}>{t("receipts.willInspect")}</p>}
          </div>)}
          <button type="button" className={s.button} onClick={() => setLines(old => [...old, { ...EMPTY_LINE }])}>{t("receipts.addLine")}</button>
          {!linesOk && <p className={s.muted}>{t("receipts.linesHint")}</p>}
        </section>
        <section className={s.panel}>
          <label className={s.field}>{t("fields.notes")}<textarea maxLength={4000} value={h.notes} onChange={e => setH(old => ({ ...old, notes: e.target.value }))} /></label>
        </section>
      </fieldset>
      {error && <p role="alert" className={s.error}>{error}</p>}
      <div className={s.actions}>
        <button type="submit" className={`${s.button} ${s.primary}`} disabled={!valid || busy}>{receiptId ? t("save") : t("receipts.create")}</button>
        <Link href={back} className={s.button}>{t("cancel")}</Link>
      </div>
    </form>}
  </PageFrame>;
}

// One goods receipt: supplier and references, the lots received, the next step, the PDF and the history.
export function ReceiptDetail({ receiptId }: { receiptId: string }) {
  const t = useTranslations("procurement");
  const errors = useTranslations("procurement.errors");
  const messages = useTranslations("messages");
  const fmt = useFormatter();
  const units = useTranslations("common.units.units");
  const unit = (code: string) => (units.has(code) ? units(code) : code);
  const canNcr = usePermission(Q.NCR_CREATE);
  const [x, setX] = useState<Receipt | null>(null);
  const [loading, setLoading] = useState(true);
  const [cancelling, setCancelling] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try { setX(await getReceipt(receiptId)); } catch (e) { setError(procurementErrorMessage(e, errors)); } finally { setLoading(false); }
  }, [receiptId, errors]);
  useEffect(() => { void load(); }, [load]);
  async function run(key: string, action: () => Promise<Receipt | void>) {
    setBusy(key); setError("");
    try { const result = await action(); if (result) setX(result); setCancelling(false); } catch (e) { setError(procurementErrorMessage(e, errors)); } finally { setBusy(null); }
  }
  const back = <Link href="/goods-receipts" className={s.button}>{t("receipts.back")}</Link>;
  if (loading) return <PageFrame title={t("receipts.detailTitle")} action={back}><p className={s.muted}>{messages("loading.default")}</p></PageFrame>;
  if (!x) return <PageFrame title={t("receipts.detailTitle")} action={back}><p role="alert" className={s.error}>{error || t("receipts.notFound")}</p></PageFrame>;
  const ncrLink = (lot: string | null, item: string) => `/non-conformance-reports/new?supplier=${x.supplier_id}&reference=${encodeURIComponent(
    [x.receipt_no, lot].filter(Boolean).join(" / "))}&item=${encodeURIComponent(item)}`;

  return <PageFrame title={x.receipt_no} subtitle={x.supplier_name} action={back}>
    {error && <p role="alert" className={s.error}>{error}</p>}
    {x.status === "cancelled" && <p role="status" className={s.error}>{t("receipts.cancelledHint", { reason: x.cancel_reason ?? "" })}</p>}
    <section className={s.panel}>
      <div className={s.actions} style={{ justifyContent: "space-between", marginBottom: 12 }}>
        <ReceiptStatusBadge status={x.status} />
        <span className={s.actions}>
          {(["ar", "en"] as const).map(lang => <button key={lang} type="button" className={s.button} disabled={busy !== null}
            onClick={() => void run(`pdf-${lang}`, () => downloadReceiptNote(x.id, lang))}>{busy === `pdf-${lang}` ? t("preparing") : t(`download.${lang}`)}</button>)}
          {x.actions.includes("edit") && <Link href={`/goods-receipts/${x.id}/edit`} className={s.button}>{t("edit")}</Link>}
          {x.actions.includes("receive") && <button type="button" className={`${s.button} ${s.primary}`} disabled={busy !== null}
            onClick={() => void run("receive", () => receiveReceipt(x.id))}>{t("receipts.receive")}</button>}
          {x.actions.includes("cancel") && <button type="button" className={`${s.button} ${s.danger}`} disabled={busy !== null} onClick={() => setCancelling(true)}>{t("receipts.cancel")}</button>}
        </span>
      </div>
      <dl className={s.grid} style={{ margin: 0 }}>
        <Item label={t("fields.date")}>{fmt.date(x.receipt_date)}</Item>
        <Item label={t("fields.supplier")}><Link href={`/suppliers/${x.supplier_id}`}>{x.supplier_name}</Link>
          {x.supplier_status && x.supplier_status !== "approved" && <div><SupplierStatusBadge status={x.supplier_status} /></div>}</Item>
        <Item label={t("fields.supplier_delivery_no")}><bdi>{x.supplier_delivery_no ?? "—"}</bdi></Item>
        <Item label={t("fields.supplier_invoice_no")}><bdi>{x.supplier_invoice_no ?? "—"}</bdi></Item>
        <Item label={t("fields.purchase_reference")}>{x.purchase_order_id ? <Link href={`/purchase-orders/${x.purchase_order_id}`}><bdi>{x.po_number}</bdi></Link>
          : <bdi>{x.purchase_reference ?? "—"}</bdi>}</Item>
        <Item label={t("fields.vehicle_plate")}><bdi>{[x.vehicle_plate, x.driver_name].filter(Boolean).join(" — ") || "—"}</bdi> <DriverAffiliation value={x.driver_affiliation}/></Item>
        <Item label={t("receipts.receivedBy")}>{x.received_by_name ? `${x.received_by_name} — ${fmt.dateTime(x.received_at!)}` : "—"}</Item>
      </dl>
    </section>
    <section className={s.panel} aria-label={t("receipts.lines")}>
      <h2 style={{ marginTop: 0 }}>{t("receipts.lines")}</h2>
      <div className={s.tableWrap}><table className={s.table}>
        <thead><tr><th>#</th>{["material", "supplier_lot", "quantity", "package_count", "weight", "quality"].map(c => <th key={c}>{t(`fields.${c}`)}</th>)}<th /></tr></thead>
        <tbody>{x.lines.map(l => <tr key={l.id}>
          <td>{l.line_no}</td>
          <td>{l.description}</td>
          <td><bdi dir="ltr">{l.supplier_lot ?? "—"}</bdi></td>
          <td><bdi>{fmt.quantity(l.quantity, unit(l.unit))}</bdi></td>
          <td>{l.package_count ?? "—"}</td>
          <td><bdi>{l.weight ? fmt.quantity(l.weight, unit(l.weight_unit)) : "—"}</bdi></td>
          <td>{x.status === "received" && x.line_quality[l.id] ? <>
            <LotStatusBadge status={x.line_quality[l.id].status} />
            {x.line_quality[l.id].inspection && <div><Link href={`/quality-checks/${x.line_quality[l.id].inspection!.id}`}>
              <bdi>{x.line_quality[l.id].inspection!.inspection_code}</bdi></Link></div>}
          </> : l.inspection_required ? <span className={s.muted}>{t("receipts.inspected")}</span> : "—"}</td>
          <td>{canNcr && x.status === "received" && <Link href={ncrLink(l.supplier_lot, l.description)} className={s.button}>{t("receipts.raiseNcr")}</Link>}</td>
        </tr>)}</tbody>
      </table></div>
      <p className={s.muted} style={{ marginBottom: 0 }}>{t("receipts.totals", { quantities: x.quantities.map(q => fmt.quantity(q.quantity, unit(q.unit))).join(" · ") || "—",
        weight: x.weight_kg ? fmt.quantity(x.weight_kg, unit("kg")) : "—" })}</p>
      {x.inspection_lines > 0 && <p className={s.muted} style={{ marginBottom: 0 }}>{t("receipts.inspectionNote")}</p>}
    </section>
    {x.notes && <section className={s.panel}><p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{x.notes}</p></section>}
    <section className={s.panel} aria-label={t("historyTitle")}>
      <h2 style={{ marginTop: 0 }}>{t("historyTitle")}</h2>
      <ol className={s.timeline}>{x.history.map((e, i) => <li key={`${e.at}-${i}`}>
        <strong>{t.has(`events.${e.action}`) ? t(`events.${e.action}`) : e.action}</strong>
        <span className={s.muted}>{e.actor_name ?? "—"} · {fmt.dateTime(e.at)}</span>
        {e.reason && <span style={{ whiteSpace: "pre-wrap" }}>{e.reason}</span>}
      </li>)}</ol>
    </section>
    {cancelling && <ReasonDialog title={t("receipts.cancelTitle")} description={t("receipts.cancelText")} confirmLabel={t("receipts.cancel")} danger busy={busy !== null}
      onClose={() => setCancelling(false)} onConfirm={reason => void run("cancel", () => cancelReceipt(x.id, reason))} />}
  </PageFrame>;
}
