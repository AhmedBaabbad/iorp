"use client";

import { useTranslations } from "next-intl";
import { wasteCategoryColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { WasteCategory } from "../types";

export function WasteCategoryBadge({ category }: { category: WasteCategory }) {
  const t = useTranslations("enums.wasteRecord.wasteCategory");
  return <span style={{ ...sharedStyles.badge, ...wasteCategoryColors[category] }}>{t(category)}</span>;
}
