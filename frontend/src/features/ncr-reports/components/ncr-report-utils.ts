import { getEnumLabel } from "@/i18n/enum-helpers";
import type { NCRReportType, NCRSourceType, NCRStatus } from "../types";

export function shortId(value: string) {
  return value.length > 8 ? value.slice(0, 8) : value;
}

export function formatNcrStatus(value: NCRStatus, t: (key: string) => string) {
  return getEnumLabel("ncrReport", "status", value, t);
}

export function formatSourceType(value: NCRSourceType, t: (key: string) => string) {
  return getEnumLabel("ncrReport", "sourceType", value, t);
}

export function formatReportType(value: NCRReportType, t: (key: string) => string) {
  return getEnumLabel("ncrReport", "reportType", value, t);
}

export function truncateText(value: string, maxLength: number) {
  if (value.length <= maxLength) {
    return value;
  }

  return `${value.slice(0, maxLength - 1)}...`;
}
