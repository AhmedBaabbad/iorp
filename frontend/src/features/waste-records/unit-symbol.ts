"use client";
import { useTranslations } from "next-intl";

// A unit code (kg, roll) as printed after a number in the screen's language (كجم / kg, رول / roll); text that is not a
// code (a record awaiting a unit review) is shown as written.
export function useUnitSymbol() {
  const units = useTranslations("common.units.units");
  return (code: string) => (units.has(code) ? units(code) : code);
}
