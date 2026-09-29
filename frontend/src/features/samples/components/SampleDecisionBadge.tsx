"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import { sharedStyles } from "@/styles/shared-styles";
import type { SampleDecision } from "../types";

const sampleDecisionColors: Record<SampleDecision, { background: string; color: string }> = {
  pending: { background: "var(--warning-soft)", color: "var(--warning)" },
  accepted: { background: "var(--success-soft)", color: "var(--success)" },
  rejected: { background: "var(--danger-soft)", color: "var(--danger)" },
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
