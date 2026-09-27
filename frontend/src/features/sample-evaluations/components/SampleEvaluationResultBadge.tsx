"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import { sampleEvaluationResultStatusColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { SampleEvaluationResultStatus } from "../types";

type SampleEvaluationResultBadgeProps = {
  resultStatus: SampleEvaluationResultStatus | null | undefined;
};

export function SampleEvaluationResultBadge({
  resultStatus,
}: SampleEvaluationResultBadgeProps) {
  const t = useTranslations();

  if (!resultStatus) {
    return <span style={sharedStyles.meta}>-</span>;
  }

  const label = getEnumLabel("sampleEvaluation", "resultStatus", resultStatus, t);

  return (
    <span style={{ ...sharedStyles.badge, ...sampleEvaluationResultStatusColors[resultStatus] }}>
      {label}
    </span>
  );
}
