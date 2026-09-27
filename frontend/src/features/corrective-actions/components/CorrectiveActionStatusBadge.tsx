"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import { correctiveActionStatusColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { CorrectiveActionStatus } from "../types";

type CorrectiveActionStatusBadgeProps = {
  status: CorrectiveActionStatus;
};

export function CorrectiveActionStatusBadge({ status }: CorrectiveActionStatusBadgeProps) {
  const t = useTranslations();
  const label = getEnumLabel("correctiveAction", "status", status, t);

  return (
    <span style={{ ...sharedStyles.badge, ...correctiveActionStatusColors[status] }}>
      {label}
    </span>
  );
}
