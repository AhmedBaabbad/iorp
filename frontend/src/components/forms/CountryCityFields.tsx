"use client";

import { useTranslations } from "next-intl";
import { ListSelect } from "@/features/masterdata";
import { sharedStyles } from "@/styles/shared-styles";

export type LocationValues = { country: string; city: string; city_other: string };

export function CountryCityFields({ value, onChange, disabled = false }: {
  value: LocationValues; onChange: (patch: Partial<LocationValues>) => void; disabled?: boolean;
}) {
  const t = useTranslations("common.location");
  return <>
    <label style={sharedStyles.field}><span style={sharedStyles.label}>{t("country")}</span>
      <ListSelect list="country" style={sharedStyles.input} ariaLabel={t("country")} value={value.country} disabled={disabled}
        onChange={country => onChange({ country, city: "", city_other: "" })} />
    </label>
    <label style={sharedStyles.field}><span style={sharedStyles.label}>{t("city")}</span>
      <ListSelect list="city" style={sharedStyles.input} ariaLabel={t("city")} value={value.city} parent={value.country || null}
        disabled={disabled || !value.country} onChange={city => onChange({ city, city_other: "" })} />
    </label>
    {value.city.endsWith("_other") && <label style={sharedStyles.field}><span style={sharedStyles.label}>{t("cityName")}</span>
      <input style={sharedStyles.input} value={value.city_other} required maxLength={120} disabled={disabled}
        onChange={event => onChange({ city_other: event.target.value })} />
    </label>}
  </>;
}

export function cityLabel(city: string | null | undefined, other: string | null | undefined, resolve: (value: string | null | undefined) => string) {
  return city?.endsWith("_other") && other ? other : resolve(city);
}
