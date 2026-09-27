"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import { defectSeverityColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { DefectSeverity } from "../types";

type DefectSeverityBadgeProps = {
  severity: DefectSeverity;
};

export function DefectSeverityBadge({ severity }: DefectSeverityBadgeProps) {
  const t = useTranslations();
  const label = getEnumLabel("qualityDefect", "severity", severity, t);

  return (
    <span style={{ ...sharedStyles.badge, ...defectSeverityColors[severity] }}>
      {label}
    </span>
  );
}
