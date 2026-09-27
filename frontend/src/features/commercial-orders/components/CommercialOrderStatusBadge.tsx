"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import { commercialOrderStatusColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { CommercialOrderStatus } from "../types";

type CommercialOrderStatusBadgeProps = {
  status: CommercialOrderStatus;
};

export function CommercialOrderStatusBadge({ status }: CommercialOrderStatusBadgeProps) {
  const t = useTranslations();
  const label = getEnumLabel("commercialOrder", "status", status, t);

  return (
    <span style={{ ...sharedStyles.badge, ...commercialOrderStatusColors[status] }}>
      {label}
    </span>
  );
}
