"use client";

import { useTranslations } from "next-intl";

import { getEnumLabel } from "@/i18n/enum-helpers";
import { closureResultColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { ClosureVerificationResult } from "../types";

type ClosureResultBadgeProps = {
  result: ClosureVerificationResult;
};

export function ClosureResultBadge({ result }: ClosureResultBadgeProps) {
  const t = useTranslations();
  const label = getEnumLabel("closureVerification", "verificationResult", result, t);

  return (
    <span style={{ ...sharedStyles.badge, ...closureResultColors[result] }}>
      {label}
    </span>
  );
}
