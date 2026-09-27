import { getEnumLabel } from "@/i18n/enum-helpers";
import type {
  QualityCheckResult,
  QualityCheckType,
} from "../types";

export function formatCheckType(value: QualityCheckType, t: (key: string) => string) {
  return getEnumLabel("qualityCheck", "checkType", value, t);
}

export function formatResult(value: QualityCheckResult | null, t: (key: string) => string) {
  return getEnumLabel("qualityCheck", "result", value, t);
}

export function shortId(value: string) {
  return value.length > 8 ? value.slice(0, 8) : value;
}
