"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import { quoteStatusColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { QuoteStatus } from "../types";

type QuoteStatusBadgeProps = {
  status: QuoteStatus;
};

export function QuoteStatusBadge({ status }: QuoteStatusBadgeProps) {
  const t = useTranslations();
  const label = getEnumLabel("quote", "status", status, t);

  return (
    <span style={{ ...sharedStyles.badge, ...quoteStatusColors[status] }}>
      {label}
    </span>
  );
}
