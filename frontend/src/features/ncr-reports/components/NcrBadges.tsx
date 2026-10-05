"use client";

import { useTranslations } from "next-intl";
import s from "@/features/production-demands/demands.module.css";
import type { NcrSeverity, NcrStatus } from "../types";

const STATUS: Record<NcrStatus, string> = { open: s.high, investigation: s.blue, action: s.overdue, verification: s.released, closed: s.green, cancelled: s.cancelled };
const SEVERITY: Record<NcrSeverity, string> = { minor: "", major: s.high, critical: s.urgent };

export function NcrStatusBadge({ status }: { status: NcrStatus }) {
  const t = useTranslations("ncr.statuses");
  return <span className={`${s.badge} ${STATUS[status]}`}>{t(status)}</span>;
}

export function NcrSeverityBadge({ severity }: { severity: NcrSeverity }) {
  const t = useTranslations("ncr.severities");
  return <span className={`${s.badge} ${SEVERITY[severity]}`}>{t(severity)}</span>;
}
