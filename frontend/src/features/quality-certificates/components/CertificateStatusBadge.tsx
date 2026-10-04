"use client";

import { useTranslations } from "next-intl";
import s from "@/features/production-demands/demands.module.css";
import type { CertificateStatus } from "../types";

const CLASS: Record<CertificateStatus, string> = { issued: s.green, draft: s.high, revoked: s.cancelled };

export function CertificateStatusBadge({ status }: { status: CertificateStatus }) {
  const t = useTranslations("quality.certificates.statuses");
  return <span className={`${s.badge} ${CLASS[status]}`}>{t(status)}</span>;
}
