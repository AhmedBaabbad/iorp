"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import { closureStatusColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { ClosureStatus } from "../types";

type ClosureStatusBadgeProps = {
  status: ClosureStatus;
};

export function ClosureStatusBadge({ status }: ClosureStatusBadgeProps) {
  const t = useTranslations();
  const label = getEnumLabel("closureVerification", "closureStatus", status, t);

  return (
    <span style={{ ...sharedStyles.badge, ...closureStatusColors[status] }}>
      {label}
    </span>
  );
}
