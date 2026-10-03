"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { usePermission } from "@/features/auth/permission-hooks";
import s from "@/features/production-demands/demands.module.css";
import { getDowntimeSummary } from "../api";
import { LINKABLE_ORDER_STATUSES } from "../downtime-rules";
import type { DowntimeSummary } from "../types";
import { DowntimeSummaryCards } from "./DowntimeSummaryCards";
import { downtimeErrorMessage } from "./downtime-errors";
import { P } from "@/lib/production-permissions";

// "التوقفات" on the order page: stops recorded against this order, planned vs. availability loss.
export function OrderDowntimeSection({ order, revision = 0 }: { order: { id: string; status: string }; revision?: number }) {
  const t = useTranslations("production.downtimeEvents");
  const canRead = usePermission(P.DOWNTIME_READ);
  const canWrite = usePermission(P.DOWNTIME_CREATE);
  const relevant = !["draft", "released", "cancelled"].includes(order.status);
  const [summary, setSummary] = useState<DowntimeSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!canRead || !relevant) return;
    let active = true;
    getDowntimeSummary({ production_order_id: order.id }).then(v => { if (active) setSummary(v); }).catch(e => { if (active) setError(downtimeErrorMessage(e, t)); });
    return () => { active = false; };
  }, [canRead, relevant, order.id, order.status, revision, t]);

  if (!canRead || !relevant) return null;
  const canRecord = canWrite && LINKABLE_ORDER_STATUSES.includes(order.status);
  return <section className={s.panel} aria-label={t("orderSection.title")}>
    <div className={s.actions} style={{ justifyContent: "space-between" }}>
      <h2 style={{ margin: 0 }}>{t("orderSection.title")}</h2>
      <span className={s.actions}>
        <Link className={s.button} href={`/downtime-events?order=${order.id}`}>{t("orderSection.viewAll")}</Link>
        {canRecord && <Link className={`${s.button} ${s.primary}`} href={`/downtime-events/new?order=${order.id}`}>{t("actions.record")}</Link>}
      </span>
    </div>
    <p className={s.muted}>{t("orderSection.hint")}</p>
    {error && <p role="alert" className={s.error}>{error}</p>}
    {summary && (summary.count + summary.open_count === 0
      ? <p className={s.muted} style={{ margin: 0 }}>{t("orderSection.empty")}</p>
      : <DowntimeSummaryCards summary={summary} />)}
  </section>;
}
