"use client";

import { useLocale } from "next-intl";

import { useAuth } from "@/features/auth";
import type { Locale } from "@/i18n/config";
import {
  formatCurrency,
  formatDate,
  formatDateTime,
  formatDecimal,
  formatDuration,
  formatNumber,
  formatPercent,
  formatQuantity,
  formatTime,
  formatTimeRange,
} from "@/lib/formatters";

export function useFormatter() {
  const locale = useLocale() as Locale;
  const { user } = useAuth();
  const timeZone = user?.organization_timezone;

  return {
    date: (value: string | Date | null | undefined) => formatDate(value, locale, timeZone),
    time: (value: string | Date | null | undefined) => formatTime(value, locale, timeZone),
    dateTime: (value: string | Date | null | undefined) => formatDateTime(value, locale, timeZone),
    timeRange: (start: string | null | undefined, end: string | null | undefined) =>
      formatTimeRange(start, end, locale),
    number: (value: number | string | null | undefined) => formatNumber(value, locale),
    decimal: (value: number | string | null | undefined, decimalPlaces?: number) =>
      formatDecimal(value, locale, decimalPlaces),
    quantity: (value: number | string | null | undefined, unit?: string | null) =>
      formatQuantity(value, unit, locale),
    duration: (minutes: number | null | undefined) => formatDuration(minutes, locale),
    percent: (value: number | null | undefined, decimalPlaces?: number) =>
      formatPercent(value, locale, decimalPlaces),
    currency: (value: number | string | null | undefined, currencyCode?: string) =>
      formatCurrency(value, currencyCode, locale),
  };
}
