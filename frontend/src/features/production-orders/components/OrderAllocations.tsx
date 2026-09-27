"use client";
import Link from "next/link";
import { useState } from "react";
import { useTranslations } from "next-intl";
import { usePermission } from "@/features/auth/permission-hooks";
import { AllocationStatusBadge } from "@/features/production-demands/demand-allocations";
import { ReasonDialog } from "@/features/production-demands/reason-dialog";
import { canReleaseFromOrder, lifecycleErrorCode } from "@/features/production-demands/planning-lifecycle";
import { cancelProductionOrder } from "../api/production-orders-api";
import type { ProductionOrderData } from "../types";
import s from "@/features/production-demands/demands.module.css";

// Released rows stay listed: a cancelled order never loses its demand origin.
export function OrderAllocations({ order, onChanged }: { order: ProductionOrderData; onChanged?: () => void }) {
  const t = useTranslations("production.allocation");
  const d = useTranslations("production.demands");
  const canCancel = usePermission("production:orders:cancel");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState(false);
  const cancellable = canCancel && canReleaseFromOrder(order.status);
  async function cancel(reason: string) {
    setBusy(true); setError("");
    try { await cancelProductionOrder(order.id, reason); setConfirming(false); onChanged?.(); }
    catch (e) { setError(lifecycleErrorCode(e)); setConfirming(false); }
    finally { setBusy(false); }
  }
  return <section className={s.panel}><h2>{t("sources")}</h2>
    {cancellable && <div className={s.actions}><button className={s.button} disabled={busy} onClick={() => setConfirming(true)}>{t("cancelOrder")}</button><span className={s.muted}>{t("cancelOrderHint")}</span></div>}
    {error && <p role="alert" className={s.error}>{t(`errors.${t.has(`errors.${error}`) ? error : "request_failed"}`)}</p>}
    {!order.allocations?.length ? <p>{t("empty")}</p> : <div className={s.tableWrap}><table className={s.table}>
      <thead><tr><th>{d("customer")}</th><th>{d("demandNumber")}</th><th>{d("lineNo")}</th><th>{t("allocated")}</th><th>{d("unit")}</th><th>{t("allocationStatus")}</th><th>{t("releasedAt")}</th><th>{t("releaseReason")}</th></tr></thead>
      <tbody>{order.allocations.map(a => <tr key={a.id} style={a.status === "released" ? { opacity: 0.75 } : undefined}>
        <td>{a.customer_name}</td><td><Link href={`/production/demands/${a.production_demand_id}`}>{a.demand_number}</Link></td><td>{a.demand_item_line_no}</td><td>{a.allocated_quantity}</td><td>{a.unit}</td>
        <td><AllocationStatusBadge status={a.status} /></td><td>{a.released_at ? new Date(a.released_at).toLocaleString() : "—"}</td><td>{a.release_reason ?? "—"}</td>
      </tr>)}</tbody>
      <tfoot><tr><th colSpan={3}>{t("activeTotal")}</th><td>{order.active_allocated_quantity ?? order.planned_quantity}</td><td>{order.unit}</td><td colSpan={3} /></tr></tfoot>
    </table></div>}
    {confirming && <ReasonDialog title={t("cancelOrderTitle", { order: order.production_order_number })} description={t("cancelOrderHint")} confirmLabel={t("cancelOrder")} busy={busy} onClose={() => setConfirming(false)} onConfirm={cancel} />}
  </section>;
}
