"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import { qualityCheckStatusColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { QualityCheckStatus } from "../types";

type QualityCheckStatusBadgeProps = {
  status: QualityCheckStatus;
};

export function QualityCheckStatusBadge({ status }: QualityCheckStatusBadgeProps) {
  const t = useTranslations();
  const label = getEnumLabel("qualityCheck", "status", status, t);

  return (
    <span style={{ ...sharedStyles.badge, ...qualityCheckStatusColors[status] }}>
      {label}
    </span>
  );
}
