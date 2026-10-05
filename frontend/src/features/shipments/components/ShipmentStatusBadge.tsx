"use client";

import { useTranslations } from "next-intl";
import s from "@/features/production-demands/demands.module.css";
import type { ReturnStatus, ShipmentStatus } from "../types";

const CLASS: Record<ShipmentStatus, string> = {
  draft: "", ready: s.blue, dispatched: s.high, delivered: s.green, partially_delivered: s.overdue, returned: s.urgent,
  not_delivered: s.cancelled, cancelled: s.cancelled,
};
const RETURN_CLASS: Record<ReturnStatus, string> = { requested: s.high, approved: s.blue, received: s.green, rejected: s.cancelled, cancelled: s.cancelled };

export function ShipmentStatusBadge({ status }: { status: ShipmentStatus }) {
  const t = useTranslations("shipping.statuses");
  return <span className={`${s.badge} ${CLASS[status]}`}>{t(status)}</span>;
}

export function ReturnStatusBadge({ status }: { status: ReturnStatus }) {
  const t = useTranslations("shipping.returns.statuses");
  return <span className={`${s.badge} ${RETURN_CLASS[status]}`}>{t(status)}</span>;
}
