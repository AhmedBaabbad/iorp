import { sharedStyles } from "@/styles/shared-styles";
import { workCenterStatusColors, workCenterTypeColors } from "@/styles/badge-colors";
import { getEnumLabel } from "@/i18n/enum-helpers";
import type { WorkCenterStatus, WorkCenterType } from "../types";

export function formatWorkCenterType(value: WorkCenterType, t: (key: string) => string) {
  return getEnumLabel("workCenter", "centerType", value, t);
}

export function formatWorkCenterStatus(value: WorkCenterStatus, t: (key: string) => string) {
  return getEnumLabel("workCenter", "status", value, t);
}

export function typeBadgeStyle(type: WorkCenterType) {
  return {
    ...sharedStyles.badge,
    ...workCenterTypeColors[type],
  };
}

export function statusBadgeStyle(status: WorkCenterStatus) {
  return { ...sharedStyles.badge, ...workCenterStatusColors[status] };
}
