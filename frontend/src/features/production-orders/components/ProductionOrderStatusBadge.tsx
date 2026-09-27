"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import { productionOrderStatusColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { ProductionOrderStatus } from "../types";

type ProductionOrderStatusBadgeProps = {
  status: ProductionOrderStatus;
};

export function ProductionOrderStatusBadge({ status }: ProductionOrderStatusBadgeProps) {
  const t = useTranslations();
  const label = getEnumLabel("productionOrder", "status", status, t);

  return (
    <span style={{ ...sharedStyles.badge, ...productionOrderStatusColors[status] }}>
      {label}
    </span>
  );
}

export function formatProductionOrderStatus(
  status: ProductionOrderStatus,
  t: (key: string) => string,
) {
  return getEnumLabel("productionOrder", "status", status, t);
}
