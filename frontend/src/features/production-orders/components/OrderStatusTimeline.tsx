"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useFormatter } from "@/hooks/useFormatter";
import { getProductionOrderStatusHistory } from "../api/production-orders-api";
import type { OrderStatusHistoryEntry,OrderRescheduleHistoryEntry } from "../types";
import {DateChangePreview} from "./OrderReschedule";
import { ProductionOrderStatusBadge } from "./ProductionOrderStatusBadge";
import s from "@/features/production-demands/demands.module.css";

// Every status change of the order, newest first: who, when, why, and whether it was automatic.
export function OrderStatusTimeline({ orderId, revision, reschedules=[] }: { orderId: string; revision: number;reschedules?:OrderRescheduleHistoryEntry[] }) {
  const t = useTranslations("production.productionOrders.lifecycle");
  const fmt = useFormatter();
  const scheduling=useTranslations("production.productionOrders.reschedule");
  const [entries, setEntries] = useState<OrderStatusHistoryEntry[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    getProductionOrderStatusHistory(orderId)
      .then((rows) => { if (active) { setEntries(rows); setFailed(false); } })
      .catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [orderId, revision]);
  const history=[...(entries??[]).map(entry=>({kind:"status" as const,entry})),...reschedules.map(entry=>({kind:"schedule" as const,entry}))]
    .sort((a,b)=>Date.parse(b.entry.created_at)-Date.parse(a.entry.created_at)||b.entry.id.localeCompare(a.entry.id));

  return (
    <section className={s.panel} aria-label={t("historyTitle")}>
      <h2 style={{ marginTop: 0 }}>{t("historyTitle")}</h2>
      {failed && <p role="alert" className={s.error}>{t("errors.request_failed")}</p>}
      {entries && history.length === 0 && <p className={s.muted}>{t("historyEmpty")}</p>}
      {history.length > 0 && (
        <ol className={s.timeline}>
          {history.map(event => event.kind==="schedule"?<li key={`schedule-${event.entry.id}`}>
            <strong>{scheduling("historyAction")}</strong>
            <div className={s.muted}>{fmt.dateTime(event.entry.created_at)} · {event.entry.actor_name??t("unknownUser")}</div>
            <DateChangePreview oldStart={event.entry.old_start} newStart={event.entry.new_start} oldEnd={event.entry.old_end} newEnd={event.entry.new_end}/>
            <div>{t("reason")}: {event.entry.reason||scheduling("reasonNotProvided")}</div>
          </li>:(()=>{const entry=event.entry;return <li key={`status-${entry.id}`}>
              <div className={s.actions}>
                <ProductionOrderStatusBadge status={entry.from_status} />
                <span aria-hidden="true" className={s.flowArrow} />
                <ProductionOrderStatusBadge status={entry.to_status} />
                <strong>{t(`actions.${entry.action}`)}</strong>
              </div>
              <div className={s.muted}>
                {fmt.dateTime(entry.created_at)} · {entry.trigger === "manual" ? (entry.actor_name ?? t("unknownUser")) : t(`triggers.${entry.trigger}`)}
              </div>
              {entry.reason && <div>{t("reason")}: {entry.reason}</div>}
            </li>;})())}
        </ol>
      )}
    </section>
  );
}
