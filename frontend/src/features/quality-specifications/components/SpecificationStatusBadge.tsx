"use client";

import { useTranslations } from "next-intl";
import s from "@/features/production-demands/demands.module.css";
import type { SpecificationStatus } from "../types";

const CLASS: Record<SpecificationStatus, string> = { active: s.green, draft: s.high, superseded: "" };

export function SpecificationStatusBadge({ status }: { status: SpecificationStatus }) {
  const t = useTranslations("quality.specifications.statuses");
  return <span className={`${s.badge} ${CLASS[status]}`}>{t(status)}</span>;
}
