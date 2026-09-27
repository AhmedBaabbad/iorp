"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import { sampleStatusColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { SampleStatus } from "../types";

type SampleStatusBadgeProps = {
  status: SampleStatus;
};

export function SampleStatusBadge({ status }: SampleStatusBadgeProps) {
  const t = useTranslations();
  const label = getEnumLabel("sample", "status", status, t);

  return (
    <span style={{ ...sharedStyles.badge, ...sampleStatusColors[status] }}>
      {label}
    </span>
  );
}
