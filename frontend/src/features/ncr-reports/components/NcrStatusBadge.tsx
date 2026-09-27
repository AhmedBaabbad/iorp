"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import { ncrStatusColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { NCRStatus } from "../types";

type NcrStatusBadgeProps = {
  status: NCRStatus;
};

export function NcrStatusBadge({ status }: NcrStatusBadgeProps) {
  const t = useTranslations();
  const label = getEnumLabel("ncrReport", "status", status, t);

  return (
    <span style={{ ...sharedStyles.badge, ...ncrStatusColors[status] }}>
      {label}
    </span>
  );
}
