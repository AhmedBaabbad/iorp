"use client";

import { useTranslations } from "next-intl";
import { downtimeCategoryColors, downtimeStatusColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { DowntimeCategory, DowntimeStatus } from "../types";

export function DowntimeCategoryBadge({ category }: { category: DowntimeCategory }) {
  const t = useTranslations("enums.downtimeEvent.category");
  return <span style={{ ...sharedStyles.badge, ...downtimeCategoryColors[category] }}>{t(category)}</span>;
}

export function DowntimeStatusBadge({ status }: { status: DowntimeStatus }) {
  const t = useTranslations("enums.downtimeEvent.status");
  return <span style={{ ...sharedStyles.badge, ...downtimeStatusColors[status] }}>{t(status)}</span>;
}

// Planned stops sit outside planned production time; everything else is an availability loss.
export function DowntimeTypeBadge({ planned }: { planned: boolean }) {
  const t = useTranslations("production.downtimeEvents.types");
  return <span style={{ ...sharedStyles.badge, background: "var(--surface-muted)", color: planned ? "var(--text-muted)" : "var(--danger)" }}>{t(planned ? "planned" : "loss")}</span>;
}
