import { getEnumLabel } from "@/i18n/enum-helpers";
import type { Disposition, RejectionReason } from "../types";

export function formatRejectionReason(value: RejectionReason, t: (key: string) => string) {
  return getEnumLabel("qualityRejection", "rejectionReason", value, t);
}

export function formatDisposition(value: Disposition, t: (key: string) => string) {
  return getEnumLabel("qualityRejection", "disposition", value, t);
}

export function shortId(value: string) {
  return value.length > 8 ? value.slice(0, 8) : value;
}
