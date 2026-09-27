import { getEnumLabel } from "@/i18n/enum-helpers";

export function formatShiftType(value: string, t: (key: string) => string) {
  return getEnumLabel("shiftDefinition", "shiftType", value, t);
}
