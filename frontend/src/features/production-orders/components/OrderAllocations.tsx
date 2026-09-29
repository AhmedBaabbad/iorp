"use client";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { AllocationStatusBadge } from "@/features/production-demands/demand-allocations";
import type { ProductionOrderData } from "../types";
import s from "@/features/production-demands/demands.module.css";

// Released rows stay listed: a cancelled order never loses its demand origin.
// Cancelling the order is a status action (OrderStatusPanel), not part of this section.
export function OrderAllocations({ order }: { order: ProductionOrderData }) {
  const t = useTranslations("production.allocation");
  const d = useTranslations("production.demands");
  return <section className={s.panel}><h2>{t("sources")}</h2>
    {!order.allocations?.length ? <p>{t("empty")}</p> : <div className={s.tableWrap}><table className={s.table}>
      <thead><tr><th>{d("customer")}</th><th>{d("demandNumber")}</th><th>{d("lineNo")}</th><th>{t("allocated")}</th><th>{d("unit")}</th><th>{t("allocationStatus")}</th><th>{t("releasedAt")}</th><th>{t("releaseReason")}</th></tr></thead>
      <tbody>{order.allocations.map(a => <tr key={a.id} style={a.status === "released" ? { opacity: 0.75 } : undefined}>
        <td>{a.customer_name}</td><td><Link href={`/production/demands/${a.production_demand_id}`}>{a.demand_number}</Link></td><td>{a.demand_item_line_no}</td><td>{a.allocated_quantity}</td><td>{a.unit}</td>
        <td><AllocationStatusBadge status={a.status} /></td><td>{a.released_at ? new Date(a.released_at).toLocaleString() : "—"}</td><td>{a.release_reason ?? "—"}</td>
      </tr>)}</tbody>
      <tfoot><tr><th colSpan={3}>{t("activeTotal")}</th><td>{order.active_allocated_quantity ?? order.planned_quantity}</td><td>{order.unit}</td><td colSpan={3} /></tr></tfoot>
    </table></div>}
  </section>;
}
