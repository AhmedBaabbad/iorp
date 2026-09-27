import type { Locale } from "@/i18n/config";

const NO_VALUE = "—";
const DATE_ONLY_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;
const TIME_ONLY_PATTERN = /^(\d{2}):(\d{2})(?::\d{2})?$/;

function toDate(value: string | Date): Date {
  if (value instanceof Date) {
    return value;
  }

  const dateOnlyMatch = DATE_ONLY_PATTERN.exec(value);
  if (dateOnlyMatch) {
    const [, year, month, day] = dateOnlyMatch;
    return new Date(Number(year), Number(month) - 1, Number(day));
  }

  return new Date(value);
}

/**
 * Reads calendar/time components of a real instant as they appear in a given
 * IANA timezone (falls back to the browser's local zone when omitted).
 * Values that are already wall-clock-only (plain "YYYY-MM-DD" or "HH:MM")
 * carry no instant/timezone at all and must never go through this — see the
 * early-return branches in formatDate/formatTime below.
 */
function getZonedParts(date: Date, timeZone?: string) {
  const parts = new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    ...(timeZone ? { timeZone } : {}),
  }).formatToParts(date);
  const get = (type: string) => parts.find((part) => part.type === type)?.value ?? "";
  const hour = get("hour");

  return {
    year: get("year"),
    month: get("month"),
    day: get("day"),
    hour: hour === "24" ? "00" : hour,
    minute: get("minute"),
  };
}

export function formatDate(
  value: string | Date | null | undefined,
  locale: Locale,
  timeZone?: string,
): string {
  if (!value) return NO_VALUE;

  if (typeof value === "string") {
    const dateOnlyMatch = DATE_ONLY_PATTERN.exec(value);
    if (dateOnlyMatch) {
      const [, year, month, day] = dateOnlyMatch;
      if (locale === "ar") return `${day}/${month}/${year}`;
      return new Intl.DateTimeFormat("en-US", { year: "numeric", month: "short", day: "numeric" }).format(
        new Date(Number(year), Number(month) - 1, Number(day)),
      );
    }
  }

  const date = toDate(value);
  if (Number.isNaN(date.getTime())) return NO_VALUE;

  if (locale === "ar") {
    const { day, month, year } = getZonedParts(date, timeZone);
    return `${day}/${month}/${year}`;
  }

  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    ...(timeZone ? { timeZone } : {}),
  }).format(date);
}

export function formatTime(
  value: string | Date | null | undefined,
  locale: Locale,
  timeZone?: string,
): string {
  if (!value) return NO_VALUE;

  if (typeof value === "string") {
    const timeOnlyMatch = TIME_ONLY_PATTERN.exec(value);
    if (timeOnlyMatch) {
      const [, hours, minutes] = timeOnlyMatch;
      return `${hours}:${minutes}`;
    }
  }

  const date = toDate(value);
  if (Number.isNaN(date.getTime())) return NO_VALUE;

  const { hour, minute } = getZonedParts(date, timeZone);
  return `${hour}:${minute}`;
}

export function formatDateTime(
  value: string | Date | null | undefined,
  locale: Locale,
  timeZone?: string,
): string {
  if (!value) return NO_VALUE;
  const date = toDate(value);
  if (Number.isNaN(date.getTime())) return NO_VALUE;
  return `${formatDate(date, locale, timeZone)} - ${formatTime(date, locale, timeZone)}`;
}

export function formatTimeRange(
  startValue: string | null | undefined,
  endValue: string | null | undefined,
  locale: Locale,
): string {
  const start = formatTime(startValue, locale);
  const end = formatTime(endValue, locale);
  if (start === NO_VALUE && end === NO_VALUE) return NO_VALUE;
  return `${start} – ${end}`;
}

export function formatNumber(
  value: number | string | null | undefined,
  locale: Locale,
): string {
  if (value === null || value === undefined || value === "") return NO_VALUE;
  const numberValue = typeof value === "string" ? Number.parseFloat(value) : value;
  if (Number.isNaN(numberValue)) return NO_VALUE;

  return new Intl.NumberFormat("en-US", {
    useGrouping: true,
    maximumFractionDigits: 0,
  }).format(numberValue);
}

export function formatDecimal(
  value: number | string | null | undefined,
  locale: Locale,
  decimalPlaces = 2,
): string {
  if (value === null || value === undefined || value === "") return NO_VALUE;
  const numberValue = typeof value === "string" ? Number.parseFloat(value) : value;
  if (Number.isNaN(numberValue)) return NO_VALUE;

  return new Intl.NumberFormat("en-US", {
    useGrouping: true,
    minimumFractionDigits: decimalPlaces,
    maximumFractionDigits: decimalPlaces,
  }).format(numberValue);
}

export function formatQuantity(
  value: number | string | null | undefined,
  unit: string | null | undefined,
  locale: Locale,
): string {
  if (value === null || value === undefined || value === "") return NO_VALUE;
  const formatted = formatNumber(value, locale);
  if (formatted === NO_VALUE) return NO_VALUE;
  if (!unit) return formatted;
  return `${formatted} ${unit}`;
}

export function formatDuration(
  minutes: number | null | undefined,
  locale: Locale,
): string {
  if (minutes === null || minutes === undefined) return NO_VALUE;
  const unit = locale === "ar" ? "دقيقة" : "min";
  return `${formatNumber(minutes, locale)} ${unit}`;
}

export function formatPercent(
  value: number | null | undefined,
  locale: Locale,
  decimalPlaces = 1,
): string {
  if (value === null || value === undefined) return NO_VALUE;
  return `${formatDecimal(value, locale, decimalPlaces)}%`;
}

export function formatCurrency(
  value: number | string | null | undefined,
  currencyCode = "SAR",
  locale: Locale,
): string {
  if (value === null || value === undefined || value === "") return NO_VALUE;
  const numberValue = typeof value === "string" ? Number.parseFloat(value) : value;
  if (Number.isNaN(numberValue)) return NO_VALUE;
  return `${formatDecimal(numberValue, locale, 2)} ${currencyCode}`;
}
