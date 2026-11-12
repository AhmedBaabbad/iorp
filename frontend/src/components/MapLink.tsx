"use client";

import { useTranslations } from "next-intl";
import { sharedStyles } from "@/styles/shared-styles";

export function mapHref(locationUrl?: string | null, address?: string | null, city?: string | null, country?: string | null): string | null {
  if (locationUrl) {
    try {
      const parsed = new URL(locationUrl);
      if (parsed.protocol === "https:" && parsed.hostname) return locationUrl.trim();
    } catch { /* Old invalid links are never rendered as an href. */ }
  }
  if (!address?.trim()) return null;
  const query = [address, city, country].filter(value => value?.trim()).map(value => value!.trim()).join(", ");
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
}

export function MapLink({ locationUrl, address, city, country }: {
  locationUrl?: string | null; address?: string | null; city?: string | null; country?: string | null;
}) {
  const t = useTranslations("common.location");
  const href = mapHref(locationUrl, address, city, country);
  return href ? <a href={href} target="_blank" rel="noopener noreferrer" style={{...sharedStyles.secondaryButton, minHeight:"var(--control-height)", maxWidth:"100%", boxSizing:"border-box", overflowWrap:"anywhere"}}>{t("openGoogleMaps")}</a> : null;
}
