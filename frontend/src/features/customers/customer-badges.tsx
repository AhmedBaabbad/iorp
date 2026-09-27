"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import {
  customerPriorityLevelColors,
  customerRelationshipStageColors,
  customerStatusColors,
} from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { CustomerStatus, PriorityLevel, RelationshipStage } from "@/types/customers";

export function CustomerStatusBadge({ status }: { status: CustomerStatus }) {
  const tEnums = useTranslations();

  return (
    <span style={{ ...sharedStyles.badge, ...customerStatusColors[status] }}>
      {getEnumLabel("customer", "status", status, tEnums)}
    </span>
  );
}

export function CustomerPriorityBadge({ priority }: { priority: PriorityLevel }) {
  const tEnums = useTranslations();

  return (
    <span style={{ ...sharedStyles.badge, ...customerPriorityLevelColors[priority] }}>
      {getEnumLabel("customer", "priorityLevel", priority, tEnums)}
    </span>
  );
}

export function CustomerRelationshipStageBadge({ stage }: { stage: RelationshipStage }) {
  const tEnums = useTranslations();

  return (
    <span style={{ ...sharedStyles.badge, ...customerRelationshipStageColors[stage] }}>
      {getEnumLabel("customer", "relationshipStage", stage, tEnums)}
    </span>
  );
}
