import ar from "@/i18n/locales/ar/common.json";
import en from "@/i18n/locales/en/common.json";
export function formatUnit(unit: string | null | undefined, locale: string): string {
  if (!unit) return "";
  const labels: Record<string,string> = locale.startsWith("ar") ? ar.units.units : en.units.units;
  const code = unit.trim().toLowerCase();
  return Object.prototype.hasOwnProperty.call(labels, code) ? labels[code] : unit;
}
