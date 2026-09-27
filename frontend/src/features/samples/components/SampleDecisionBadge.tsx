"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import { sharedStyles } from "@/styles/shared-styles";
import type { SampleDecision } from "../types";

const sampleDecisionColors: Record<SampleDecision, { background: string; color: string }> = {
  pending: { background: "#fef9c3", color: "#854d0e" },
  accepted: { background: "#dcfce7", color: "#166534" },
  rejected: { background: "#fee2e2", color: "#991b1b" },
};

type SampleDecisionBadgeProps = {
  decision: SampleDecision | null | undefined;
};

export function SampleDecisionBadge({ decision }: SampleDecisionBadgeProps) {
  const t = useTranslations();

  if (!decision) {
    return <span style={sharedStyles.meta}>-</span>;
  }

  const label = getEnumLabel("sample", "decision", decision, t);

  return (
    <span style={{ ...sharedStyles.badge, ...sampleDecisionColors[decision] }}>
      {label}
    </span>
  );
}
