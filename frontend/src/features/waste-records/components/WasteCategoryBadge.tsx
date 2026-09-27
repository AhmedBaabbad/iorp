"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import { wasteCategoryColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { WasteCategory } from "../types";

type WasteCategoryBadgeProps = {
  category: WasteCategory;
};

export function WasteCategoryBadge({ category }: WasteCategoryBadgeProps) {
  const t = useTranslations();
  const label = getEnumLabel("wasteRecord", "wasteCategory", category, t);

  return (
    <span style={{ ...sharedStyles.badge, ...wasteCategoryColors[category] }}>
      {label}
    </span>
  );
}
