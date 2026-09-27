"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import { qualityRejectionDispositionStatusColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { DispositionStatus } from "../types";

type DispositionStatusBadgeProps = {
  status: DispositionStatus;
};

export function DispositionStatusBadge({ status }: DispositionStatusBadgeProps) {
  const t = useTranslations();
  const label = getEnumLabel("qualityRejection", "dispositionStatus", status, t);

  return (
    <span style={{ ...sharedStyles.badge, ...qualityRejectionDispositionStatusColors[status] }}>
      {label}
    </span>
  );
}
