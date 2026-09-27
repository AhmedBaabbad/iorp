"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import { qualityRejectionDispositionColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { Disposition } from "../types";

type DispositionBadgeProps = {
  disposition: Disposition;
};

export function DispositionBadge({ disposition }: DispositionBadgeProps) {
  const t = useTranslations();
  const label = getEnumLabel("qualityRejection", "disposition", disposition, t);

  return (
    <span style={{ ...sharedStyles.badge, ...qualityRejectionDispositionColors[disposition] }}>
      {label}
    </span>
  );
}
