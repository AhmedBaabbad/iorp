"use client";
import { NumericSpecInput } from "@/components/forms/NumericSpecInput";
import { formatThickness, thicknessFields } from "@/lib/spec-value";
import { customerDisplayName } from "@/lib/customer-name";
import type { Option } from "@/features/reference-directory/RecordSelect";
import { apiClient } from "@/lib/api-client";

import { TransportSelection, DirectorySelect, type TransportValues } from "@/features/reference-directory/DirectorySelect";
import { useLocale } from "next-intl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";

import { UnitSelect } from "@/components/forms/UnitSelect";
import { PageFrame } from "@/components/layout/page-frame";
import { grossKg, isWeightUnit, lineNet, totalNetKg, unchangedLegacyQuantity, type WeightLine } from "../weights";
import s from "@/features/production-demands/demands.module.css";
import { createShipment, getShipment, getShippingCustomers, getShippingProductionOrders, updateShipment } from "../api";
import { DECIMAL, shippingErrorMessage, todayIso } from "../shipping-errors";
import { DELIVERY_METHODS, type CustomerOption, type DeliveryMethod, type ProductionOrderOption, type ShipmentHeader, type ShipmentLineInput } from "../types";
import { MapLink } from "@/components/MapLink";
import { useListName } from "@/features/masterdata";
import { ListSelect } from "@/features/masterdata";

// A line as edited (numbers as typed): dimensions, quantity and unit, per-unit net and a read-only legacy net, and
// the production order (batch) it comes from.
type Line = WeightLine & { id?: string; description: string; width_mm: string; thickness_mm: string; production_order_id: string };
const EMPTY_LINE: Line = { description: "", width_mm: "", thickness_mm: "", quantity: "", unit: "roll", unit_net_weight: "", weight_unit: "kg", production_order_id: "" };
type Header = { [K in keyof Omit<ShipmentHeader, "notify_consignee" | "customer_id" | "driver_id" | "vehicle_id" | "carrier_id" | "driver_affiliation" | "customer_contact_id" | "delivery_site_id">]: string };
const EMPTY_HEADER: Header = { customer_name: "", customer_reference: "", consignee_name: "", consignee_phone: "", consignee_email: "", delivery_address: "",
  delivery_city: "", delivery_country: "", location_url: "", driver_name: "", driver_phone: "", driver_id_no: "", vehicle_plate: "", vehicle_type: "", carrier_name: "", tracking_no: "", notes: "" };

const blank = (v: string) => v.trim() || null;
// Weights in their own units, totalled in kilograms like the server and the delivery note.
const text = (v: string | null) => (v === null ? "" : String(Number(v)));

// A delivery note: create one, or edit it while it is a draft (shipmentId).
export function ShipmentForm({ shipmentId }: { shipmentId?: string }) {
  const t = useTranslations("shipping");
  const units = useTranslations("common.units.units");
  const unitLabel = (code: string) => units.has(code) ? units(code) : code;
  const errors = useTranslations("shipping.errors");
  const messages = useTranslations("messages");
  const router = useRouter();
  const editing = Boolean(shipmentId);
  const locale = useLocale();
  const ar=locale==="ar";
  const [transport,setTransport]=useState<TransportValues>({});
  const location = useTranslations("common.location");
  const cityName = useListName("city", key => key), countryName = useListName("country");
  const [site,setSite]=useState<string|null>(null);
  const [contact,setContact]=useState<string|null>(null);
  const [method, setMethod] = useState<DeliveryMethod>("factory_delivery");
  const [date, setDate] = useState(todayIso());
  const [registered, setRegistered] = useState(true);
  const [customerId, setCustomerId] = useState("");
  const defaultsCustomer = useRef("");
  const contactChanged = useRef(false);
  const siteChanged = useRef(false);
  const [query, setQuery] = useState("");
  const [customers, setCustomers] = useState<CustomerOption[]>([]);
  const [h, setH] = useState<Header>(EMPTY_HEADER);
  const [notify, setNotify] = useState(false);
  const [lines, setLines] = useState<Line[]>([{ ...EMPTY_LINE }]);
  const [gross, setGross] = useState("");
  const [grossUnit, setGrossUnit] = useState("kg");
  const [orderQuery, setOrderQuery] = useState("");
  const [orders, setOrders] = useState<ProductionOrderOption[]>([]);
  const [locked, setLocked] = useState(false);
  const [loading, setLoading] = useState(editing);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const selectSite = useCallback((id: string | null, row?: Option) => {
    setSite(id);
    setH(old => ({ ...old,
      delivery_address: String(row?.address ?? ""),
      delivery_city: String(row?.city_other || row?.city || ""),
      delivery_country: String(row?.country ?? ""),
      location_url: String(row?.location_url ?? ""),
    }));
  }, []);

  useEffect(() => {
    if (!shipmentId) return;
    let active = true;
    getShipment(shipmentId).then(x => {
      if (!active) return;
      defaultsCustomer.current=x.customer_id??"";
      setTransport({driver_id:x.driver_id,vehicle_id:x.vehicle_id,carrier_id:x.carrier_id,driver_affiliation:x.driver_affiliation});setSite(x.delivery_site_id??null);setContact(x.customer_contact_id??null);
      setMethod(x.delivery_method); setDate(x.shipment_date); setRegistered(Boolean(x.customer_id)); setCustomerId(x.customer_id ?? "");
      setH(Object.fromEntries(Object.keys(EMPTY_HEADER).map(k => [k, (x[k as keyof Header] as string | null) ?? ""])) as Header);
      setNotify(x.notify_consignee); setLocked(!x.actions.includes("edit"));
      setGross(text(x.gross_weight_kg ?? null)); setGrossUnit("kg");
      setLines(x.lines.map(l => ({ id: l.id, description: l.description, width_mm: text(l.width_mm), thickness_mm: formatThickness(l.thickness_mm, l.thickness_max_mm),
        quantity: text(l.quantity), unit: l.unit, unit_net_weight: text(l.unit_net_weight ?? null), weight_unit: l.weight_unit,
        ...(l.unit_net_weight == null ? { legacy_weight: l.weight, legacy_quantity: text(l.quantity), legacy_unit: l.unit, legacy_weight_unit: l.weight_unit } : {}),
        production_order_id: l.production_order_id ?? "" })));
      setOrders(x.lines.filter(l => l.production_order_id).map(l => ({ id: l.production_order_id!, number: l.production_order_no ?? "", product_type: "",
        status: "", planned_quantity: "", unit: "" })));
      if (x.customer_id) setCustomers([{ id: x.customer_id, customer_code: "", name: x.customer_name, phone: null, email: null, city: null }]);
    }).catch(e => { if (active) setError(shippingErrorMessage(e, errors)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [shipmentId, errors]);
  useEffect(() => {
    if (!registered) return;
    let active = true;
    const timer = setTimeout(() => { getShippingCustomers(query).then(v => { if (active) setCustomers(old => [...v, ...old.filter(o => o.id === customerId && !v.some(n => n.id === o.id))]); })
      .catch(() => undefined); }, 200);
    return () => { active = false; clearTimeout(timer); };
  }, [registered, query, customerId]);

  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      getShippingProductionOrders(orderQuery).then(found => {
        // keep the orders already chosen on a line in the list
        if (active) setOrders(old => [...found, ...old.filter(o => !found.some(n => n.id === o.id))]);
      }).catch(() => undefined);
    }, 200);
    return () => { active = false; clearTimeout(timer); };
  }, [orderQuery]);

  useEffect(() => {
    if (!registered || !customerId) { defaultsCustomer.current = ""; return; }
    if (defaultsCustomer.current === customerId) return;
    defaultsCustomer.current = customerId;
    let active = true;
    const base = "/shipping/directory/customers/"+customerId;
    Promise.all([apiClient<Option[]>(base+"/contacts"), apiClient<Option[]>(base+"/sites")]).then(([contacts, sites]) => {
      if (!active) return;
      const defaultContact = contacts.find(row => row.is_default && row.active !== false);
      const defaultSite = sites.find(row => row.is_default && row.active !== false);
      const siteContact = contacts.find(row => row.id === defaultSite?.contact_id && row.active !== false);
      if (!contactChanged.current) setContact(old => old ?? defaultContact?.id ?? siteContact?.id ?? null);
      if (!siteChanged.current && defaultSite) selectSite(defaultSite.id, defaultSite);
    }).catch(() => undefined);
    return () => { active = false; };
  }, [registered, customerId, selectSite]);

  const chosen = useMemo(() => customers.find(c => c.id === customerId) ?? null, [customers, customerId]);
  const set = (field: keyof Header, value: string) => setH(old => ({ ...old, [field]: value }));
  const setLine = (index: number, field: keyof Line, value: string) => setLines(old => old.map((l, i) => (i === index ? { ...l, [field]: value } : l)));
  const linesOk = lines.every(l => l.description.trim() && DECIMAL.test(l.quantity.trim()) && Number(l.quantity) > 0 && l.unit.trim()
    && [l.width_mm, l.unit_net_weight].every(v => !v.trim() || DECIMAL.test(v.trim()))
    && (isWeightUnit(l.unit) || Boolean(l.unit_net_weight.trim()) || unchangedLegacyQuantity(l))
    && (() => { try { const r = thicknessFields(l.thickness_mm); return r.thickness_mm === null || Number(r.thickness_mm) >= 0; } catch { return false; } })());
  const netTotal = totalNetKg(lines), grossTotal = grossKg(gross, grossUnit);
  const grossBelowNet = grossTotal !== null && grossTotal < netTotal;
  const valid = Boolean(date) && (registered ? Boolean(customerId) : Boolean(h.customer_name.trim())) && linesOk && (!gross.trim() || DECIMAL.test(gross.trim())) && !grossBelowNet;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid || busy || locked) return;
    setBusy(true); setError("");
    const header = Object.fromEntries(Object.entries(h).map(([k, v]) => [k, blank(v)])) as unknown as ShipmentHeader;
    const body = { ...header, ...transport, delivery_site_id:site,customer_contact_id:contact, delivery_method: method, shipment_date: date, notify_consignee: notify, customer_id: registered ? customerId : null,
      customer_name: registered ? blank(h.customer_name) : h.customer_name.trim(),
      gross_weight: blank(gross), gross_weight_unit: grossUnit,
      lines: lines.map<ShipmentLineInput>(l => ({ description: l.description.trim(), width_mm: blank(l.width_mm), ...thicknessFields(l.thickness_mm),
        ...(l.id ? { id: l.id } : {}), quantity: l.quantity.trim(), unit: l.unit,
        ...(!isWeightUnit(l.unit) ? { unit_net_weight: blank(l.unit_net_weight) } : {}),
        weight_unit: l.weight_unit, production_order_id: l.production_order_id || null })) };
    try {
      const saved = shipmentId ? await updateShipment(shipmentId, body) : await createShipment(body);
      router.push(`/shipments/${saved.id}`);
    } catch (e) { setError(shippingErrorMessage(e, errors, f => t(`fields.${f}`))); setBusy(false); }
  }

  const input = (field: keyof Header, extra: Record<string, unknown> = {}) =>
    <label className={s.field}>{t(`fields.${field}`)}<input value={h[field]} disabled={busy || locked} onChange={e => set(field, e.target.value)} {...extra} /></label>;
  const back = shipmentId ? `/shipments/${shipmentId}` : "/shipments";
  const title = editing ? t("editTitle") : t("createTitle");

  return <PageFrame title={title} subtitle={t("formSubtitle")} action={<Link href={back} className={s.button}>{t("back")}</Link>}>
    {loading ? <p className={s.muted}>{messages("loading.default")}</p> : <form onSubmit={submit} aria-label={title}>
      {locked && <p role="status" className={s.error}>{t("lockedHint")}</p>}
      <fieldset disabled={busy || locked} style={{ border: 0, padding: 0, margin: 0 }}>
        <section className={s.panel}>
          <h2 style={{ marginTop: 0 }}>{t("sections.basics")}</h2>
          <div className={s.grid}>
            <label className={s.field}>{t("fields.date")}<input type="date" required value={date} onChange={e => setDate(e.target.value)} /></label>
            <label className={s.field}>{t("fields.method")}
              <select value={method} onChange={e => setMethod(e.target.value as DeliveryMethod)}>
                {DELIVERY_METHODS.map(v => <option key={v} value={v}>{t(`methods.${v}`)}</option>)}
              </select>
            </label>
            {input("customer_reference", { maxLength: 80, dir: "ltr" })}
          </div>
          <p className={s.muted} style={{ marginBottom: 0 }}>{t(`methodHints.${method}`)}</p>
        </section>

        <section className={s.panel}>
          <h2 style={{ marginTop: 0 }}>{t("sections.customer")}</h2>
          <div className={s.actions} role="radiogroup" aria-label={t("sections.customer")} style={{ marginBottom: 12 }}>
            <label><input type="radio" checked={registered} onChange={() => setRegistered(true)} /> {t("registeredCustomer")}</label>
            <label><input type="radio" checked={!registered} onChange={() => { setRegistered(false); setCustomerId("");setSite(null);setContact(null); }} /> {t("namedCustomer")}</label>
          </div>
          <div className={s.grid}>
            {registered ? <>
              <label className={s.field}>{t("searchCustomer")}<input value={query} onChange={e => setQuery(e.target.value)} placeholder={t("searchCustomerPlaceholder")} /></label>
              <label className={s.field}>{t("fields.customer")}
                <select required value={customerId} onChange={e => {contactChanged.current=false;siteChanged.current=false;setCustomerId(e.target.value);setSite(null);setContact(null);setH(old=>({...old,customer_name:"",consignee_name:"",consignee_phone:"",consignee_email:"",delivery_address:"",delivery_country:"",delivery_city:"",location_url:""}));}}>
                  <option value="">{customers.length ? t("chooseCustomer") : t("noCustomers")}</option>
                  {customers.map(c => <option key={c.id} value={c.id}>{customerDisplayName(c, locale)}{c.customer_code ? ` — ${c.customer_code}` : ""}</option>)}
                </select>
              </label>
            </> : input("customer_name", { required: true, maxLength: 255 })}
          </div>
          {registered && chosen && (chosen.phone || chosen.email) && <p className={s.muted} style={{ marginBottom: 0 }}>
            {t("customerContacts", { phone: chosen.phone ?? "—", email: chosen.email ?? "—" })}</p>}
        </section>

        <section className={s.panel}>
          <h2 style={{ marginTop: 0 }}>{t("sections.recipient")}</h2>
          {registered&&customerId&&<><DirectorySelect key={`site-${customerId}`} path={`/shipping/directory/customers/${customerId}/sites`} value={site} label={ar?"موقع التسليم المحفوظ":"Saved delivery site"} onChange={(id,row)=>{siteChanged.current=true;selectSite(id||null,row);setContact(old=>old||(contactChanged.current?null:row?.contact_id)||null);}}/><DirectorySelect key={`contact-${customerId}`} path={`/shipping/directory/customers/${customerId}/contacts`} value={contact} label={ar?"جهة الاتصال المحفوظة":"Saved contact"} onChange={id=>{contactChanged.current=true;setContact(id||null);}}/></>}
          <div className={s.grid}>
            {input("consignee_name", { disabled:!!contact, maxLength: 255, placeholder: t("recipientPlaceholder") })}
            {input("consignee_phone", { disabled:!!contact, maxLength: 30, dir: "ltr", inputMode: "tel", placeholder: "05xxxxxxxx" })}
            {input("consignee_email", { disabled:!!contact, maxLength: 255, dir: "ltr", type: "email" })}
            <label className={s.field}>{location("country")}<ListSelect list="country" ariaLabel={location("country")} value={h.delivery_country || chosen?.country || ""}
              disabled={busy || locked || !!site} onChange={key=>setH(old=>({...old,delivery_country:key,delivery_city:""}))}/></label>
            <label className={s.field}>{t("fields.delivery_city")}{site?<input readOnly disabled value={h.delivery_city?cityName(h.delivery_city):""}/>:<ListSelect list="city" ariaLabel={t("fields.delivery_city")} value={h.delivery_city}
              parent={h.delivery_country || chosen?.country || null} disabled={busy || locked || !(h.delivery_country || chosen?.country)} onChange={key => set("delivery_city", key)} />}</label>
            {input("location_url", { disabled:!!site, maxLength: 500, dir: "ltr", type: "url", placeholder: "https://maps.google.com/…" })}
          </div>
          <label className={s.field}>{t("fields.delivery_address")}<textarea disabled={!!site} maxLength={1000} value={h.delivery_address} onChange={e => set("delivery_address", e.target.value)} /></label>
          <MapLink locationUrl={h.location_url} address={h.delivery_address} city={h.delivery_city ? cityName(h.delivery_city) : null} country={(h.delivery_country || customers.find(c=>c.id===customerId)?.country) ? countryName(h.delivery_country || customers.find(c=>c.id===customerId)?.country) : null} />
          <label style={{ display: "block", marginTop: 8 }}><input type="checkbox" checked={notify} onChange={e => setNotify(e.target.checked)} /> {t("fields.notify_consignee")}</label>
          <p className={s.muted} style={{ marginBottom: 0 }}>{t("notifyHint")}</p>
        </section>

        <section className={s.panel}>
          <h2 style={{ marginTop: 0 }}>{t("sections.transport")}</h2>
          <TransportSelection value={transport} onChange={setTransport} carrier={method==="carrier"}/>
          <div className={s.grid}>
            {method === "carrier" ? <>
              {input("carrier_name", { disabled:!!transport.carrier_id, maxLength: 200 })}
              {input("tracking_no", { maxLength: 80, dir: "ltr" })}
            </> : <>
              <label className={s.field}>{method === "pickup" ? t("fields.collector_name") : t("fields.driver_name")}
                <input disabled={!!transport.driver_id} value={h.driver_name} maxLength={200} onChange={e => set("driver_name", e.target.value)} /></label>
              {input("driver_phone", { disabled:!!transport.driver_id, maxLength: 30, dir: "ltr", inputMode: "tel" })}
              {method === "pickup" && input("driver_id_no", { disabled:!!transport.driver_id, maxLength: 40, dir: "ltr" })}
              {input("vehicle_plate", { disabled:!!transport.vehicle_id, maxLength: 40, placeholder: t("platePlaceholder") })}
              <label className={s.field}>{t("fields.vehicle_type")}  {/* MD-003: from the organization's vehicle types */}
                <ListSelect list="vehicle_type" value={h.vehicle_type} disabled={busy || locked || !!transport.vehicle_id} ariaLabel={t("fields.vehicle_type")}
                  onChange={key => set("vehicle_type", key)} /></label>
            </>}
          </div>
          <p className={s.muted} style={{ marginBottom: 0 }}>{t("transportHint")}</p>
        </section>

        <section className={s.panel} aria-label={t("sections.lines")}>
          <h2 style={{ marginTop: 0 }}>{t("sections.lines")}</h2>
          <div className={s.toolbar}>
            <label className={s.field}>{t("productionOrder.search")}
              <input type="search" value={orderQuery} placeholder={t("productionOrder.searchPlaceholder")} onChange={e => setOrderQuery(e.target.value)} /></label>
            <span className={s.muted}>{t("productionOrder.hint")}</span>
          </div>
          {lines.map((l, i) => <div key={i} className={s.panel} style={{ margin: "0 0 10px", padding: 14 }}>
            <div className={s.actions} style={{ justifyContent: "space-between", marginBottom: 8 }}>
              <strong>{t("lineNo", { no: String(i + 1) })}</strong>
              {lines.length > 1 && <button type="button" className={`${s.button} ${s.danger}`} onClick={() => setLines(old => old.filter((_, n) => n !== i))}>{t("removeLine")}</button>}
            </div>
            <div className={s.grid}>
              <label className={s.field} style={{ gridColumn: "1 / -1" }}>{t("lineFields.description")}
                <input required maxLength={255} value={l.description} onChange={e => setLine(i, "description", e.target.value)} /></label>
              {(["width_mm", "thickness_mm"] as const).map(field => <label key={field} className={s.field}>{t(`lineFields.${field}`)}
                <NumericSpecInput value={l[field]} allowsRange={field === "thickness_mm"} onValueChange={text => setLine(i, field, text)} /></label>)}
              <label className={s.field}>{t("lineFields.quantity")}
                <input required inputMode="decimal" dir="ltr" value={l.quantity} onChange={e => setLine(i, "quantity", e.target.value)} /></label>
              <label className={s.field}>{t("lineFields.unit")}
                <UnitSelect value={l.unit} onChange={v => setLines(old => old.map((row, n) => n === i ? { ...row, unit: v, ...(isWeightUnit(v) ? { unit_net_weight: "" } : {}) } : row))} ariaLabel={t("lineFields.unit")} /></label>
              {!isWeightUnit(l.unit) && <><label className={s.field}>{t("lineFields.unit_net_weight")}
                <input required={!unchangedLegacyQuantity(l)} inputMode="decimal" dir="ltr" value={l.unit_net_weight} onChange={e => setLine(i, "unit_net_weight", e.target.value)} /></label>
              <label className={s.field}>{t("lineFields.weight_unit")}
                <UnitSelect value={l.weight_unit} onChange={v => setLine(i, "weight_unit", v || "kg")} groups={["weight"]} ariaLabel={t("lineFields.weight_unit")} /></label></>}
              <div className={s.field}><span>{t("lineFields.net_weight")}</span><output aria-label={t("lineFields.net_weight")}><bdi dir="ltr">{lineNet(l) ? `${lineNet(l)!.value} ${unitLabel(lineNet(l)!.unit)}` : "—"}</bdi></output>
                {l.id && !isWeightUnit(l.unit) && !l.unit_net_weight.trim() && l.legacy_weight != null && unchangedLegacyQuantity(l) && <small>{t("legacyNetHint")}</small>}</div>
              <label className={s.field}>{t("lineFields.production_order")}
                <select value={l.production_order_id} onChange={e => setLine(i, "production_order_id", e.target.value)}>
                  <option value="">{t("productionOrder.none")}</option>
                  {orders.map(o => <option key={o.id} value={o.id}>{o.number}{o.product_type ? ` — ${o.product_type}` : ""}</option>)}
                </select></label>
            </div>
          </div>)}
          <div className={s.actions}>
            <button type="button" className={s.button} onClick={() => setLines(old => [...old, { ...EMPTY_LINE }])}>{t("addLine")}</button>
            <span className={s.muted}>{t("totalsPreview", { weight: String(netTotal) })}</span>
          </div>
          <div className={s.grid}>
            <label className={s.field}>{t("weights.gross")}<input inputMode="decimal" dir="ltr" value={gross} onChange={e => setGross(e.target.value)} /></label>
            <label className={s.field}>{t("weights.grossUnit")}<UnitSelect value={grossUnit} onChange={v => setGrossUnit(v || "kg")} groups={["weight"]} ariaLabel={t("weights.grossUnit")} /></label>
            <div className={s.field}><span>{t("weights.packaging")}</span><output aria-label={t("weights.packaging")}><bdi dir="ltr">{grossTotal === null ? "—" : `${Math.round((grossTotal - netTotal) * 1000) / 1000} ${unitLabel("kg")}`}</bdi></output></div>
          </div>
          {grossBelowNet && <p role="alert" className={s.error}>{errors("GROSS_BELOW_NET")}</p>}
          {!linesOk && <p className={s.muted}>{t("linesHint")}</p>}
        </section>

        <section className={s.panel}>
          <label className={s.field}>{t("fields.notes")}<textarea maxLength={4000} value={h.notes} onChange={e => set("notes", e.target.value)} /></label>
        </section>
      </fieldset>
      {error && <p role="alert" className={s.error}>{error}</p>}
      <div className={s.actions}>
        <button type="submit" className={`${s.button} ${s.primary}`} disabled={!valid || busy || locked}>{editing ? t("save") : t("create")}</button>
        <Link href={back} className={s.button}>{t("cancel")}</Link>
      </div>
    </form>}
  </PageFrame>;
}
