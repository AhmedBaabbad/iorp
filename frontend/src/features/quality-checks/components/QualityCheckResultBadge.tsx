"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import { qualityCheckResultColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { QualityCheckResult } from "../types";

type QualityCheckResultBadgeProps = {
  result: QualityCheckResult | null;
};

export function QualityCheckResultBadge({ result }: QualityCheckResultBadgeProps) {
  const t = useTranslations();
  const key = result ?? "pending";
  const label = getEnumLabel("qualityCheck", "result", result, t);

  return (
    <span style={{ ...sharedStyles.badge, ...qualityCheckResultColors[key] }}>
      {label}
    </span>
  );
}
