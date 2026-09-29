"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useFormatter } from "@/hooks/useFormatter";
import { getProductionOrderStatusHistory } from "../api/production-orders-api";
import type { OrderStatusHistoryEntry } from "../types";
import { ProductionOrderStatusBadge } from "./ProductionOrderStatusBadge";
import s from "@/features/production-demands/demands.module.css";

// Every status change of the order, newest first: who, when, why, and whether it was automatic.
export function OrderStatusTimeline({ orderId, revision }: { orderId: string; revision: number }) {
  const t = useTranslations("production.productionOrders.lifecycle");
  const fmt = useFormatter();
  const [entries, setEntries] = useState<OrderStatusHistoryEntry[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    getProductionOrderStatusHistory(orderId)
      .then((rows) => { if (active) { setEntries(rows); setFailed(false); } })
      .catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [orderId, revision]);

  return (
    <section className={s.panel} aria-label={t("historyTitle")}>
      <h2 style={{ marginTop: 0 }}>{t("historyTitle")}</h2>
      {failed && <p role="alert" className={s.error}>{t("errors.request_failed")}</p>}
      {entries && entries.length === 0 && <p className={s.muted}>{t("historyEmpty")}</p>}
      {entries && entries.length > 0 && (
        <ol className={s.timeline}>
          {[...entries].reverse().map((entry) => (
            <li key={entry.id}>
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
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
