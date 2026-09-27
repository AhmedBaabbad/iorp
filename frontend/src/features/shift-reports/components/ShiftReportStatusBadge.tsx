"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import { shiftReportStatusColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { ShiftReportStatus } from "../types";

type ShiftReportStatusBadgeProps = {
  status: ShiftReportStatus;
};

export function ShiftReportStatusBadge({ status }: ShiftReportStatusBadgeProps) {
  const t = useTranslations();
  const label = getEnumLabel("shiftReport", "status", status, t);

  return (
    <span style={{ ...sharedStyles.badge, ...shiftReportStatusColors[status] }}>
      {label}
    </span>
  );
}

export function formatShiftReportStatus(
  status: ShiftReportStatus,
  t: (key: string) => string,
) {
  return getEnumLabel("shiftReport", "status", status, t);
}
