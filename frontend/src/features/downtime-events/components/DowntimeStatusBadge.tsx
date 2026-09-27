"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import { downtimeStatusColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { DowntimeStatus } from "../types";

type DowntimeStatusBadgeProps = {
  status: DowntimeStatus;
};

export function DowntimeStatusBadge({ status }: DowntimeStatusBadgeProps) {
  const t = useTranslations();
  const label = getEnumLabel("downtimeEvent", "status", status, t);

  return (
    <span style={{ ...sharedStyles.badge, ...downtimeStatusColors[status] }}>
      {label}
    </span>
  );
}
