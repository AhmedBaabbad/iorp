"use client";
import { Dialog } from "@/components/ui/Dialog";
import {useUnitLabel} from "@/components/UnitLabel";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { addOrderAllocation, getEligibleOrders, type EligibleOrder } from "@/features/production-orders/api/production-orders-api";
import type { Item } from "./api";
import { lifecycleErrorCode } from "./planning-lifecycle";
import s from "./demands.module.css";

// "Allocate to an existing production order": the server lists the open orders (draft, released, in progress, on hold)
// this demand item may join; the screen never decides by status itself.
export function ExistingOrderDialog({ item, quantity, onClose }: { item: Item; quantity: string; onClose: () => void }) {
  const unitText = useUnitLabel();
  const t = useTranslations("production.allocation");
  const d = useTranslations("production.demands");
  const enums = useTranslations();
  const common = useTranslations("common");
  const router = useRouter();
  const [orders, setOrders] = useState<EligibleOrder[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    getEligibleOrders(item.id!).then(found => { if (active) setOrders(found); }).catch(e => { if (active) { setOrders([]); setError(lifecycleErrorCode(e)); } });
    return () => { active = false; };
  }, [item.id]);
  async function choose(order: EligibleOrder) {
    setBusy(true); setError("");
    try { await addOrderAllocation(order.id, item.id!, quantity); router.push(`/production-orders/${order.id}`); }
    catch (e) { setError(lifecycleErrorCode(e)); }
    finally { setBusy(false); }
  }
  return <Dialog title={t("existingTitle")} onClose={onClose} busy={busy} size="lg"
    footer={<button type="button" className={s.button} disabled={busy} onClick={onClose}>{common("actions.cancel")}</button>}>
    <p className={s.muted}>{t("existingHint", { quantity, unit: item.unit })}</p>
    {error && <p role="alert" className={s.error}>{t(`errors.${t.has(`errors.${error}`) ? error : "request_failed"}`)}</p>}
    {orders === null ? <p>{d("loading")}</p> : !orders.length ? <p>{t("noEligible")}</p> :
      <div className={s.tableWrap}><table className={s.table} aria-label={t("existingTitle")}>
        <thead><tr><th>{t("order")}</th><th>{t("orderStatus")}</th><th>{t("workCenter")}</th><th>{t("plannedQuantity")}</th><th>{t("plannedDates")}</th><th /></tr></thead>
        <tbody>{orders.map(order => <tr key={order.id}>
          <td>{order.production_order_number}</td>
          <td>{enums(`enums.productionOrder.status.${order.status}`)}</td>
          <td>{order.work_center_name ?? "—"}</td>
          <td>{order.planned_quantity} {unitText(order.unit)}</td>
          <td>{order.planned_start_date} → {order.planned_end_date}</td>
          <td><button type="button" className={`${s.button} ${s.primary}`} disabled={busy} onClick={() => choose(order)}>{t("addToThisOrder")}</button></td>
        </tr>)}</tbody>
      </table></div>}
  </Dialog>;
}
