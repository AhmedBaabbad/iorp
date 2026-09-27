"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import { downtimeCategoryColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { DowntimeCategory } from "../types";

type DowntimeCategoryBadgeProps = {
  category: DowntimeCategory;
};

export function DowntimeCategoryBadge({ category }: DowntimeCategoryBadgeProps) {
  const t = useTranslations();
  const label = getEnumLabel("downtimeEvent", "category", category, t);

  return (
    <span style={{ ...sharedStyles.badge, ...downtimeCategoryColors[category] }}>
      {label}
    </span>
  );
}
