import { getEnumLabel } from "@/i18n/enum-helpers";
import { commercialOrderStatusColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { CommercialOrderStatus } from "../types";

export function orderStatusBadgeStyle(status: CommercialOrderStatus) {
  return { ...sharedStyles.badge, ...commercialOrderStatusColors[status] };
}

export function formatOrderStatus(status: CommercialOrderStatus, t: (key: string) => string) {
  return getEnumLabel("commercialOrder", "status", status, t);
}
