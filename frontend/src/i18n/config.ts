export const LOCALES = ["ar", "en"] as const;
export const DEFAULT_LOCALE = "ar";
export const LOCALE_COOKIE_NAME = "IORP_LOCALE";
export const RTL_LOCALES = ["ar"] as const;

export type Locale = (typeof LOCALES)[number];

export function isLocale(value: string | undefined): value is Locale {
  return LOCALES.includes(value as Locale);
}

export function isRTL(locale: Locale): boolean {
  return RTL_LOCALES.includes(locale as (typeof RTL_LOCALES)[number]);
}
