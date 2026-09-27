import { getEnumLabel } from "@/i18n/enum-helpers";
import { shiftStatusColors, shiftTypeColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { ShiftStatus, ShiftType } from "../types";

export function formatShiftType(value: ShiftType, t: (key: string) => string) {
  return getEnumLabel("shiftDefinition", "shiftType", value, t);
}

export function formatShiftStatus(value: ShiftStatus, t: (key: string) => string) {
  return getEnumLabel("shiftDefinition", "status", value, t);
}

export function formatTime(value: string) {
  return value.slice(0, 5);
}

export function formatTimeRange(startTime: string, endTime: string) {
  return `${formatTime(startTime)} – ${formatTime(endTime)}`;
}

export function typeBadgeStyle(value: ShiftType) {
  return { ...sharedStyles.badge, ...shiftTypeColors[value] };
}

export function statusBadgeStyle(status: ShiftStatus) {
  return { ...sharedStyles.badge, ...shiftStatusColors[status] };
}
