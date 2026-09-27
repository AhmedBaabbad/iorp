"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import { correctiveActionPriorityColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { CorrectiveActionPriority } from "../types";

type CorrectiveActionPriorityBadgeProps = {
  priority: CorrectiveActionPriority;
};

export function CorrectiveActionPriorityBadge({
  priority,
}: CorrectiveActionPriorityBadgeProps) {
  const t = useTranslations();
  const label = getEnumLabel("correctiveAction", "priority", priority, t);

  return (
    <span style={{ ...sharedStyles.badge, ...correctiveActionPriorityColors[priority] }}>
      {label}
    </span>
  );
}
