"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import { productionOrderPriorityColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { ProductionOrderPriority } from "../types";

type ProductionOrderPriorityBadgeProps = {
  priority: ProductionOrderPriority;
};

export function ProductionOrderPriorityBadge({ priority }: ProductionOrderPriorityBadgeProps) {
  const t = useTranslations();
  const label = getEnumLabel("productionOrder", "priority", priority, t);

  return (
    <span style={{ ...sharedStyles.badge, ...productionOrderPriorityColors[priority] }}>
      {label}
    </span>
  );
}

export function formatProductionOrderPriority(
  priority: ProductionOrderPriority,
  t: (key: string) => string,
) {
  return getEnumLabel("productionOrder", "priority", priority, t);
}
