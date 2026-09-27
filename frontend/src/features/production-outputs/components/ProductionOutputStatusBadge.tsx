"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import { productionOutputStatusColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { ProductionOutputStatus } from "../types";

type ProductionOutputStatusBadgeProps = {
  status: ProductionOutputStatus;
};

export function ProductionOutputStatusBadge({ status }: ProductionOutputStatusBadgeProps) {
  const t = useTranslations();
  const label = getEnumLabel("productionOutput", "status", status, t);

  return (
    <span style={{ ...sharedStyles.badge, ...productionOutputStatusColors[status] }}>
      {label}
    </span>
  );
}
