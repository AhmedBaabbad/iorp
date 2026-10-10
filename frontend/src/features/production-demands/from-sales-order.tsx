"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import { useProductName } from "@/features/masterdata";
import { SpecList } from "@/features/commercial-orders/components/sales-lifecycle";
import { useFormatter } from "@/hooks/useFormatter";
import { demandsApi, type Customer, type DemandPriority, type SalesOrderOption } from "./api";
import { ErrorMessage, errorKey, priorities } from "./shared";
import s from "./demands.module.css";

/**
 * A production demand from a confirmed sales order (SALES-001): choose the order, then how much of each line goes to
 * production now. A line never takes more than the order still has; the rest stays for a later demand. The lines keep the
 * order's product, specification and unit. The form's transfer key makes a repeated submit return the same demand.
 */
export function DemandFromSalesOrder() {
  const t = useTranslations("production.demands");
  const tf = useTranslations("production.demands.fromSalesOrder");
  const units = useTranslations("common.units.units");
  const unit = (code: string) => (units.has(code) ? units(code) : code);
  const fmt = useFormatter();
  const productName = useProductName();
  const router = useRouter();
  const params = useSearchParams();
  const [search, setSearch] = useState("");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerId, setCustomerId] = useState(params.get("customer") ?? "");
  const [orders, setOrders] = useState<SalesOrderOption[]>([]);
  const [orderId, setOrderId] = useState(params.get("sales_order") ?? "");
  const [quantities, setQuantities] = useState<Record<string, string>>({});
  const [delivery, setDelivery] = useState("");
  const [priority, setPriority] = useState<DemandPriority>("normal");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [loadingOrders, setLoadingOrders] = useState(false);
  const [error, setError] = useState("");
  const transferKey = useMemo(() => crypto.randomUUID(), []);

  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => demandsApi.customers(search).then((v) => { if (active) setCustomers(v); })
      .catch((e) => { if (active) setError(errorKey(e)); }), 200);
    return () => { active = false; clearTimeout(timer); };
  }, [search]);

  useEffect(() => {
    let active = true;
    setOrders([]);
    if (!customerId) return;
    setLoadingOrders(true);
    demandsApi.salesOrders(customerId).then((v) => { if (active) setOrders(v); })
      .catch((e) => { if (active) setError(errorKey(e)); }).finally(() => { if (active) setLoadingOrders(false); });
    return () => { active = false; };
  }, [customerId]);

  const order = orders.find((o) => o.id === orderId) ?? null;
  useEffect(() => {
    // Every line starts with all that remains; the planner lowers it to send part now.
    setQuantities(order ? Object.fromEntries(order.lines.map((l) => [l.id, Number(l.remaining_quantity) > 0 ? String(Number(l.remaining_quantity)) : ""])) : {});
    setDelivery(order?.requested_delivery_date ? order.requested_delivery_date.slice(0, 10) : "");
  }, [order?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (!order) { setError("sales_order_required"); return; }
    const lines = order.lines.filter((l) => Number(quantities[l.id] || 0) > 0)
      .map((l) => ({ order_item_id: l.id, quantity: quantities[l.id] }));
    if (!lines.length) { setError("items_required"); return; }
    if (order.lines.some((l) => Number(quantities[l.id] || 0) > Number(l.remaining_quantity))) { setError("quantity_exceeds_remaining"); return; }
    setBusy(true);
    try {
      const demand = await demandsApi.fromSalesOrder({ sales_order_id: order.id, transfer_key: transferKey, lines,
        requested_delivery_date: delivery || null, priority, notes: notes || null });
      router.push(`/production/demands/${demand.id}`);
    } catch (e) { setError(errorKey(e)); setBusy(false); }
  }

  const customerOptions = customers.some((c) => c.id === customerId) || !customerId ? customers
    : [{ id: customerId, code: "", name: tf("selectedCustomer") }, ...customers];

  return (
    <form onSubmit={submit}>
      <ErrorMessage code={error} />
      <fieldset disabled={busy} className={s.panel}>
        <legend>{tf("title")}</legend>
        <p className={s.muted} style={{ marginTop: 0 }}>{tf("hint")}</p>
        <div className={s.grid}>
          <label className={s.field}>{t("searchCustomer")}<input value={search} onChange={(e) => setSearch(e.target.value)} /></label>
          <label className={s.field}>{t("customer")}
            <select required value={customerId} onChange={(e) => { setCustomerId(e.target.value); setOrderId(""); }}>
              <option value="">{t("selectCustomer")}</option>
              {customerOptions.map((c) => <option key={c.id} value={c.id}>{c.code ? `${c.code} · ` : ""}{c.name}</option>)}
            </select>
          </label>
          {customerId && (
            <label className={s.field}>{tf("salesOrder")}
              <select required value={orderId} onChange={(e) => setOrderId(e.target.value)}>
                <option value="">{orders.length ? tf("selectSalesOrder") : tf("noSalesOrders")}</option>
                {orders.map((o) => <option key={o.id} value={o.id}>{o.number}</option>)}
              </select>
              {loadingOrders && <span className={s.muted}>{t("loading")}</span>}
            </label>
          )}
          <label className={s.field}>{t("requestedDeliveryDate")}<input type="date" value={delivery} onChange={(e) => setDelivery(e.target.value)} /></label>
          <label className={s.field}>{t("priority")}
            <select value={priority} onChange={(e) => setPriority(e.target.value as DemandPriority)}>
              {priorities.map((v) => <option key={v} value={v}>{t(`priorities.${v}`)}</option>)}
            </select>
          </label>
          <label className={s.field}>{t("notes")}<textarea value={notes} onChange={(e) => setNotes(e.target.value)} /></label>
        </div>
      </fieldset>

      {order && (
        <fieldset disabled={busy} className={s.panel}>
          <legend>{tf("lines")}</legend>
          <div className={s.tableWrap}>
            <table className={s.table}>
              <thead><tr>
                <th>#</th><th>{t("productType")}</th><th>{tf("ordered")}</th><th>{tf("sent")}</th><th>{tf("remaining")}</th><th>{tf("sendNow")}</th>
              </tr></thead>
              <tbody>
                {order.lines.map((l) => (
                  <tr key={l.id}>
                    <td>{l.line_no}</td>
                    <td>{productName(l.product_type)}<SpecList productKey={l.product_type} spec={l.target_spec_json} /></td>
                    <td><bdi>{fmt.quantity(l.ordered_quantity, unit(l.unit))}</bdi></td>
                    <td><bdi>{fmt.quantity(l.transferred_quantity, unit(l.unit))}</bdi></td>
                    <td><bdi>{fmt.quantity(l.remaining_quantity, unit(l.unit))}</bdi></td>
                    <td>
                      <input type="number" min="0" step="0.001" max={Number(l.remaining_quantity)} aria-label={tf("sendNowFor", { line: l.line_no })}
                        disabled={Number(l.remaining_quantity) <= 0} value={quantities[l.id] ?? ""}
                        onChange={(e) => setQuantities((q) => ({ ...q, [l.id]: e.target.value }))} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className={s.muted} style={{ marginBottom: 0 }}>{tf("lockedLinesHint")}</p>
        </fieldset>
      )}

      <div className={s.toolbar}>
        <button disabled={busy || !order} className={`${s.button} ${s.primary}`} type="submit">{tf("create")}</button>
      </div>
    </form>
  );
}
