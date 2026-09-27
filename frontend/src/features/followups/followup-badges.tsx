"use client";

import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";

import { getEnumLabel } from "@/i18n/enum-helpers";
import {
  commercialFollowUpPriorityColors,
  commercialFollowUpStatusColors,
} from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { FollowUpPriority, FollowUpStatus } from "@/types/followups";

const overdueBadge: CSSProperties = {
  ...sharedStyles.badge,
  background: "#fee2e2",
  color: "#991b1b",
};

export function FollowUpStatusBadge({
  status,
  isOverdue,
}: {
  status: FollowUpStatus;
  isOverdue?: boolean;
}) {
  const t = useTranslations("commercial.followUps");
  const tEnums = useTranslations();

  if (isOverdue) {
    return (
      <span style={overdueBadge} role="status">
        {t("overdueLabel")}
      </span>
    );
  }

  return (
    <span style={{ ...sharedStyles.badge, ...commercialFollowUpStatusColors[status] }}>
      {getEnumLabel("followUp", "status", status, tEnums)}
    </span>
  );
}

export function FollowUpPriorityBadge({ priority }: { priority: FollowUpPriority }) {
  const tEnums = useTranslations();

  return (
    <span style={{ ...sharedStyles.badge, ...commercialFollowUpPriorityColors[priority] }}>
      {getEnumLabel("followUp", "priority", priority, tEnums)}
    </span>
  );
}
