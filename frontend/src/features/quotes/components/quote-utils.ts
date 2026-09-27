import { getEnumLabel } from "@/i18n/enum-helpers";
import type { Locale } from "@/i18n/config";
import { quoteStatusColors } from "@/styles/badge-colors";
import { sharedStyles } from "@/styles/shared-styles";
import type { QuoteStatus } from "../types";

export function statusBadgeStyle(status: QuoteStatus) {
  return { ...sharedStyles.badge, ...quoteStatusColors[status] };
}

export function formatQuoteStatus(status: QuoteStatus, t: (key: string) => string) {
  return getEnumLabel("quote", "status", status, t);
}

export function formatCommercialCurrency(
  formattedCurrency: string,
  currencyCode: string,
  locale: Locale,
) {
  const formattedAmount = formattedCurrency
    .replace(/\sSAR$/, "")
    .replace(/\sUSD$/, "");

  if (currencyCode === "SAR") {
    return `${formattedAmount} ${locale === "ar" ? "ر.س" : "SAR"}`;
  }

  if (currencyCode === "USD") {
    return `${formattedAmount} $`;
  }

  return `${formattedAmount} ${currencyCode}`;
}
