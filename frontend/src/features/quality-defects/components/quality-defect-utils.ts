import { getEnumLabel } from "@/i18n/enum-helpers";
import type { DefectCategory } from "../types";

export function formatDefectCategory(category: DefectCategory, t: (key: string) => string) {
  return getEnumLabel("qualityDefect", "defectCategory", category, t);
}

export function truncateText(value: string, maxLength: number) {
  if (value.length <= maxLength) {
    return value;
  }

  return `${value.slice(0, maxLength - 1)}...`;
}
