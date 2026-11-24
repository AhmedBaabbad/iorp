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
import {usePermission} from "@/features/auth/permission-hooks";
import {P} from "@/lib/production-permissions";
import {ExtendEndFields,scheduleOverdue,scheduleOpen,schedulingError,useOrderExtension} from "@/features/production-orders/components/OrderReschedule";
import type {ProductionOrderData} from "@/features/production-orders/types";

// "Allocate to an existing production order": the server lists the open orders (draft, released, in progress, on hold)
// this demand item may join; the screen never decides by status itself.
export function ExistingOrderDialog({ item, quantity, onClose }: { item: Item; quantity: string; onClose: () => void }) {
  const unitText = useUnitLabel();
  const t = useTranslations("production.allocation");
  const d = useTranslations("production.demands");
  const enums = useTranslations();
  const common = useTranslations("common");
  const scheduling=useTranslations("production.productionOrders.reschedule"),canUpdate=usePermission(P.ORDERS_UPDATE);
  const router = useRouter();
  const [orders, setOrders] = useState<EligibleOrder[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [selected,setSelected]=useState<string|null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    getEligibleOrders(item.id!).then(found => { if (active) setOrders(found); }).catch(e => { if (active) { setOrders([]); setError(e); } });
    return () => { active = false; };
  }, [item.id]);
  async function choose(order: EligibleOrder,beforeAttach?:()=>Promise<void>) {
    setBusy(true); setError(null);
    try { await beforeAttach?.();await addOrderAllocation(order.id, item.id!, quantity); router.push(`/production-orders/${order.id}`); }
    catch (e) { setError(e); }
    finally { setBusy(false); }
  }
  return <Dialog title={t("existingTitle")} onClose={onClose} busy={busy} size="lg"
    footer={<button type="button" className={s.button} disabled={busy} onClick={onClose}>{common("actions.cancel")}</button>}>
    <p className={s.muted}>{t("existingHint", { quantity, unit: item.unit })}</p>
    {Boolean(error) && <p role="alert" className={s.error}>{schedulingError(error,scheduling,()=>{const code=lifecycleErrorCode(error);return t(`errors.${t.has(`errors.${code}`)?code:"request_failed"}`);})}</p>}
    {orders === null ? <p>{d("loading")}</p> : !orders.length ? <p>{t("noEligible")}</p> :
      <div className={s.tableWrap}><table className={s.table} aria-label={t("existingTitle")}>
        <thead><tr><th>{t("order")}</th><th>{t("orderStatus")}</th><th>{t("workCenter")}</th><th>{t("plannedQuantity")}</th><th>{t("plannedDates")}</th><th /></tr></thead>
        <tbody>{orders.map(order => <tr key={order.id}>
          <td>{order.production_order_number}</td>
          <td>{enums(`enums.productionOrder.status.${order.status}`)}</td>
          <td>{order.work_center_name ?? "—"}</td>
          <td>{order.planned_quantity} {unitText(order.unit)}</td>
          <td>{order.planned_start_date} → {order.planned_end_date} {scheduleOverdue(order)&&<span className={`${s.badge} ${s.urgent}`}>{scheduling("overdue")}</span>}</td>
          <td><button type="button" className={`${s.button} ${s.primary}`} disabled={busy} onClick={() => canUpdate&&scheduleOverdue(order)&&scheduleOpen(order)?setSelected(order.id):void choose(order)}>{t("addToThisOrder")}</button></td>
        </tr>)}</tbody>
      </table></div>}
    {selected&&orders?.find(order=>order.id===selected)&&<SelectedAllocation key={selected} order={orders.find(order=>order.id===selected)!} busy={busy}
      onSubmit={choose} onRescheduled={saved=>setOrders(rows=>rows?.map(row=>row.id===saved.id?{...row,planned_start_date:saved.planned_start_date,planned_end_date:saved.planned_end_date,finish_overdue:Boolean(saved.lifecycle?.finish_overdue)}:row)??null)}/>}
  </Dialog>;
}

function SelectedAllocation({order,busy,onSubmit,onRescheduled}:{order:EligibleOrder;busy:boolean;onSubmit:(order:EligibleOrder,before:()=>Promise<void>)=>Promise<void>;onRescheduled:(order:ProductionOrderData)=>void}){
  const t=useTranslations("production.productionOrders.reschedule");
  const extension=useOrderExtension(order,onRescheduled);
  return <form onSubmit={event=>{event.preventDefault();void onSubmit(order,extension.beforeAttach);}} aria-label={t("confirmAttach")}>
    <fieldset disabled={busy} style={{border:0,padding:0,minWidth:0}}>
      <p>{order.production_order_number}</p>
      {scheduleOverdue(order)&&<ExtendEndFields order={order} extension={extension}/>}
      <button type="submit" className={`${s.button} ${s.primary}`}>{t("confirmAttach")}</button>
    </fieldset>
  </form>;
}
