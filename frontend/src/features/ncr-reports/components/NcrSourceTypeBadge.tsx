"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import { ncrSourceTypeColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { NCRSourceType } from "../types";

type NcrSourceTypeBadgeProps = {
  sourceType: NCRSourceType;
};

export function NcrSourceTypeBadge({ sourceType }: NcrSourceTypeBadgeProps) {
  const t = useTranslations();
  const label = getEnumLabel("ncrReport", "sourceType", sourceType, t);

  return (
    <span style={{ ...sharedStyles.badge, ...ncrSourceTypeColors[sourceType] }}>
      {label}
    </span>
  );
}
