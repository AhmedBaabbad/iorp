"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import { followUpStatusColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { ActionFollowUpStatus } from "../types";

type FollowUpStatusBadgeProps = {
  status: ActionFollowUpStatus;
};

export function FollowUpStatusBadge({ status }: FollowUpStatusBadgeProps) {
  const t = useTranslations();
  const label = getEnumLabel("actionFollowUp", "status", status, t);

  return (
    <span style={{ ...sharedStyles.badge, ...followUpStatusColors[status] }}>
      {label}
    </span>
  );
}
