"use client";

import type { CSSProperties } from "react";
import { useTranslations } from "next-intl";
import { UNIT_GROUPS, UNITS, type UnitGroup } from "@/lib/units";
import { sharedStyles } from "@/styles/shared-styles";

/**
 * A unit of measure as a grouped dropdown, labelled in the screen's language: the full name and the symbol that documents
 * print (common.units.names, common.units.units). `groups` limits it
 * (e.g. weight units only). A unit saved before the list existed stays selectable as written.
 */
export function UnitSelect({ value, onChange, disabled, groups, required = true, className, style, ariaLabel, placeholder }: {
  value: string; onChange: (value: string) => void; disabled?: boolean; groups?: UnitGroup[]; required?: boolean;
  className?: string; style?: CSSProperties; ariaLabel?: string; placeholder?: string;
}) {
  const t = useTranslations("common.units");
  const shown = groups ?? (Object.keys(UNIT_GROUPS) as UnitGroup[]);
  const legacy = value && !UNITS.includes(value);
  // Chosen by its full name, with the short form every document prints: "مليمتر (مم)", "Millimetre (mm)".
  const label = (code: string) => (t(`names.${code}`) === t(`units.${code}`) ? t(`names.${code}`) : `${t(`names.${code}`)} (${t(`units.${code}`)})`);
  return (
    <select className={className} style={className ? style : { ...sharedStyles.input, ...style }} value={value} aria-label={ariaLabel}
      onChange={(event) => onChange(event.target.value)} disabled={disabled} required={required}>
      <option value="">{placeholder ?? t("choose")}</option>
      {legacy ? <option value={value}>{value}</option> : null}
      {shown.map((group) => shown.length > 1
        ? <optgroup key={group} label={t(`groups.${group}`)}>{UNIT_GROUPS[group].map((code) => <option key={code} value={code}>{label(code)}</option>)}</optgroup>
        : UNIT_GROUPS[group].map((code) => <option key={code} value={code}>{label(code)}</option>))}
    </select>
  );
}
