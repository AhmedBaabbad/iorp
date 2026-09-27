"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import { defectCategoryColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { DefectCategory } from "../types";

type DefectCategoryBadgeProps = {
  category: DefectCategory;
};

export function DefectCategoryBadge({ category }: DefectCategoryBadgeProps) {
  const t = useTranslations();
  const label = getEnumLabel("qualityDefect", "defectCategory", category, t);

  return (
    <span style={{ ...sharedStyles.badge, ...defectCategoryColors[category] }}>
      {label}
    </span>
  );
}
